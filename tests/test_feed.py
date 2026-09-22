from haha_media.feed import STORIES


def test_media_stories_have_unique_slugs() -> None:
    assert len(STORIES) >= 5
    assert len({story.slug for story in STORIES}) == len(STORIES)
