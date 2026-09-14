from __future__ import annotations

from dataclasses import asdict
import os
import subprocess
import sys
from typing import Any

import streamlit as st
import streamlit.runtime

from src.agents.investigation_agent import InvestigationAgent
from src.agents.mitigation_agent import MitigationAgent
from src.agents.orchestrator import OrchestratorAgent
from src.database.bootstrap import ensure_database
from src.database.connection import DEFAULT_DB_PATH
from src.database.repository import WarehouseRepository
from src.simulation.simulator import ServiceActivitySimulator
from src.ui.chat import activity_markdown
from src.ui.dashboard import advisor_chart, compliance_chart, csat_chart, root_cause_chart, status_chart
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


def _init_state() -> None:
    st.session_state.setdefault("selected_ro", "RO-1002")
    st.session_state.setdefault("selected_ro_index", 0)
    st.session_state.setdefault("pending_plan", None)
    st.session_state.setdefault("agent_activity", [])
    st.session_state.setdefault("chat_history", [])
    st.session_state.setdefault("status_message", "")
    st.session_state.setdefault("last_investigation", None)
    st.session_state.setdefault("assistant_prompt", "")


def _dashboard_snapshot() -> dict[str, Any]:
    return {
        "kpis": repository.get_kpis(),
        "compliance": repository.compliance_breakdown(),
        "status_counts": repository.violation_status_counts(),
        "root_causes": repository.get_root_cause_summary(),
        "advisors": repository.get_advisor_performance(),
        "csat": repository.get_customer_satisfaction(),
    }


def _violations_data():
    violations = repository.get_sla_violations()
    display = violations_display_table(violations)
    ro_choices = violations["ro_id"].drop_duplicates().tolist()
    if not ro_choices:
        ro_choices = repository.get_repair_orders()["ro_id"].tolist()
    return violations, display, ro_choices


def _select_ro(ro_id: str) -> None:
    previous_ro = st.session_state.get("selected_ro")
    st.session_state.selected_ro = ro_id
    if previous_ro != ro_id:
        st.session_state.last_investigation = None
        st.session_state.pending_plan = None


def _set_selected_ro_from_index(ro_choices: list[str], index: int) -> None:
    safe_index = max(0, min(index, len(ro_choices) - 1)) if ro_choices else 0
    st.session_state.selected_ro_index = safe_index
    if ro_choices:
        st.session_state.selected_ro = ro_choices[safe_index]


def _status_variant(message: str) -> str:
    lowered = message.lower()
    if "error" in lowered or "failed" in lowered or "not found" in lowered:
        return "error"
    if "warning" in lowered or "unchanged" in lowered or "unavailable" in lowered:
        return "warning"
    return "success"


def _show_status() -> None:
    message = st.session_state.status_message
    if not message:
        return
    variant = _status_variant(message)
    if variant == "error":
        st.error(message)
    elif variant == "warning":
        st.warning(message)
    else:
        st.success(message)


def _queue_assistant_prompt(message: str) -> None:
    st.session_state.assistant_prompt = message


def _run_investigation(ro_id: str) -> dict[str, Any]:
    report = investigation_agent.investigate(ro_id)
    if "error" in report:
        st.session_state.agent_activity = [f"Failed to load {ro_id}"]
        st.session_state.last_investigation = report
        return report
    primary_violation = repository.get_primary_violation_for_ro(ro_id)
    st.session_state.agent_activity = [
        f"Found {ro_id}",
        f"Retrieved {len(report['events'])} service events",
        f"Found {len(report['violations'])} SLA violations",
        "Analyzed root cause",
        "Retrieved NHTSA context",
        "Retrieved weather context",
    ]
    report["primary_violation"] = primary_violation
    st.session_state.last_investigation = report
    return report


def _generate_plan(ro_id: str) -> str:
    plan = mitigation_agent.generate_plan(ro_id)
    st.session_state.pending_plan = asdict(plan) if plan else None
    return "Plan ready. Review the actions below before execution." if plan else "No mitigation plan available for this RO."


def _execute_plan() -> str:
    plan = st.session_state.pending_plan
    if not plan:
        return "No approved mitigation plan is waiting."
    result = mitigation_agent.execute_mitigation(plan["ro_id"], plan["actions"])
    st.session_state.pending_plan = None
    return result["message"]


def _submit_assistant_prompt(message: str) -> None:
    response = orchestrator.handle_request(message, st.session_state.selected_ro)
    st.session_state.chat_history.append({"role": "user", "content": message})
    st.session_state.chat_history.append({"role": "assistant", "content": response["text"]})
    st.session_state.agent_activity = response.get("activity_log", [])
    if response["intent"] == "mitigation" and response.get("data", {}).get("plan") is not None:
        st.session_state.pending_plan = asdict(response["data"]["plan"])


def _render_kpis(kpis: dict[str, Any]) -> None:
    labels = [
        ("Total Repair Orders", kpis.get("total_repair_orders", 0), None),
        ("Active SLA Violations", kpis.get("active_sla_violations", 0), None),
        ("Critical Violations", kpis.get("critical_violations", 0), None),
        ("At-Risk ROs", kpis.get("at_risk_ros", 0), None),
        ("Mitigated Violations", kpis.get("mitigated_violations", 0), None),
        ("Average SLA Compliance", f"{kpis.get('average_sla_compliance', 0)}%", None),
        ("Average Customer Satisfaction", kpis.get("average_customer_satisfaction", 0), None),
        ("High Customer Impact Cases", kpis.get("high_customer_impact_cases", 0), None),
    ]
    cols = st.columns(4)
    for index, (label, value, delta) in enumerate(labels):
        with cols[index % 4]:
            st.metric(label, value, delta)


def _render_sidebar() -> None:
    st.sidebar.markdown("## Control Panel")
    ro = repository.get_repair_order(st.session_state.selected_ro)
    if ro:
        st.sidebar.markdown(f"**Selected RO**\n\n{st.session_state.selected_ro}")
        st.sidebar.caption(f"{ro['customer_name']} | {ro['make']} {ro['model']} {ro['model_year']}")
        violation = repository.get_primary_violation_for_ro(st.session_state.selected_ro)
        if violation:
            st.sidebar.metric("Current severity", violation["severity"])
            st.sidebar.metric("Customer impact", violation["customer_impact"])
            st.sidebar.metric("Delay", f"{violation['difference_minutes']} min")
    if st.sidebar.button("Refresh Data", width="stretch", key="sidebar_refresh"):
        st.session_state.status_message = "Dashboard refreshed from DuckDB."
    if st.sidebar.button("Simulate Activity", width="stretch", key="sidebar_simulate"):
        st.session_state.status_message = simulator.simulate_new_service_activity()["message"]
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Demo Prompts")
    for prompt in [
        "Check today's SLA violations",
        "Why is RO-1002 violating SLA?",
        "Mitigate RO-1002",
        "Which service advisors have the most SLA breaches?",
    ]:
        if st.sidebar.button(prompt, width="stretch", key=f"sidebar_prompt_{prompt}"):
            _queue_assistant_prompt(prompt)
            st.session_state.status_message = f"Queued prompt: {prompt}"


def _render_dashboard() -> None:
    snapshot = _dashboard_snapshot()
    top_bar = st.columns([1, 1, 3])
    with top_bar[0]:
        if st.button("Refresh Dashboard", width="stretch", key="dashboard_refresh"):
            st.session_state.status_message = "Dashboard refreshed from DuckDB."
    with top_bar[1]:
        if st.button("Simulate New Service Activity", width="stretch", key="dashboard_simulate"):
            st.session_state.status_message = simulator.simulate_new_service_activity()["message"]
    with top_bar[2]:
        _show_status()

    _render_kpis(snapshot["kpis"])
    row_one = st.columns(2)
    row_two = st.columns(2)
    row_three = st.columns(2)
    with row_one[0]:
        st.plotly_chart(compliance_chart(snapshot["compliance"]), width="stretch")
    with row_one[1]:
        st.plotly_chart(status_chart(snapshot["status_counts"]), width="stretch")
    with row_two[0]:
        st.plotly_chart(root_cause_chart(snapshot["root_causes"]), width="stretch")
    with row_two[1]:
        st.plotly_chart(advisor_chart(snapshot["advisors"]), width="stretch")
    with row_three[0]:
        st.plotly_chart(csat_chart(snapshot["csat"]), width="stretch")
    with row_three[1]:
        st.markdown("### Live External Context")
        st.caption("Context is shown for the currently selected repair order in Investigation.")
        st.info("NHTSA and weather context load on demand and fall back gracefully when APIs are unavailable.")


def _render_violations() -> None:
    violations, display, ro_choices = _violations_data()
    st.markdown("### SLA Violations")
    st.caption("Click a row to select a repair order, then investigate or prepare mitigation.")
    selection = st.dataframe(
        display,
        width="stretch",
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="violations_table",
    )
    selected_rows = list(getattr(selection.selection, "rows", [])) if selection is not None else []
    if selected_rows:
        _set_selected_ro_from_index(ro_choices, int(selected_rows[0]))

    selected_ro = st.selectbox(
        "Select repair order",
        ro_choices,
        index=ro_choices.index(st.session_state.selected_ro) if st.session_state.selected_ro in ro_choices else st.session_state.selected_ro_index,
        key="violations_selectbox",
    )
    _select_ro(selected_ro)
    st.session_state.selected_ro_index = ro_choices.index(selected_ro) if selected_ro in ro_choices else 0
    st.caption(f"Selected RO: {st.session_state.selected_ro}")
    actions = st.columns(2)
    with actions[0]:
        if st.button("Investigate Selected RO", width="stretch", key="violations_investigate"):
            _run_investigation(st.session_state.selected_ro)
            st.session_state.status_message = f"Investigation loaded for {st.session_state.selected_ro}."
    with actions[1]:
        if st.button("Prepare Mitigation", width="stretch", key="violations_prepare_mitigation"):
            st.session_state.status_message = _generate_plan(st.session_state.selected_ro)

    _show_status()

    with st.expander("Top Violation Records", expanded=False):
        st.dataframe(
            violations[["ro_id", "violation_type", "severity", "status", "customer_impact", "root_cause", "difference_minutes"]],
            width="stretch",
            hide_index=True,
        )


def _render_investigation() -> None:
    st.markdown(f"### Selected RO: {st.session_state.selected_ro}")
    actions = st.columns(3)
    if actions[0].button("Load Investigation", width="stretch", key="investigation_load"):
        _run_investigation(st.session_state.selected_ro)
        st.session_state.status_message = f"Investigation refreshed for {st.session_state.selected_ro}."
    if actions[1].button("Prepare Mitigation from Investigation", width="stretch", key="investigation_prepare_mitigation"):
        st.session_state.status_message = _generate_plan(st.session_state.selected_ro)
    if actions[2].button("Ask Why In Assistant", width="stretch", key="investigation_ask_why"):
        _queue_assistant_prompt(f"Why is {st.session_state.selected_ro} violating SLA?")
        st.session_state.status_message = f"Queued assistant investigation for {st.session_state.selected_ro}."

    _show_status()

    report = st.session_state.last_investigation
    if not report or report.get("repair_order", {}).get("ro_id") != st.session_state.selected_ro:
        st.info("Select a repair order from Violations, then click Load Investigation.")
        return

    if "error" in report:
        st.error(report["error"])
        return

    ro = report["repair_order"]
    overview = st.columns(3)
    overview[0].markdown(f"**Customer**\n\n{ro['customer_name']}")
    overview[1].markdown(f"**Vehicle**\n\n{ro['make']} {ro['model']} {ro['model_year']}")
    overview[2].markdown(f"**Advisor**\n\n{ro['advisor_name']}")

    details = st.columns([1.2, 1, 1])
    with details[0]:
        st.markdown("### Service Timeline")
        st.code(timeline_markdown(report["events"]), language=None)
    with details[1]:
        st.markdown("### Root Cause")
        primary_violation = report.get("primary_violation")
        customer_impact = primary_violation["customer_impact"] if primary_violation else None
        st.markdown(root_cause_markdown(report["root_cause"], customer_impact))
    with details[2]:
        st.markdown("### External Context")
        st.markdown(external_context_markdown(report["recalls"], report["weather"]))


def _render_mitigation() -> None:
    st.markdown(f"### Mitigation for {st.session_state.selected_ro}")
    action_row = st.columns(2)
    if action_row[0].button("Generate Mitigation Plan", width="stretch", key="mitigation_generate"):
        st.session_state.status_message = _generate_plan(st.session_state.selected_ro)
    if action_row[1].button("Open Mitigation Prompt In Assistant", width="stretch", key="mitigation_queue_prompt"):
        _queue_assistant_prompt(f"Mitigate {st.session_state.selected_ro}")
        st.session_state.status_message = f"Queued mitigation prompt for {st.session_state.selected_ro}."

    pending_plan = st.session_state.pending_plan
    if pending_plan:
        class _PlanView:
            def __init__(self, payload: dict[str, Any]) -> None:
                self.ro_id = payload["ro_id"]
                self.actions = payload["actions"]
                self.reason = payload["reason"]

        st.markdown(plan_markdown(_PlanView(pending_plan)))
        if st.button("Execute Mitigation", type="primary", width="stretch", key="mitigation_execute"):
            st.session_state.status_message = _execute_plan()
    else:
        st.info("No mitigation plan generated yet.")

    _show_status()

    st.markdown("### Mitigation History")
    st.dataframe(repository.get_mitigation_history(), width="stretch", hide_index=True)


def _render_assistant() -> None:
    st.markdown("### Ask the AI Assistant")
    queued = st.session_state.assistant_prompt
    if queued:
        _submit_assistant_prompt(queued)
        st.session_state.assistant_prompt = ""

    st.caption(f"Selected RO context: {st.session_state.selected_ro}")
    prompt = st.chat_input("Ask about violations, mitigation, compliance, recalls, or advisors")
    if prompt and prompt.strip():
        _submit_assistant_prompt(prompt.strip())

    quick_prompts = st.columns(4)
    prompt_labels = [
        "Check today's SLA violations",
        f"Why is {st.session_state.selected_ro} violating SLA?",
        f"Mitigate {st.session_state.selected_ro}",
        "Which service advisors have the most SLA breaches?",
    ]
    for idx, label in enumerate(prompt_labels):
        if quick_prompts[idx].button(label, width="stretch", key=f"assistant_quick_{idx}"):
            _submit_assistant_prompt(label)

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    with st.expander("Agent Activity", expanded=False):
        st.markdown(activity_markdown(st.session_state.agent_activity))


def main() -> None:
    st.set_page_config(page_title="Automotive Service SLA Control Center", page_icon="garage", layout="wide")
    st.markdown(
        """
        <style>
        .stApp { background: linear-gradient(180deg, #0d1117 0%, #111827 100%); color: #f3f4f6; }
        .block-container { padding-top: 1.4rem; padding-bottom: 2rem; }
        [data-testid="stMetricValue"] { color: #f9fafb; }
        [data-testid="stMetricLabel"] { color: #9ca3af; }
        div[data-testid="stDataFrame"] { border: 1px solid rgba(148,163,184,0.18); border-radius: 14px; overflow: hidden; }
        div[data-testid="stMetric"] { background: rgba(17, 24, 39, 0.78); border: 1px solid rgba(148,163,184,0.15); padding: 0.8rem; border-radius: 16px; }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.element-container .stAlert) { background: transparent; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    _init_state()
    _render_sidebar()

    st.title("Automotive Service SLA Control Center")
    st.caption("DuckDB warehouse + deterministic SLA engine + controlled agentic mitigation")

    dashboard_tab, violations_tab, investigation_tab, mitigation_tab, assistant_tab = st.tabs(
        ["Dashboard", "Violations", "Investigation", "Mitigation", "AI Assistant"]
    )

    with dashboard_tab:
        _render_dashboard()
    with violations_tab:
        _render_violations()
    with investigation_tab:
        _render_investigation()
    with mitigation_tab:
        _render_mitigation()
    with assistant_tab:
        _render_assistant()


if __name__ == "__main__":
    if os.environ.get("SLAP_STREAMLIT_CHILD") == "1" or streamlit.runtime.exists():
        main()
    else:
        env = os.environ.copy()
        env["SLAP_STREAMLIT_CHILD"] = "1"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                __file__,
                "--server.address",
                "0.0.0.0",
                "--server.port",
                "7860",
            ],
            check=False,
            env=env,
        )
