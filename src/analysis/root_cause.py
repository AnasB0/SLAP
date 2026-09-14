from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


ROOT_CAUSE_LABELS = {
    "PARTS_UNAVAILABLE": "Parts unavailable",
    "TECHNICIAN_UNAVAILABLE": "Technician unavailable",
    "INSPECTION_DELAY": "Inspection delay",
    "REPAIR_COMPLEXITY": "Repair complexity",
    "QC_BACKLOG": "QC backlog",
    "ADVISOR_DELAY": "Advisor delay",
    "CUSTOMER_DELAY": "Customer delay",
    "SYSTEM_DELAY": "System delay",
    "WORKLOAD_OVERLOAD": "Workload overload",
    "UNKNOWN": "Unknown",
}


@dataclass(slots=True)
class RootCauseResult:
    primary_root_cause: str
    evidence: list[dict[str, Any]]
    contribution_pct: float
    secondary_causes: list[str]


def _minutes_between(events: dict[str, pd.Timestamp], start: str, end: str) -> float | None:
    if start not in events or end not in events:
        return None
    return round((events[end] - events[start]).total_seconds() / 60.0, 2)


def analyze_root_cause(events_df: pd.DataFrame, part_requests_df: pd.DataFrame) -> RootCauseResult:
    if events_df.empty:
        return RootCauseResult("UNKNOWN", [], 0.0, [])

    events = {
        row.event_type: pd.Timestamp(row.event_timestamp)
        for row in events_df.sort_values("event_timestamp").itertuples()
    }
    bottlenecks: list[tuple[str, float, dict[str, Any]]] = []

    inspection_delay = _minutes_between(events, "CUSTOMER_CHECK_IN", "INSPECTION_STARTED")
    if inspection_delay and inspection_delay > 20:
        bottlenecks.append(
            (
                "INSPECTION_DELAY",
                inspection_delay - 20,
                {
                    "label": "Inspection start",
                    "start": str(events["CUSTOMER_CHECK_IN"]),
                    "end": str(events["INSPECTION_STARTED"]),
                    "delay_minutes": inspection_delay,
                },
            )
        )

    tech_delay = _minutes_between(events, "INSPECTION_COMPLETED", "TECHNICIAN_ASSIGNED")
    if tech_delay and tech_delay > 30:
        bottlenecks.append(
            (
                "TECHNICIAN_UNAVAILABLE",
                tech_delay - 30,
                {
                    "label": "Technician assignment",
                    "start": str(events["INSPECTION_COMPLETED"]),
                    "end": str(events["TECHNICIAN_ASSIGNED"]),
                    "delay_minutes": tech_delay,
                },
            )
        )

    if not part_requests_df.empty:
        first_request = part_requests_df.sort_values("requested_at").iloc[0]
        if pd.notna(first_request["received_at"]):
            parts_delay = round((pd.Timestamp(first_request["received_at"]) - pd.Timestamp(first_request["requested_at"])).total_seconds() / 60.0, 2)
            if parts_delay > 60:
                bottlenecks.append(
                    (
                        "PARTS_UNAVAILABLE",
                        parts_delay - 60,
                        {
                            "label": "Parts request",
                            "start": str(first_request["requested_at"]),
                            "end": str(first_request["received_at"]),
                            "delay_minutes": parts_delay,
                        },
                    )
                )
        else:
            bottlenecks.append(
                (
                    "PARTS_UNAVAILABLE",
                    90.0,
                    {
                        "label": "Parts request",
                        "start": str(first_request["requested_at"]),
                        "end": "pending",
                        "delay_minutes": 90.0,
                    },
                )
            )

    repair_delay = _minutes_between(events, "REPAIR_STARTED", "REPAIR_COMPLETED")
    if repair_delay and repair_delay > 180:
        bottlenecks.append(
            (
                "REPAIR_COMPLEXITY",
                repair_delay - 180,
                {
                    "label": "Repair duration",
                    "start": str(events["REPAIR_STARTED"]),
                    "end": str(events["REPAIR_COMPLETED"]),
                    "delay_minutes": repair_delay,
                },
            )
        )

    qc_delay = _minutes_between(events, "REPAIR_COMPLETED", "QC_STARTED")
    if qc_delay and qc_delay > 15:
        bottlenecks.append(
            (
                "QC_BACKLOG",
                qc_delay - 15,
                {
                    "label": "QC start",
                    "start": str(events["REPAIR_COMPLETED"]),
                    "end": str(events["QC_STARTED"]),
                    "delay_minutes": qc_delay,
                },
            )
        )

    notify_delay = _minutes_between(events, "VEHICLE_READY", "CUSTOMER_NOTIFIED")
    if notify_delay and notify_delay > 15:
        bottlenecks.append(
            (
                "ADVISOR_DELAY",
                notify_delay - 15,
                {
                    "label": "Customer notification",
                    "start": str(events["VEHICLE_READY"]),
                    "end": str(events["CUSTOMER_NOTIFIED"]),
                    "delay_minutes": notify_delay,
                },
            )
        )

    delivery_delay = _minutes_between(events, "CUSTOMER_ARRIVED_FOR_PICKUP", "VEHICLE_DELIVERED")
    if delivery_delay and delivery_delay > 30:
        bottlenecks.append(
            (
                "CUSTOMER_DELAY",
                delivery_delay - 30,
                {
                    "label": "Vehicle delivery",
                    "start": str(events["CUSTOMER_ARRIVED_FOR_PICKUP"]),
                    "end": str(events["VEHICLE_DELIVERED"]),
                    "delay_minutes": delivery_delay,
                },
            )
        )

    if not bottlenecks:
        return RootCauseResult("UNKNOWN", [], 0.0, [])

    bottlenecks.sort(key=lambda item: item[1], reverse=True)
    total_overrun = sum(item[1] for item in bottlenecks) or 1.0
    primary = bottlenecks[0]
    secondary = [item[0] for item in bottlenecks[1:3]]
    return RootCauseResult(
        primary_root_cause=primary[0],
        evidence=[item[2] for item in bottlenecks],
        contribution_pct=round(primary[1] / total_overrun * 100.0, 2),
        secondary_causes=secondary,
    )
