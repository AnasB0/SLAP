CREATE TABLE IF NOT EXISTS dim_customer (
    customer_id INTEGER PRIMARY KEY,
    customer_name VARCHAR NOT NULL,
    phone VARCHAR,
    email VARCHAR,
    loyalty_tier VARCHAR,
    region VARCHAR
);

CREATE TABLE IF NOT EXISTS dim_vehicle (
    vehicle_id INTEGER PRIMARY KEY,
    vin VARCHAR NOT NULL,
    make VARCHAR NOT NULL,
    model VARCHAR NOT NULL,
    model_year INTEGER NOT NULL,
    mileage INTEGER,
    urgency_level VARCHAR
);

CREATE TABLE IF NOT EXISTS dim_service_advisor (
    advisor_id INTEGER PRIMARY KEY,
    advisor_name VARCHAR NOT NULL,
    team VARCHAR,
    shift VARCHAR
);

CREATE TABLE IF NOT EXISTS dim_technician (
    technician_id INTEGER PRIMARY KEY,
    technician_name VARCHAR NOT NULL,
    skill_level VARCHAR,
    specialty VARCHAR,
    active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS dim_part (
    part_id INTEGER PRIMARY KEY,
    part_name VARCHAR NOT NULL,
    category VARCHAR,
    lead_time_minutes INTEGER
);

CREATE TABLE IF NOT EXISTS dim_sla_policy (
    policy_id VARCHAR PRIMARY KEY,
    policy_name VARCHAR NOT NULL,
    threshold_minutes INTEGER NOT NULL,
    at_risk_ratio DOUBLE NOT NULL,
    applies_to VARCHAR NOT NULL,
    description VARCHAR
);

CREATE TABLE IF NOT EXISTS dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date DATE NOT NULL,
    day_name VARCHAR,
    month_name VARCHAR,
    year INTEGER,
    week_number INTEGER
);

CREATE TABLE IF NOT EXISTS fact_repair_order (
    ro_id VARCHAR PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    vehicle_id INTEGER NOT NULL,
    advisor_id INTEGER NOT NULL,
    technician_id INTEGER,
    opened_at TIMESTAMP NOT NULL,
    promised_ready_at TIMESTAMP NOT NULL,
    actual_ready_at TIMESTAMP,
    customer_arrival_at TIMESTAMP,
    delivered_at TIMESTAMP,
    ro_status VARCHAR NOT NULL,
    service_type VARCHAR NOT NULL,
    concern VARCHAR NOT NULL,
    estimated_repair_minutes INTEGER NOT NULL,
    priority VARCHAR NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES dim_customer(customer_id),
    FOREIGN KEY (vehicle_id) REFERENCES dim_vehicle(vehicle_id),
    FOREIGN KEY (advisor_id) REFERENCES dim_service_advisor(advisor_id),
    FOREIGN KEY (technician_id) REFERENCES dim_technician(technician_id)
);

CREATE TABLE IF NOT EXISTS fact_service_event (
    event_id BIGINT PRIMARY KEY,
    ro_id VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,
    event_timestamp TIMESTAMP NOT NULL,
    actor_type VARCHAR,
    actor_id VARCHAR,
    notes VARCHAR,
    meta_json VARCHAR,
    FOREIGN KEY (ro_id) REFERENCES fact_repair_order(ro_id)
);

CREATE TABLE IF NOT EXISTS fact_part_request (
    part_request_id BIGINT PRIMARY KEY,
    ro_id VARCHAR NOT NULL,
    part_id INTEGER NOT NULL,
    requested_at TIMESTAMP NOT NULL,
    received_at TIMESTAMP,
    quantity INTEGER NOT NULL,
    status VARCHAR NOT NULL,
    FOREIGN KEY (ro_id) REFERENCES fact_repair_order(ro_id),
    FOREIGN KEY (part_id) REFERENCES dim_part(part_id)
);

CREATE TABLE IF NOT EXISTS fact_sla_violation (
    violation_id VARCHAR PRIMARY KEY,
    ro_id VARCHAR NOT NULL,
    policy_id VARCHAR NOT NULL,
    violation_type VARCHAR NOT NULL,
    severity VARCHAR NOT NULL,
    threshold_minutes DOUBLE NOT NULL,
    actual_minutes DOUBLE NOT NULL,
    difference_minutes DOUBLE NOT NULL,
    detected_at TIMESTAMP NOT NULL,
    status VARCHAR NOT NULL,
    customer_impact VARCHAR NOT NULL,
    customer_impact_score DOUBLE NOT NULL,
    root_cause VARCHAR NOT NULL,
    FOREIGN KEY (ro_id) REFERENCES fact_repair_order(ro_id),
    FOREIGN KEY (policy_id) REFERENCES dim_sla_policy(policy_id)
);

CREATE TABLE IF NOT EXISTS fact_customer_satisfaction (
    csat_id BIGINT PRIMARY KEY,
    ro_id VARCHAR NOT NULL,
    customer_id INTEGER NOT NULL,
    advisor_id INTEGER NOT NULL,
    score INTEGER NOT NULL,
    comment VARCHAR,
    recorded_at TIMESTAMP NOT NULL,
    FOREIGN KEY (ro_id) REFERENCES fact_repair_order(ro_id)
);

CREATE TABLE IF NOT EXISTS fact_mitigation (
    mitigation_id VARCHAR PRIMARY KEY,
    ro_id VARCHAR NOT NULL,
    violation_id VARCHAR NOT NULL,
    action VARCHAR NOT NULL,
    reason VARCHAR NOT NULL,
    executed_at TIMESTAMP NOT NULL,
    executed_by VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    customer_notification BOOLEAN DEFAULT FALSE,
    idempotency_key VARCHAR NOT NULL,
    FOREIGN KEY (ro_id) REFERENCES fact_repair_order(ro_id)
);

CREATE TABLE IF NOT EXISTS fact_customer_notification (
    notification_id VARCHAR PRIMARY KEY,
    ro_id VARCHAR NOT NULL,
    customer_id INTEGER NOT NULL,
    message VARCHAR NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    channel VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    FOREIGN KEY (ro_id) REFERENCES fact_repair_order(ro_id)
);
