# Automotive SLA Agentic AI + Data Warehouse

This project is a complete local demo of an automotive service operations control center. It combines a DuckDB data warehouse, deterministic SLA monitoring, root-cause analysis, controlled mitigation execution, synthetic dealership data, public-context APIs, and an agent-style natural-language assistant.

The demo is intentionally simple enough for a student presentation while still showing real tool use and real database state changes.

## Project Overview

The application monitors synthetic repair orders and service events for SLA risk, explains why delays happened, ranks customer impact, recommends mitigations, waits for explicit user approval, executes the mitigation, and writes the result back into DuckDB.

The app includes:

- DuckDB warehouse with dimension and fact tables
- Synthetic automotive dealership operations data
- Deterministic SLA engine
- Deterministic root-cause engine
- Customer impact scoring
- OpenRouter integration using `openai/gpt-4o-mini`
- Public API context from NHTSA and Open-Meteo
- Gradio dashboard with tabs for dashboard, violations, investigation, mitigation, and AI assistant
- Simulation of new service activity
- Pytest coverage for core workflows

## Architecture

High-level flow:

```text
User request
	-> Orchestrator agent
	-> Data agent / SLA agent / Investigation agent / Context agent / Mitigation agent
	-> DuckDB queries + deterministic rules
	-> Recommendation
	-> User approval
	-> Mitigation execution
	-> Database update
	-> Dashboard refresh
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/AGENTS.md](docs/AGENTS.md).

## Technologies

- Python 3.11+
- DuckDB
- Pandas
- FastAPI
- Gradio
- Plotly
- httpx
- Pydantic
- python-dotenv
- OpenRouter
- pytest

## Why DuckDB?

DuckDB is a strong fit for this demo because it is:

- Local: no separate database server required
- Free: no paid infrastructure needed
- Fast: analytical SQL runs well on a laptop
- Simple: easy to inspect and reset during demos
- Python-friendly: works naturally with Pandas
- Good for warehousing demos: fact and dimension modeling is easy to show

This project uses a star-schema-inspired layout with dimensions such as customers, vehicles, advisors, technicians, parts, and SLA policies, plus fact tables for repair orders, service events, part requests, SLA violations, customer satisfaction, mitigations, and notifications.

## Folder Structure

```text
.
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
├── data/
├── docs/
├── scripts/
├── sql/
├── src/
└── tests/
```

## Installation

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

## Environment Variables

Copy `.env.example` to `.env` and optionally set your OpenRouter key:

```env
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=openai/gpt-4o-mini
```

If the API key is missing, the app still works with deterministic routing and analysis.

## Database Initialization

The database is created automatically when the app starts. You can also initialize and seed it manually:

```bash
python scripts/init_database.py
python scripts/seed_data.py
```

Database path:

```text
data/automotive_sla.duckdb
```

## Running the Application

```bash
python app.py
```

Then open the local Gradio URL in your browser.

The application mounts Gradio on top of FastAPI, so the project also has a simple web-app structure if you want to extend it later.

## How the Agents Work

- Orchestrator agent: classifies intent, extracts `RO-####` references, delegates work, and combines results
- Data agent: reads operational data from DuckDB
- SLA agent: runs deterministic SLA checks and retrieves violations
- Investigation agent: builds the evidence package for a selected RO
- Root-cause agent: identifies the primary bottleneck from service-event timings
- Context agent: fetches recall and weather context with graceful fallbacks
- Mitigation agent: proposes actions, waits for approval, executes actions, and logs the outcome

## How the SLA Engine Works

The SLA engine is fully deterministic. It does not ask the LLM whether a violation occurred.

Examples of rules implemented in Python:

- Appointment wait <= 30 minutes
- Inspection begins <= 20 minutes after check-in
- Technician assignment <= 30 minutes after inspection
- Parts wait <= 60 minutes
- QC starts <= 15 minutes after repair completion
- Customer notification <= 15 minutes after vehicle ready
- Delivery wait <= 30 minutes after customer arrival

The engine computes:

- Status: `ON_TRACK`, `AT_RISK`, `VIOLATED`, `MITIGATED`
- Severity: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`
- Root cause
- Customer impact label and score

## How Mitigation Works

Mitigation is a controlled action.

The workflow is:

1. The assistant or mitigation tab generates a plan.
2. The plan is shown to the user.
3. The user clicks `Execute Mitigation`.
4. The mitigation is written to `fact_mitigation`.
5. The violation status is updated to `MITIGATED`.
6. A simulated customer notification is logged when applicable.
7. The dashboard refreshes from DuckDB.

## Live API Integration

The app uses:

- NHTSA Recall API
- Open-Meteo

If those APIs fail, the dashboard and investigation views continue using safe fallback text:

`External API unavailable — showing cached/demo context.`

## Example Questions

These are supported in the AI Assistant tab:

- `Check today's SLA violations`
- `Why is RO-1002 violating SLA?`
- `Mitigate RO-1002`
- `Show me the highest customer-impact violations`
- `Which service advisors have the most SLA breaches?`
- `Show me today's SLA compliance`

## Sample SQL Queries

```sql
SELECT ro.ro_id,
			 c.customer_name,
			 v.make,
			 v.model,
			 COUNT(vi.violation_id) AS violations
FROM fact_repair_order ro
JOIN dim_customer c ON c.customer_id = ro.customer_id
JOIN dim_vehicle v ON v.vehicle_id = ro.vehicle_id
LEFT JOIN fact_sla_violation vi ON vi.ro_id = ro.ro_id
GROUP BY 1,2,3,4
ORDER BY violations DESC;
```

```sql
SELECT adv.advisor_name,
			 COUNT(DISTINCT ro.ro_id) AS total_ros,
			 COUNT(DISTINCT vi.ro_id) AS breached_ros
FROM dim_service_advisor adv
LEFT JOIN fact_repair_order ro ON ro.advisor_id = adv.advisor_id
LEFT JOIN fact_sla_violation vi ON vi.ro_id = ro.ro_id
GROUP BY 1
ORDER BY breached_ros DESC;
```

See [sql/analytics.sql](sql/analytics.sql).

## Troubleshooting

- If OpenRouter is not configured: the deterministic SLA tools still work
- If public APIs fail: the app shows fallback context instead of crashing
- If you want a clean reset: run `python scripts/seed_data.py`
- If tests fail after manual experimentation: reseed the database before running `pytest`

## Project Demo Flow

Use [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) for a structured 5 to 10 minute walkthrough.

