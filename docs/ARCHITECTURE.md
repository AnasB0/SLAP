# Architecture

## Core Workflow

```text
User Request
    |
    v
Orchestrator Agent
    |
    +--> Data Agent
    |
    +--> SLA Agent
    |
    +--> Investigation Agent
    |       |
    |       +--> Root Cause Agent
    |       |
    |       +--> Context Agent
    |
    +--> Mitigation Agent
             |
             v
      Approval Required
             |
             v
      Execute Mitigation
             |
             v
           DuckDB
             |
             v
         Dashboard
```

## Implementation Notes

- DuckDB is the single source of truth.
- The SLA engine is deterministic and runs from service-event timestamps.
- Root-cause analysis is deterministic and evidence-based.
- OpenRouter is used only for optional explanation quality, not for rule decisions.
- Mitigation is explicit, user-approved, and logged.
- Public APIs are supporting context only.

## Data Warehouse Design

Dimensions:

- `dim_customer`
- `dim_vehicle`
- `dim_service_advisor`
- `dim_technician`
- `dim_part`
- `dim_sla_policy`
- `dim_date`

Facts:

- `fact_repair_order`
- `fact_service_event`
- `fact_part_request`
- `fact_sla_violation`
- `fact_customer_satisfaction`
- `fact_mitigation`
- `fact_customer_notification`

## Deterministic Demo Scenarios

Seeded demo repair orders include:

- `RO-1002`: parts delay
- `RO-1010`: technician assignment delay
- `RO-1020`: QC delay
- `RO-1025`: customer notification delay

## Agent Activity Surface

The UI shows high-level operational activity such as:

- objective identified
- repair order found
- service events retrieved
- SLA rules checked
- violations found
- root cause analyzed
- external context retrieved
- mitigation plan generated
- waiting for approval

Private chain-of-thought is not exposed.
