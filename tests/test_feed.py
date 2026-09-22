from haha_media.feed import STORIES
from haha_media.script_writer import ContentBrief, generate_content_script


def test_media_stories_have_unique_slugs() -> None:
    assert len(STORIES) >= 5
    assert len({story.slug for story in STORIES}) == len(STORIES)


def test_script_generator_creates_a_claim_cautious_shooting_package() -> None:
    script = generate_content_script(
        ContentBrief("竹编", "一片竹篾被慢慢压弯", "年轻生活方式用户", "小红书", "温暖叙事")
    )

    assert "竹编" in script.title
    assert len(script.shots) == 5
    assert "核验来源" in script.caption
