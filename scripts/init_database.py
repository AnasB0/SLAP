from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database.bootstrap import initialize_schema


if __name__ == "__main__":
    initialize_schema()
    print("Database schema initialized.")
