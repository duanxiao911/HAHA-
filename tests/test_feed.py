from haha_media.feed import STORIES
from haha_media.knowledge import retrieve_creative_methods, retrieve_operation_strategies
from haha_media.script_writer import ContentBrief, generate_content_script


def test_media_stories_have_unique_slugs() -> None:
    assert len(STORIES) >= 5
    assert len({story.slug for story in STORIES}) == len(STORIES)
    assert all(story.author and story.region for story in STORIES)
    assert all(story.views and story.interactions for story in STORIES)


def test_script_generator_creates_a_claim_cautious_shooting_package() -> None:
    script = generate_content_script(
        ContentBrief("竹编", "一片竹篾被慢慢压弯", "年轻生活方式用户", "小红书", "温暖叙事")
    )

    assert "竹编" in script.title
    assert len(script.shots) == 5
    assert "核验来源" in script.caption
    assert script.judgment
    assert len(script.storyboard) == 5
    assert any(status == "风险" for status, _ in script.audits)
    assert len(script.titles) >= 3
    assert script.method_sources
    assert script.strategy_sources
    assert all(chunk_id.startswith("M-") for chunk_id, _ in script.method_sources)
    assert all(chunk_id.startswith("O-") for chunk_id, _ in script.strategy_sources)
    assert script.fact_checks
    assert script.retrieval_trace is not None
    assert "事实库" not in " ".join(script.sources).replace("未接入非遗事实库", "")


def test_two_knowledge_bases_are_retrieved_independently() -> None:
    methods = retrieve_creative_methods("工艺手部特写和结构化分镜")
    strategies = retrieve_operation_strategies("小红书45秒前三秒Hook和标题")

    assert methods and strategies
    assert all(hit.chunk.knowledge_base == "creative_method" for hit in methods)
    assert all(hit.chunk.knowledge_base == "operation_strategy" for hit in strategies)
    assert methods[0].chunk.id.startswith("M-")
    assert strategies[0].chunk.id.startswith("O-")
