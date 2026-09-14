from __future__ import annotations

import pandas as pd


def violations_display_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["RO", "Customer", "Vehicle", "Violation", "Severity", "Root Cause", "Delay", "Customer Impact", "Status", "Advisor"])
    display = df.copy()
    display["RO"] = display["ro_id"]
    display["Customer"] = display["customer_name"]
    display["Vehicle"] = display["vehicle"]
    display["Violation"] = display["violation_type"]
    display["Severity"] = display["severity"]
    display["Root Cause"] = display["root_cause"]
    display["Delay"] = display["difference_minutes"]
    display["Customer Impact"] = display["customer_impact"]
    display["Status"] = display["status"]
    display["Advisor"] = display["advisor_name"]
    return display[["RO", "Customer", "Vehicle", "Violation", "Severity", "Root Cause", "Delay", "Customer Impact", "Status", "Advisor"]]
