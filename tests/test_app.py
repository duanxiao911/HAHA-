from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_community_route_renders_without_exception() -> None:
    app = AppTest.from_file(str(APP_PATH), default_timeout=10)

    app.run()

    assert not app.exception


def test_script_workspace_renders_without_exception() -> None:
    app = AppTest.from_file(str(APP_PATH), default_timeout=10)
    app.query_params["space"] = "script"

    app.run()

    assert not app.exception
