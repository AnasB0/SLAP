# Agents

## Orchestrator Agent

Objective:

Understand the user's objective, decompose the task, delegate work to specialized agents and tools, and produce a final evidence-based answer.

Responsibilities:

- classify intent
- extract repair-order references
- route to specialized agents
- combine deterministic results with optional LLM explanation

## Data Agent

Objective:

Retrieve reliable operational data from DuckDB.

Responsibilities:

- fetch repair orders
- fetch service events
- fetch customers, vehicles, advisors, technicians
- run warehouse queries

## SLA Agent

Objective:

Determine SLA state using deterministic business rules.

Responsibilities:

- evaluate SLA rules
- refresh warehouse violation facts
- rank highest-impact violations

## Investigation Agent

Objective:

Explain why an SLA violation occurred using evidence from service events and contextual data.

Responsibilities:

- gather the full repair-order evidence package
- retrieve timeline and violations
- call root-cause and context agents

## Root Cause Agent

Objective:

Identify the most likely operational bottleneck.

Responsibilities:

- compare timeline gaps
- detect parts, technician, inspection, repair, QC, advisor, and delivery bottlenecks

## Context Agent

Objective:

Retrieve relevant external recall and weather information.

Responsibilities:

- query NHTSA recall data
- query Open-Meteo weather data
- provide fallback data when APIs are unavailable

## Mitigation Agent

Objective:

Generate and execute controlled corrective actions after explicit user approval.

Responsibilities:

- generate mitigation plans from deterministic evidence
- wait for explicit approval in the UI
- execute the mitigation tool
- log mitigation history
- simulate customer notification when required
