# Demo Script

## 5 to 10 Minute Demo Flow

1. Open the dashboard and explain that the KPIs come directly from DuckDB.
2. Show the data warehouse idea: fact tables for operational events and dimension tables for customers, vehicles, advisors, technicians, parts, and SLA policies.
3. Move to the violations tab and highlight active SLA problems.
4. Select `RO-1002` from the table or dropdown.
5. Open the investigation tab.
6. Ask the AI assistant: `Why is RO-1002 violating SLA?`
7. Show the service-event timeline and point out the parts request and parts receipt delay.
8. Show the root-cause panel and explain that the delay is determined from timestamps, not guessed by the LLM.
9. Show NHTSA recall context and weather context. Mention that API failures fall back gracefully.
10. Open the mitigation tab and generate the mitigation plan.
11. Click `Execute Mitigation`.
12. Show that the mitigation history table updates and the violation state changes in DuckDB.
13. Refresh the dashboard and show the metrics updating from live database state.
14. Click `Simulate New Service Activity` to show new operational events flowing into the warehouse.
15. Ask: `Which service advisors have the most SLA breaches?`

## Suggested Narration

- Emphasize the split between deterministic rules and optional LLM explanation.
- Emphasize that mitigation requires explicit user approval.
- Emphasize that this is a local, reproducible, student-friendly analytics and agentic-AI demo.
