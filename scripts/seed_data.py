from __future__ import annotations

import json
import random
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database.bootstrap import initialize_schema
from src.database.connection import DEFAULT_DB_PATH, get_connection


ADVISORS = [
    (1, "Ahmed Rahman", "North", "Morning"),
    (2, "Sara Johnson", "South", "Morning"),
    (3, "Miguel Torres", "Express", "Day"),
    (4, "Lina Patel", "Premium", "Day"),
    (5, "Omar Hassan", "Fleet", "Evening"),
]

TECHNICIANS = [
    (1, "Priya Singh", "Master", "Diagnostics", True),
    (2, "David Kim", "Senior", "Brakes", True),
    (3, "Hassan Ali", "Senior", "Electrical", True),
    (4, "Emily Chen", "Journeyman", "General", True),
    (5, "Luis Martinez", "Master", "Engine", True),
    (6, "Ava Brown", "Journeyman", "Suspension", True),
    (7, "Noah Wilson", "Senior", "HVAC", True),
    (8, "Mia Garcia", "Master", "Hybrid", True),
]

PARTS = [
    (1, "Brake Pad Set", "Brakes", 35),
    (2, "Oil Filter", "Maintenance", 15),
    (3, "Battery Pack Sensor", "Electrical", 80),
    (4, "Water Pump", "Cooling", 55),
    (5, "Control Arm", "Suspension", 75),
    (6, "HVAC Blower Motor", "HVAC", 60),
    (7, "Door Actuator", "Body", 40),
    (8, "Ignition Coil", "Engine", 25),
    (9, "Hybrid Cooling Pump", "Hybrid", 90),
    (10, "Tire Pressure Sensor", "Electrical", 20),
]

SLA_POLICIES = [
    ("appointment_wait", "Appointment wait", 30, 0.8, "APPOINTMENT_TO_CHECK_IN", "Customer should not wait more than 30 minutes after appointment."),
    ("inspection_start", "Inspection start", 20, 0.8, "CHECK_IN_TO_INSPECTION", "Inspection should start within 20 minutes of check-in."),
    ("technician_assignment", "Technician assignment", 30, 0.8, "INSPECTION_TO_TECH_ASSIGNMENT", "Technician should be assigned within 30 minutes of inspection completion."),
    ("parts_wait", "Parts wait", 60, 0.8, "PARTS_REQUEST_TO_RECEIPT", "Parts should arrive within 60 minutes of request."),
    ("repair_duration", "Repair duration", 180, 0.8, "REPAIR_START_TO_COMPLETE", "Repair should finish within the promised estimate."),
    ("qc_start", "QC start", 15, 0.8, "REPAIR_COMPLETE_TO_QC_START", "QC should begin within 15 minutes of repair completion."),
    ("customer_notification", "Customer notification", 15, 0.8, "VEHICLE_READY_TO_CUSTOMER_NOTIFIED", "Customer should be notified within 15 minutes of vehicle ready."),
    ("delivery_wait", "Delivery wait", 30, 0.8, "CUSTOMER_ARRIVAL_TO_DELIVERED", "Vehicle delivery should complete within 30 minutes of customer arrival."),
    ("overall_service_duration", "Overall service duration", 360, 0.85, "CHECK_IN_TO_VEHICLE_READY", "Overall service duration should stay within promise."),
]


def _generate_customers() -> list[tuple[int, str, str, str, str, str]]:
    first_names = [
        "Sara", "Omar", "Lina", "David", "Amira", "John", "Priya", "Carlos", "Nadia", "Mason",
        "Ella", "Ibrahim", "Sophia", "Lucas", "Aisha", "Noah", "Mila", "Zain", "Grace", "Leo",
    ]
    last_names = [
        "Rahman", "Johnson", "Patel", "Kim", "Garcia", "Wilson", "Torres", "Brown", "Singh", "Ali",
    ]
    loyalty = ["Bronze", "Silver", "Gold", "Platinum"]
    regions = ["North", "South", "East", "West"]
    customers: list[tuple[int, str, str, str, str, str]] = []
    for customer_id in range(1, 101):
        random.seed(customer_id)
        first = random.choice(first_names)
        last = random.choice(last_names)
        name = f"{first} {last}"
        phone = f"555-01{customer_id:03d}"
        email = f"customer{customer_id}@demoauto.com"
        customers.append((customer_id, name, phone, email, random.choice(loyalty), random.choice(regions)))
    return customers


def _generate_vehicles() -> list[tuple[int, str, str, str, int, int, str]]:
    makes_models = [
        ("Toyota", "Camry"), ("Honda", "CR-V"), ("Ford", "F-150"), ("BMW", "X5"), ("Lexus", "RX"),
        ("Nissan", "Altima"), ("Kia", "Sportage"), ("Hyundai", "Tucson"), ("Chevrolet", "Tahoe"), ("Audi", "A4"),
    ]
    urgencies = ["LOW", "MEDIUM", "HIGH"]
    vehicles: list[tuple[int, str, str, str, int, int, str]] = []
    for vehicle_id in range(1, 101):
        random.seed(vehicle_id * 11)
        make, model = makes_models[(vehicle_id - 1) % len(makes_models)]
        year = 2020 + (vehicle_id % 5)
        vin = f"VIN{vehicle_id:014d}"
        mileage = 15000 + vehicle_id * 1300
        vehicles.append((vehicle_id, vin, make, model, year, mileage, random.choice(urgencies)))
    return vehicles


def _generate_dates(today: date) -> list[tuple[int, date, str, str, int, int]]:
    return [
        (
            int((today + timedelta(days=offset)).strftime("%Y%m%d")),
            today + timedelta(days=offset),
            (today + timedelta(days=offset)).strftime("%A"),
            (today + timedelta(days=offset)).strftime("%B"),
            int((today + timedelta(days=offset)).strftime("%Y")),
            int((today + timedelta(days=offset)).strftime("%V")),
        )
        for offset in range(-7, 8)
    ]


def _build_event_records(ro_id: str, start_ts: datetime, estimated_repair_minutes: int, scenario: str, advisor_id: int, technician_id: int) -> tuple[list[tuple], list[tuple], datetime, datetime, datetime, str]:
    checkpoints = [
        ("APPOINTMENT", 0, "SYSTEM", "appointment booked"),
        ("CUSTOMER_CHECK_IN", 18, "ADVISOR", "customer arrived"),
        ("INSPECTION_STARTED", 28, "ADVISOR", "walkaround started"),
        ("INSPECTION_COMPLETED", 48, "ADVISOR", "initial inspection complete"),
        ("TECHNICIAN_ASSIGNED", 62, "ADVISOR", "technician assigned"),
        ("REPAIR_STARTED", 75, "TECHNICIAN", "repair work started"),
        ("PARTS_REQUESTED", 88, "TECHNICIAN", "parts requested"),
        ("PARTS_RECEIVED", 122, "SYSTEM", "parts received"),
        ("REPAIR_COMPLETED", 75 + estimated_repair_minutes, "TECHNICIAN", "repair complete"),
        ("QC_STARTED", 75 + estimated_repair_minutes + 8, "TECHNICIAN", "qc started"),
        ("QC_COMPLETED", 75 + estimated_repair_minutes + 24, "TECHNICIAN", "qc complete"),
        ("CUSTOMER_NOTIFIED", 75 + estimated_repair_minutes + 38, "ADVISOR", "customer notified"),
        ("VEHICLE_READY", 75 + estimated_repair_minutes + 35, "SYSTEM", "vehicle ready"),
        ("CUSTOMER_ARRIVED_FOR_PICKUP", 75 + estimated_repair_minutes + 85, "CUSTOMER", "customer back for pickup"),
        ("VEHICLE_DELIVERED", 75 + estimated_repair_minutes + 98, "ADVISOR", "vehicle delivered"),
    ]
    overrides = {
        "parts_delay": {"PARTS_RECEIVED": 88 + 75},
        "inspection_delay": {"INSPECTION_STARTED": 50},
        "technician_delay": {"TECHNICIAN_ASSIGNED": 110},
        "repair_delay": {"REPAIR_COMPLETED": 75 + estimated_repair_minutes + 95},
        "qc_delay": {"QC_STARTED": 75 + estimated_repair_minutes + 40, "QC_COMPLETED": 75 + estimated_repair_minutes + 60},
        "notification_delay": {"CUSTOMER_NOTIFIED": 75 + estimated_repair_minutes + 70},
        "delivery_delay": {"VEHICLE_DELIVERED": 75 + estimated_repair_minutes + 130},
        "overall_delay": {
            "PARTS_RECEIVED": 88 + 90,
            "REPAIR_COMPLETED": 75 + estimated_repair_minutes + 70,
            "QC_STARTED": 75 + estimated_repair_minutes + 92,
            "CUSTOMER_NOTIFIED": 75 + estimated_repair_minutes + 120,
        },
        "at_risk_parts": {"PARTS_RECEIVED": 88 + 58},
        "at_risk_qc": {"QC_STARTED": 75 + estimated_repair_minutes + 14},
    }
    active_cutoff = scenario.startswith("active_")
    active_kind = scenario.replace("active_", "") if active_cutoff else ""
    if scenario in overrides:
        for event_type, value in overrides[scenario].items():
            checkpoints = [
                (etype, value if etype == event_type else minute, actor_type, note)
                for etype, minute, actor_type, note in checkpoints
            ]
    if active_cutoff and active_kind in overrides:
        for event_type, value in overrides[active_kind].items():
            checkpoints = [
                (etype, value if etype == event_type else minute, actor_type, note)
                for etype, minute, actor_type, note in checkpoints
            ]
    checkpoints.sort(key=lambda item: item[1])

    omitted_types: set[str] = set()
    if active_cutoff:
        if active_kind == "parts_delay":
            omitted_types |= {"PARTS_RECEIVED", "REPAIR_COMPLETED", "QC_STARTED", "QC_COMPLETED", "CUSTOMER_NOTIFIED", "VEHICLE_READY", "CUSTOMER_ARRIVED_FOR_PICKUP", "VEHICLE_DELIVERED"}
        elif active_kind == "repair_delay":
            omitted_types |= {"REPAIR_COMPLETED", "QC_STARTED", "QC_COMPLETED", "CUSTOMER_NOTIFIED", "VEHICLE_READY", "CUSTOMER_ARRIVED_FOR_PICKUP", "VEHICLE_DELIVERED"}
        elif active_kind == "inspection_delay":
            omitted_types |= {"INSPECTION_COMPLETED", "TECHNICIAN_ASSIGNED", "REPAIR_STARTED", "PARTS_REQUESTED", "PARTS_RECEIVED", "REPAIR_COMPLETED", "QC_STARTED", "QC_COMPLETED", "CUSTOMER_NOTIFIED", "VEHICLE_READY", "CUSTOMER_ARRIVED_FOR_PICKUP", "VEHICLE_DELIVERED"}

    events: list[tuple] = []
    part_requests: list[tuple] = []
    vehicle_ready_at = None
    delivered_at = None
    customer_arrival_at = None

    for index, (event_type, minute_offset, actor_type, note) in enumerate(checkpoints, start=1):
        if event_type in omitted_types:
            continue
        event_ts = start_ts + timedelta(minutes=minute_offset)
        actor_id = str(advisor_id if actor_type == "ADVISOR" else technician_id if actor_type == "TECHNICIAN" else 0)
        meta = json.dumps({"scenario": scenario})
        events.append((int(ro_id.split('-')[1]) * 100 + index, ro_id, event_type, event_ts, actor_type, actor_id, note, meta))
        if event_type == "PARTS_REQUESTED":
            part_id = (int(ro_id.split('-')[1]) % len(PARTS)) + 1
            requested_at = event_ts
            received_row = next(item for item in checkpoints if item[0] == "PARTS_RECEIVED")
            if "PARTS_RECEIVED" in omitted_types:
                received_at = None
                status = "PENDING"
            else:
                received_at = start_ts + timedelta(minutes=received_row[1])
                status = "RECEIVED"
            part_requests.append((int(ro_id.split('-')[1]) * 10 + 1, ro_id, part_id, requested_at, received_at, 1, status))
        if event_type == "VEHICLE_READY":
            vehicle_ready_at = event_ts
        if event_type == "CUSTOMER_ARRIVED_FOR_PICKUP":
            customer_arrival_at = event_ts
        if event_type == "VEHICLE_DELIVERED":
            delivered_at = event_ts

    if vehicle_ready_at is None:
        ready_checkpoint = next((item for item in checkpoints if item[0] == "VEHICLE_READY"), None)
        if ready_checkpoint and "VEHICLE_READY" not in omitted_types:
            vehicle_ready_at = start_ts + timedelta(minutes=ready_checkpoint[1])

    if customer_arrival_at is None:
        arrival_checkpoint = next((item for item in checkpoints if item[0] == "CUSTOMER_ARRIVED_FOR_PICKUP"), None)
        if arrival_checkpoint and "CUSTOMER_ARRIVED_FOR_PICKUP" not in omitted_types:
            customer_arrival_at = start_ts + timedelta(minutes=arrival_checkpoint[1])

    if delivered_at is None:
        delivered_checkpoint = next((item for item in checkpoints if item[0] == "VEHICLE_DELIVERED"), None)
        if delivered_checkpoint and "VEHICLE_DELIVERED" not in omitted_types:
            delivered_at = start_ts + timedelta(minutes=delivered_checkpoint[1])

    actual_ready_at = vehicle_ready_at
    ro_status = "READY" if vehicle_ready_at and delivered_at is None else "CLOSED" if delivered_at else "IN_PROGRESS"
    return events, part_requests, actual_ready_at, customer_arrival_at, delivered_at, ro_status


def seed_database(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    from src.sla.sla_engine import SLAEngine

    random.seed(42)
    initialize_schema(db_path)
    conn = get_connection(db_path)
    try:
        for table in [
            "fact_customer_notification",
            "fact_mitigation",
            "fact_customer_satisfaction",
            "fact_sla_violation",
            "fact_part_request",
            "fact_service_event",
            "fact_repair_order",
            "dim_date",
            "dim_sla_policy",
            "dim_part",
            "dim_technician",
            "dim_service_advisor",
            "dim_vehicle",
            "dim_customer",
        ]:
            conn.execute(f"DELETE FROM {table}")

        today = date.today()
        conn.executemany("INSERT INTO dim_customer VALUES (?, ?, ?, ?, ?, ?)", _generate_customers())
        conn.executemany("INSERT INTO dim_vehicle VALUES (?, ?, ?, ?, ?, ?, ?)", _generate_vehicles())
        conn.executemany("INSERT INTO dim_service_advisor VALUES (?, ?, ?, ?)", ADVISORS)
        conn.executemany("INSERT INTO dim_technician VALUES (?, ?, ?, ?, ?)", TECHNICIANS)
        conn.executemany("INSERT INTO dim_part VALUES (?, ?, ?, ?)", PARTS)
        conn.executemany("INSERT INTO dim_sla_policy VALUES (?, ?, ?, ?, ?, ?)", SLA_POLICIES)
        conn.executemany("INSERT INTO dim_date VALUES (?, ?, ?, ?, ?, ?)", _generate_dates(today))

        scenarios = {
            1002: "parts_delay",
            1005: "inspection_delay",
            1010: "technician_delay",
            1015: "repair_delay",
            1020: "qc_delay",
            1025: "notification_delay",
            1030: "overall_delay",
            1035: "delivery_delay",
            1040: "at_risk_parts",
            1045: "at_risk_qc",
            1050: "active_parts_delay",
            1054: "active_repair_delay",
            1055: "active_inspection_delay",
        }
        concerns = [
            "Brake vibration", "Routine maintenance", "Check engine light", "AC not cooling", "Battery warning",
            "Suspension noise", "Oil leak", "Hybrid system alert", "Door lock issue", "Tire sensor warning",
        ]
        service_types = ["Maintenance", "Diagnostics", "Repair", "Recall Inspection"]
        priorities = ["STANDARD", "PRIORITY", "VIP"]
        ro_rows: list[tuple] = []
        event_rows: list[tuple] = []
        part_rows: list[tuple] = []
        csat_rows: list[tuple] = []

        for ro_number in range(1001, 1056):
            customer_id = ((ro_number - 1001) % 100) + 1
            vehicle_id = ((ro_number - 1001) % 100) + 1
            advisor_id = ((ro_number - 1001) % len(ADVISORS)) + 1
            technician_id = ((ro_number - 1001) % len(TECHNICIANS)) + 1
            base_day = today - timedelta(days=(1055 - ro_number) % 4)
            start_ts = datetime.combine(base_day, time(hour=8 + ((ro_number - 1001) % 4), minute=((ro_number * 7) % 20)))
            estimate = 120 + ((ro_number - 1000) % 4) * 30
            concern = concerns[(ro_number - 1001) % len(concerns)]
            scenario = scenarios.get(ro_number, "normal")
            promised_ready_at = start_ts + timedelta(minutes=estimate + 150)
            events, part_requests, actual_ready_at, customer_arrival_at, delivered_at, ro_status = _build_event_records(
                f"RO-{ro_number}",
                start_ts,
                estimate,
                scenario,
                advisor_id,
                technician_id,
            )
            if scenario == "normal" and random.random() < 0.08:
                ro_status = "READY"
            ro_rows.append(
                (
                    f"RO-{ro_number}",
                    customer_id,
                    vehicle_id,
                    advisor_id,
                    technician_id,
                    start_ts,
                    promised_ready_at,
                    actual_ready_at,
                    customer_arrival_at,
                    delivered_at,
                    ro_status,
                    service_types[(ro_number - 1001) % len(service_types)],
                    concern,
                    estimate,
                    priorities[(ro_number - 1001) % len(priorities)],
                )
            )
            event_rows.extend(events)
            part_rows.extend(part_requests)
            if delivered_at:
                score = 5
                if scenario in {"parts_delay", "repair_delay", "overall_delay", "delivery_delay"}:
                    score = 2
                elif scenario in {"inspection_delay", "technician_delay", "qc_delay", "notification_delay"}:
                    score = 3
                elif scenario in {"at_risk_parts", "at_risk_qc"}:
                    score = 4
                csat_rows.append((ro_number * 10, f"RO-{ro_number}", customer_id, advisor_id, score, f"Synthetic feedback for {scenario}", delivered_at + timedelta(minutes=45),))

        conn.executemany(
            """
            INSERT INTO fact_repair_order VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ro_rows,
        )
        conn.executemany(
            "INSERT INTO fact_service_event VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            event_rows,
        )
        conn.executemany(
            "INSERT INTO fact_part_request VALUES (?, ?, ?, ?, ?, ?, ?)",
            part_rows,
        )
        conn.executemany(
            "INSERT INTO fact_customer_satisfaction VALUES (?, ?, ?, ?, ?, ?, ?)",
            csat_rows,
        )
    finally:
        conn.close()

    SLAEngine(db_path).refresh_sla_states()


if __name__ == "__main__":
    seed_database()
    print("Database seeded with synthetic automotive SLA data.")
