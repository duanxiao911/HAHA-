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


def test_parameter_board_values_drive_the_next_generation() -> None:
    app = AppTest.from_file(str(APP_PATH), default_timeout=10)
    app.query_params["space"] = "script"
    app.run()

    app.selectbox(key="creator_model_choice").select("本地演示")
    app.text_input(key="creator_param_craft").set_value("剪纸")
    app.text_area(key="creator_param_story_seed").set_value("一张红纸变成窗花")
    app.multiselect(key="creator_param_goals").select("工艺展示")
    app.selectbox(key="creator_param_platform").select("抖音")
    app.selectbox(key="creator_param_duration").select("30秒")
    app.selectbox(key="creator_param_aspect").select("16:9")
    app.button[0].click().run(timeout=10)

    brief = app.session_state["creator_brief"]
    assert brief.craft == "剪纸"
    assert brief.platform == "抖音"
    assert brief.duration == "30秒"
    assert brief.aspect_ratio == "16:9"
    assert app.session_state["model_run_mode"] == "local"
    assert not app.exception
