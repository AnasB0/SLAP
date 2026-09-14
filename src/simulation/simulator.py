from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from src.database.connection import DEFAULT_DB_PATH
from src.database.repository import WarehouseRepository
from src.sla.sla_engine import SLAEngine


class ServiceActivitySimulator:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.repository = WarehouseRepository(db_path)
        self.sla_engine = SLAEngine(db_path)
        self.random = random.Random(77)

    def simulate_new_service_activity(self) -> dict[str, str]:
        open_ros = self.repository.query_df(
            "SELECT ro_id, technician_id, ro_status FROM fact_repair_order WHERE ro_status IN ('IN_PROGRESS', 'READY', 'MITIGATED') ORDER BY ro_id"
        )
        if open_ros.empty:
            return {"message": "No open repair orders available for simulation."}
        ro = open_ros.iloc[self.random.randrange(len(open_ros))]
        ro_id = ro["ro_id"]
        latest_event_df = self.repository.query_df(
            "SELECT event_type, event_timestamp FROM fact_service_event WHERE ro_id = ? ORDER BY event_timestamp DESC LIMIT 1",
            [ro_id],
        )
        latest_type = latest_event_df.iloc[0]["event_type"]
        latest_time = latest_event_df.iloc[0]["event_timestamp"]
        transitions = {
            "CUSTOMER_CHECK_IN": "INSPECTION_STARTED",
            "INSPECTION_STARTED": "INSPECTION_COMPLETED",
            "INSPECTION_COMPLETED": "TECHNICIAN_ASSIGNED",
            "TECHNICIAN_ASSIGNED": "REPAIR_STARTED",
            "REPAIR_STARTED": "PARTS_REQUESTED",
            "PARTS_REQUESTED": "PARTS_RECEIVED",
            "PARTS_RECEIVED": "REPAIR_COMPLETED",
            "REPAIR_COMPLETED": "QC_STARTED",
            "QC_STARTED": "QC_COMPLETED",
            "QC_COMPLETED": "VEHICLE_READY",
            "VEHICLE_READY": "CUSTOMER_NOTIFIED",
            "CUSTOMER_NOTIFIED": "CUSTOMER_ARRIVED_FOR_PICKUP",
            "CUSTOMER_ARRIVED_FOR_PICKUP": "VEHICLE_DELIVERED",
        }
        next_event = transitions.get(latest_type, "CUSTOMER_NOTIFIED")
        new_time = latest_time + timedelta(minutes=self.random.randint(8, 28))
        self.repository.add_service_event(
            ro_id=ro_id,
            event_type=next_event,
            event_timestamp=new_time,
            actor_type="SYSTEM",
            actor_id=str(ro["technician_id"] or 0),
            notes=f"Simulated event: {next_event}",
            meta_json=json.dumps({"simulated": True}),
        )
        new_status = "IN_PROGRESS"
        actual_ready_at = None
        delivered_at = None
        customer_arrival_at = None
        if next_event == "VEHICLE_READY":
            new_status = "READY"
            actual_ready_at = new_time
        elif next_event == "CUSTOMER_ARRIVED_FOR_PICKUP":
            new_status = "READY"
            customer_arrival_at = new_time
        elif next_event == "VEHICLE_DELIVERED":
            new_status = "CLOSED"
            delivered_at = new_time
        self.repository.update_repair_order_state(
            ro_id=ro_id,
            ro_status=new_status,
            actual_ready_at=actual_ready_at,
            delivered_at=delivered_at,
            customer_arrival_at=customer_arrival_at,
        )
        self.sla_engine.refresh_sla_states()
        return {"message": f"Simulated new service activity for {ro_id}: {next_event}."}
