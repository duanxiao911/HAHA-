"""Clean-slate HAHA cultural media MVP."""

from __future__ import annotations

import streamlit as st

from haha_media.feed import STORIES
from haha_media.theme import apply_theme


def main() -> None:
    st.set_page_config(page_title="HAHA · 非遗影像馆", page_icon="◇", layout="wide")
    apply_theme()
    st.markdown(
        """
        <header class="site-header">
          <div class="wordmark">HAHA <span>HERITAGE, HERE AND AHEAD</span></div>
          <div class="header-note">文化媒体 · 礼物发现 · AI 对话</div>
        </header>
        """,
        unsafe_allow_html=True,
    )
    pages = st.tabs(("非遗影像馆", "非遗礼遇", "AI 学习对话", "我的文化档案"))
    with pages[0]:
        render_media_home()
    for page, title, copy in (
        (pages[1], "非遗礼遇", "从一段故事进入一件有文化来处的礼物。"),
        (pages[2], "AI 学习对话", "在这里提问、理解与继续探索非遗。"),
        (pages[3], "我的文化档案", "收藏、观看足迹与文化兴趣将在这里沉淀。"),
    ):
        with page:
            st.markdown(f"## {title}")
            st.info(f"{copy} 该板块将接在影像馆 MVP 之后开发。")


def render_media_home() -> None:
    st.markdown(
        """
        <section class="media-hero">
          <span>HAHA MEDIA · BETA</span>
          <h1>先被一门手艺打动，<br>再走近它的故事。</h1>
          <p>这是一个独立重写的非遗媒体首页。它用短内容建立好奇心，
          再自然地把观众带向 AI 解读与文化礼物。</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    primary, side = st.columns((1.45, 1), gap="large")
    with primary:
        featured = STORIES[0]
        st.markdown(featured.cover_markup, unsafe_allow_html=True)
        st.caption(f"本期影像 · {featured.duration} · {featured.category}")
        st.markdown(f"## {featured.title}")
        st.write(featured.summary)
        first, second = st.columns(2)
        if first.button("问 AI：这门手艺有什么故事？", type="primary", width="stretch"):
            st.session_state["media_response"] = featured.ai_answer
        if second.button("看看相关礼物", width="stretch"):
            st.session_state["media_response"] = (
                "礼物板块会依据你看过的内容、收藏和场景偏好做推荐。"
            )
    with side:
        st.markdown("### 接着看")
        for story in STORIES[1:4]:
            with st.container(border=True):
                st.markdown(story.cover_markup, unsafe_allow_html=True)
                st.caption(f"{story.duration} · {story.category}")
                st.markdown(f"**{story.title}**")
                if st.button("打开故事", key=f"open_{story.slug}", width="stretch"):
                    st.session_state["media_response"] = story.ai_answer
    if response := st.session_state.get("media_response"):
        st.markdown("### HAHA 正在为你展开")
        st.info(response)
    st.markdown("### 更多文化片段")
    columns = st.columns(3, gap="medium")
    for column, story in zip(columns, STORIES[3:], strict=False):
        with column:
            with st.container(border=True):
                st.markdown(story.cover_markup, unsafe_allow_html=True)
                st.caption(f"{story.duration} · {story.category}")
                st.markdown(f"**{story.title}**")
                st.caption(story.summary)
    st.caption("内容为比赛 MVP 中的原创演示文案与视觉占位，不包含旧仓库的商品、来源或图片资料。")


if __name__ == "__main__":
    main()
