from dataclasses import make_dataclass
from pathlib import Path

from streamlit.testing.v1 import AppTest

import app as app_module
from haha_media.script_writer import ContentBrief, generate_content_script

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_conversation_prompt_extracts_known_project_and_delivery_parameters() -> None:
    brief = app_module._brief_from_conversation(
        "请为中国剪纸制作一条面向初次接触非遗人群的30秒抖音工艺展示内容"
    )

    assert brief.craft == "中国剪纸"
    assert brief.platform == "抖音"
    assert brief.duration == "30秒"
    assert brief.goal == "工艺展示"


def test_old_session_brief_is_upgraded_to_current_schema() -> None:
    OldBrief = make_dataclass(
        "ContentBrief",
        [("craft", str), ("story_seed", str), ("audience", str), ("platform", str), ("tone", str)],
    )
    old_brief = OldBrief("剪纸", "红纸展开", "年轻学生", "抖音", "人物纪实")

    upgraded = app_module._rebuild_content_brief(old_brief, asset_context="参考正文")

    assert upgraded.craft == "剪纸"
    assert upgraded.asset_context == "参考正文"


def test_community_route_renders_without_exception() -> None:
    app = AppTest.from_file(str(APP_PATH), default_timeout=10)

    app.run()

    assert not app.exception


def test_script_workspace_renders_without_exception() -> None:
    app = AppTest.from_file(str(APP_PATH), default_timeout=10)
    app.query_params["space"] = "script"

    app.run()

    assert not app.exception


def test_all_public_routes_render_without_exception() -> None:
    routes = (
        {"module": "media"},
        {"module": "map"},
        {"module": "gift"},
        {"module": "learn"},
        {"module": "profile"},
        {"space": "publish"},
    )
    for query_params in routes:
        app = AppTest.from_file(str(APP_PATH), default_timeout=10)
        for key, value in query_params.items():
            app.query_params[key] = value
        app.run()
        assert not app.exception, query_params


def test_theme_exposes_shared_design_tokens() -> None:
    theme_path = APP_PATH.parent / "src" / "haha_media" / "theme.py"
    css = theme_path.read_text(encoding="utf-8")
    for token in (
        "--canvas",
        "--surface",
        "--brand",
        "--space-4",
        "--radius-control",
        "--radius-card",
        "--shadow-s",
        "--z-header",
        "--page-max",
    ):
        assert token in css


def test_placeholder_copy_is_removed_from_public_pages() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    assert "该板块当前为预留入口" not in source


def test_homepage_contains_carousel_and_compact_scroll_navigation() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    assert 'class="hero-carousel"' in source
    assert "unsafe_allow_javascript=True" in source
    assert "requestAnimationFrame(apply)" in source
    assert "classList.toggle" in source


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
    app.button(key="apply-creator-parameters").click().run(timeout=10)

    brief = app.session_state["creator_brief"]
    assert brief.craft == "剪纸"
    assert brief.platform == "抖音"
    assert brief.duration == "30秒"
    assert brief.aspect_ratio == "16:9"
    assert app.session_state["model_run_mode"] == "local"
    assert not app.exception


def test_parameter_board_regenerates_existing_result_with_a_new_run() -> None:
    app, original_run_id = _generated_workspace()

    app.selectbox(key="creator_param_platform").select("B站").run()
    app.selectbox(key="creator_param_duration").select("30秒").run()
    app.selectbox(key="creator_param_aspect").select("16:9").run()
    app.selectbox(key="creator_param_tone").select("人物纪实").run()
    app.button(key="apply-creator-parameters").click().run(timeout=10)

    brief = app.session_state["creator_brief"]
    script = app.session_state["generated_script"]
    feedback = app.session_state["creator_parameter_feedback"]
    assert brief.platform == "B站"
    assert brief.duration == "30秒"
    assert brief.aspect_ratio == "16:9"
    assert brief.tone == "人物纪实"
    assert script.retrieval_trace.generation_id != original_run_id
    assert ("推荐平台", "B站") in script.judgment
    assert ("推荐规格", "30秒 · 16:9") in script.judgment
    assert any("30秒" in title for title in script.titles)
    assert all("45秒" not in title for title in script.titles)
    assert script.shots[-1].startswith("26–30 秒")
    assert feedback["status"] == "success"
    assert "已应用参数并重新生成" in feedback["message"]
    assert not app.exception


def test_pending_parameter_label_updates_before_generation() -> None:
    app = AppTest.from_file(str(APP_PATH), default_timeout=10)
    app.query_params["space"] = "script"
    app.run()

    app.selectbox(key="creator_param_platform").select("抖音").run()
    app.selectbox(key="creator_param_duration").select("15秒").run()
    app.selectbox(key="creator_param_tone").select("人物纪实").run()

    context = "\n".join(str(item.value) for item in app.markdown)
    assert "待应用参数" in context
    assert "抖音" in context
    assert "15秒" in context
    assert not app.exception


def test_first_chat_generation_uses_parameter_panel_values() -> None:
    app = AppTest.from_file(str(APP_PATH), default_timeout=10)
    app.query_params["space"] = "script"
    app.run()

    app.selectbox(key="creator_model_choice").select("本地演示").run()
    app.selectbox(key="creator_param_platform").select("抖音").run()
    app.selectbox(key="creator_param_duration").select("30秒").run()
    app.selectbox(key="creator_param_aspect").select("3:4").run()
    app.selectbox(key="creator_param_tone").select("诗意东方").run()
    app.chat_input[0].set_value("中国剪纸").run(timeout=10)

    brief = app.session_state["creator_brief"]
    assert brief.craft == "中国剪纸"
    assert brief.platform == "抖音"
    assert brief.duration == "30秒"
    assert brief.aspect_ratio == "3:4"
    assert brief.tone == "诗意东方"
    assert ("推荐平台", "抖音") in app.session_state["generated_script"].judgment
    assert not app.exception


def _generated_workspace() -> tuple[AppTest, str]:
    brief = ContentBrief(
        "中国剪纸",
        "剪刀沿着红纸缓慢转动",
        "第一次接触非遗的人",
        "小红书",
        "安静观察",
    )
    script = generate_content_script(brief)
    run_id = script.retrieval_trace.generation_id
    app = AppTest.from_file(str(APP_PATH), default_timeout=10)
    app.query_params["space"] = "script"
    app.session_state["generated_script"] = script
    app.session_state["creator_brief"] = brief
    app.session_state["creator_stage"] = "master"
    app.session_state["creator_model_choice"] = "本地演示"
    app.session_state["creator_state_version"] = app_module.CREATOR_STATE_VERSION
    app.run()
    return app, run_id


def test_quick_revision_regenerates_and_updates_platform() -> None:
    app, run_id = _generated_workspace()

    app.button(key=f"quick-revision-{run_id}-8-改成抖音版").click().run(timeout=10)

    brief = app.session_state["creator_brief"]
    assert brief.platform == "抖音"
    assert brief.revision_instruction == "改成抖音版"
    assert app.session_state["generated_script"].retrieval_trace.generation_id != run_id
    assert not app.exception


def test_master_script_editor_writes_back_to_current_result() -> None:
    app, run_id = _generated_workspace()

    app.text_area(key=f"master-script-{run_id}").set_value("第一段\n第二段").run()

    assert app.session_state["generated_script"].voiceover == ("第一段", "第二段")
    assert not app.exception
