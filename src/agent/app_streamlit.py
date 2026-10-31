"""Compatibilidade: encaminha o comando antigo para a interface integrada."""

import runpy
from pathlib import Path

APP_INTEGRADA = (
    Path(__file__).resolve().parents[1] / "dashboard" / "app_dashboard.py"
)

runpy.run_path(str(APP_INTEGRADA), run_name="__main__")
