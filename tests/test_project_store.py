from pathlib import Path
from uuid import uuid4

from haha_media.project_store import list_projects, load_project, save_project
from haha_media.script_writer import ContentBrief, generate_content_script


def test_project_survives_save_and_load(monkeypatch) -> None:
    database = Path("data") / f"test-projects-{uuid4().hex}.db"
    monkeypatch.setenv("HAHA_PROJECT_DB", str(database))
    brief = ContentBrief(
        "中国剪纸",
        "一张红纸变成窗花",
        "第一次接触非遗的人",
        "小红书",
        "安静观察",
        asset_context="文件：notes.txt\n参考素材正文",
    )
    script = generate_content_script(brief)

    try:
        project_id = save_project(
            project_id=None,
            brief=brief,
            script=script,
            messages=[{"role": "user", "content": "制作剪纸内容"}],
            run_attempt={"status": "success", "run_id": script.retrieval_trace.generation_id},
            model_choice="本地演示",
        )
        restored = load_project(project_id)

        assert restored is not None
        assert restored["brief"] == brief
        assert restored["script"] == script
        assert restored["messages"][0]["content"] == "制作剪纸内容"
        assert list_projects()[0]["id"] == project_id
    finally:
        database.unlink(missing_ok=True)
