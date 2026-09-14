from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import gradio as gr
from fastapi import FastAPI

from src.agents.investigation_agent import InvestigationAgent
from src.agents.mitigation_agent import MitigationAgent
from src.agents.orchestrator import OrchestratorAgent
from src.database.bootstrap import ensure_database
from src.database.connection import DEFAULT_DB_PATH
from src.database.repository import WarehouseRepository
from src.simulation.simulator import ServiceActivitySimulator
from src.ui.chat import activity_markdown
from src.ui.dashboard import advisor_chart, compliance_chart, csat_chart, make_kpi_markdown, root_cause_chart, status_chart
from src.ui.investigation import external_context_markdown, root_cause_markdown, timeline_markdown
from src.ui.mitigation import plan_markdown
from src.ui.violations import violations_display_table


DB_PATH = DEFAULT_DB_PATH
ensure_database(DB_PATH)

repository = WarehouseRepository(DB_PATH)
orchestrator = OrchestratorAgent(DB_PATH)
investigation_agent = InvestigationAgent(DB_PATH)
mitigation_agent = MitigationAgent(DB_PATH)
simulator = ServiceActivitySimulator(DB_PATH)


def _empty_app_state() -> dict[str, Any]:
    return {"selected_ro": "RO-1002", "pending_plan": None, "agent_activity": [], "chat_history": []}


def load_dashboard() -> tuple[str, Any, Any, Any, Any, Any, str, str]:
    kpis = repository.get_kpis()
    compliance = repository.compliance_breakdown()
    status_counts = repository.violation_status_counts()
    root_causes = repository.get_root_cause_summary()
    advisors = repository.get_advisor_performance()
    csat = repository.get_customer_satisfaction()
    recall_demo = "Use the Investigation tab to load live recall context for the selected RO."
    weather_demo = "Use the Investigation tab to load live weather context."
    return (
        make_kpi_markdown(kpis),
        compliance_chart(compliance),
        status_chart(status_counts),
        root_cause_chart(root_causes),
        advisor_chart(advisors),
        csat_chart(csat),
        recall_demo,
        weather_demo,
    )


def load_violations() -> tuple[Any, list[str]]:
    df = repository.get_sla_violations()
    return violations_display_table(df), df["ro_id"].drop_duplicates().tolist()


def select_ro_from_dropdown(ro_id: str, state: dict[str, Any]) -> tuple[dict[str, Any], str, str]:
    state["selected_ro"] = ro_id
    ro = repository.get_repair_order(ro_id)
    selected_text = f"Selected RO: {ro_id}" if ro else f"Selected RO: {ro_id} not found"
    return state, selected_text, selected_text


def select_ro_from_table(table, evt: gr.SelectData, state: dict[str, Any]) -> tuple[dict[str, Any], str, str, str]:
    if table is None or evt is None:
        return state, state.get("selected_ro", "RO-1002"), f"Selected RO: {state.get('selected_ro', 'RO-1002')}", f"Selected RO: {state.get('selected_ro', 'RO-1002')}"
    row_index = evt.index[0] if isinstance(evt.index, tuple) else evt.index
    ro_id = str(table.iloc[row_index]["RO"])
    state["selected_ro"] = ro_id
    text = f"Selected RO: {ro_id}"
    return state, ro_id, text, text


def investigate_selected_ro(state: dict[str, Any]) -> tuple[str, str, str, str, dict[str, Any]]:
    ro_id = state.get("selected_ro") or "RO-1002"
    report = investigation_agent.investigate(ro_id)
    if "error" in report:
        return report["error"], "", "", "", state
    root = report["root_cause"]
    primary_violation = repository.get_primary_violation_for_ro(ro_id)
    selected_info = (
        f"{ro_id}\nCustomer: {report['repair_order']['customer_name']}\n"
        f"Vehicle: {report['repair_order']['make']} {report['repair_order']['model']} {report['repair_order']['model_year']}\n"
        f"Advisor: {report['repair_order']['advisor_name']}"
    )
    timeline = timeline_markdown(report["events"])
    root_md = root_cause_markdown(root, primary_violation["customer_impact"] if primary_violation else None)
    context_md = external_context_markdown(report["recalls"], report["weather"])
    state["agent_activity"] = [
        f"Found {ro_id}",
        f"Retrieved {len(report['events'])} service events",
        f"Found {len(report['violations'])} SLA violations",
        "Analyzed root cause",
        "Retrieved NHTSA context",
        "Retrieved weather context",
    ]
    return selected_info, timeline, root_md, context_md, state


def generate_mitigation(state: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    ro_id = state.get("selected_ro") or "RO-1002"
    plan = mitigation_agent.generate_plan(ro_id)
    state["pending_plan"] = asdict(plan) if plan else None
    status = "Plan ready. Click Execute Mitigation to apply changes." if plan else "No mitigation plan available for this RO."
    return plan_markdown(plan), status, state


def execute_mitigation(state: dict[str, Any]) -> tuple[str, Any, dict[str, Any], str, Any, Any, Any, Any, Any, Any, list[str]]:
    plan_dict = state.get("pending_plan")
    if not plan_dict:
        dashboard = load_dashboard()
        violations, choices = load_violations()
        return "No approved mitigation plan is waiting.", repository.get_mitigation_history(), state, *dashboard, violations, choices
    result = mitigation_agent.execute_mitigation(plan_dict["ro_id"], plan_dict["actions"])
    state["pending_plan"] = None
    dashboard = load_dashboard()
    violations, choices = load_violations()
    return result["message"], repository.get_mitigation_history(), state, *dashboard, violations, choices


def ask_ai(message: str, history: list[tuple[str, str]], state: dict[str, Any]) -> tuple[list[tuple[str, str]], str, dict[str, Any]]:
    response = orchestrator.handle_request(message, state.get("selected_ro"))
    history = history + [(message, response["text"])]
    state["agent_activity"] = response.get("activity_log", [])
    if response["intent"] == "mitigation" and response.get("data", {}).get("plan") is not None:
        state["pending_plan"] = asdict(response["data"]["plan"])
    return history, activity_markdown(state["agent_activity"]), state


def simulate_activity() -> tuple[str, str, Any, Any, Any, Any, Any, Any, str, str, Any, list[str]]:
    result = simulator.simulate_new_service_activity()
    dashboard = load_dashboard()
    violations, choices = load_violations()
    return result["message"], *dashboard, repository.get_mitigation_history(), choices


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="Automotive SLA Control Center") as demo:
        state = gr.State(_empty_app_state())
        gr.Markdown("# Automotive Service SLA Control Center")
        with gr.Tabs():
            with gr.Tab("📊 Dashboard"):
                kpi_md = gr.Markdown()
                compliance_plot = gr.Plot()
                status_plot = gr.Plot()
                root_plot = gr.Plot()
                advisor_plot = gr.Plot()
                csat_plot = gr.Plot()
                recall_box = gr.Markdown()
                weather_box = gr.Markdown()
                simulation_status = gr.Markdown("")
                refresh_dashboard_btn = gr.Button("🔄 Refresh Dashboard")
                simulate_btn = gr.Button("🔄 Simulate New Service Activity")
            with gr.Tab("🚨 Violations"):
                violations_table = gr.Dataframe(interactive=False)
                ro_dropdown = gr.Dropdown(label="Select RO", choices=[])
                selected_label = gr.Markdown("Selected RO: RO-1002")
                investigate_btn = gr.Button("🔎 Investigate Selected RO")
                mitigate_btn = gr.Button("🛠️ Mitigate Selected RO")
            with gr.Tab("🔎 Investigation"):
                investigation_selected = gr.Markdown()
                timeline_md = gr.Markdown()
                root_md = gr.Markdown()
                context_md = gr.Markdown()
            with gr.Tab("🛠️ Mitigation"):
                mitigation_plan_md = gr.Markdown("No mitigation plan generated yet.")
                mitigation_status_md = gr.Markdown("")
                execute_btn = gr.Button("▶ Execute Mitigation")
                mitigation_history = gr.Dataframe(interactive=False)
            with gr.Tab("💬 AI Assistant"):
                chatbot = gr.Chatbot(height=420)
                assistant_input = gr.Textbox(label="Ask the assistant", placeholder="Why is RO-1002 violating SLA?")
                assistant_send = gr.Button("Send")
                with gr.Accordion("Agent Activity", open=False):
                    activity_md = gr.Markdown("No agent activity recorded yet.")

        refresh_dashboard_btn.click(
            load_dashboard,
            outputs=[kpi_md, compliance_plot, status_plot, root_plot, advisor_plot, csat_plot, recall_box, weather_box],
        )
        simulate_btn.click(
            simulate_activity,
            outputs=[simulation_status, kpi_md, compliance_plot, status_plot, root_plot, advisor_plot, csat_plot, recall_box, weather_box, mitigation_history, ro_dropdown],
        )
        refresh_dashboard_btn.click(load_violations, outputs=[violations_table, ro_dropdown])
        violations_table.select(select_ro_from_table, inputs=[violations_table, state], outputs=[state, ro_dropdown, selected_label, investigation_selected])
        ro_dropdown.change(select_ro_from_dropdown, inputs=[ro_dropdown, state], outputs=[state, selected_label, investigation_selected])
        investigate_btn.click(investigate_selected_ro, inputs=[state], outputs=[investigation_selected, timeline_md, root_md, context_md, state])
        mitigate_btn.click(generate_mitigation, inputs=[state], outputs=[mitigation_plan_md, mitigation_status_md, state])
        execute_btn.click(
            execute_mitigation,
            inputs=[state],
            outputs=[mitigation_status_md, mitigation_history, state, kpi_md, compliance_plot, status_plot, root_plot, advisor_plot, csat_plot, recall_box, weather_box, violations_table, ro_dropdown],
        )
        assistant_send.click(ask_ai, inputs=[assistant_input, chatbot, state], outputs=[chatbot, activity_md, state])
        assistant_input.submit(ask_ai, inputs=[assistant_input, chatbot, state], outputs=[chatbot, activity_md, state])

        demo.load(load_dashboard, outputs=[kpi_md, compliance_plot, status_plot, root_plot, advisor_plot, csat_plot, recall_box, weather_box])
        demo.load(load_violations, outputs=[violations_table, ro_dropdown])
        demo.load(lambda: repository.get_mitigation_history(), outputs=[mitigation_history])
        demo.load(lambda: "Selected RO: RO-1002", outputs=[selected_label])

    return demo


app = FastAPI(title="Automotive SLA Agentic AI")
gradio_app = build_ui()
app = gr.mount_gradio_app(app, gradio_app, path="/")


if __name__ == "__main__":
    gradio_app.launch(server_name="0.0.0.0", server_port=7860)
