from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_interactions_work() -> None:
    app_test = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py")
    app_test.run(timeout=20)

    app_test.selectbox(key="violations_selectbox").select("RO-1002").run(timeout=20)
    app_test.button(key="violations_investigate").click().run(timeout=20)
    app_test.button(key="violations_prepare_mitigation").click().run(timeout=20)
    app_test.button(key="mitigation_execute").click().run(timeout=20)
    app_test.button(key="assistant_quick_1").click().run(timeout=20)

    assert len(app_test.exception) == 0
    assert len(app_test.chat_message) >= 2
