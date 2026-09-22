"""Clean-slate HAHA cultural media MVP."""

from __future__ import annotations

import streamlit as st

from haha_media.feed import STORIES
from haha_media.script_writer import ContentBrief, ContentScript, generate_content_script
from haha_media.theme import apply_theme

CATEGORY_LABELS = {
    "all": "首页",
    "hot": "热门",
    "embroidery": "刺绣",
    "pottery": "陶艺",
    "dyeing": "织染",
    "metal": "金工",
    "wood": "木作",
    "paper": "纸艺",
    "food": "传统美食",
    "folk": "民俗影像",
}


def main() -> None:
    st.set_page_config(page_title="HAHA · 非遗影像馆", page_icon="◇", layout="wide")
    apply_theme()
    space = str(st.query_params.get("space", "community"))
    if space in {"publish", "script"}:
        _render_creator_route(space)
        return
    module = str(st.query_params.get("module", "media"))
    _render_top_navigation(module)
    if module == "media":
        render_media_home()
    else:
        _render_module_placeholder(module)


def _render_top_navigation(module: str) -> None:
    brand, search, script, publish = st.columns(
        (1.05, 1.65, 0.72, 0.55), vertical_alignment="center"
    )
    with brand:
        st.markdown(
            '<div class="top-brand">HAHA <span>非遗视频社区</span></div>', unsafe_allow_html=True
        )
    with search:
        st.text_input(
            "搜索手艺、工艺或创作者",
            placeholder="搜一搜：竹编、蓝染、手艺人的一天",
            key="media_search",
            label_visibility="collapsed",
        )
    with script:
        if st.button("图文脚本", width="stretch"):
            _navigate("script")
    with publish:
        if st.button("＋ 投稿", width="stretch"):
            _navigate("publish")
    st.markdown(
        '<nav class="top-nav" aria-label="平台导航">'
        f'<a class="{"active" if module == "media" else ""}" href="?module=media">非遗影像馆</a>'
        f'<a class="{"active" if module == "gift" else ""}" href="?module=gift">非遗礼遇</a>'
        f'<a class="{"active" if module == "learn" else ""}" href="?module=learn">AI 学习对话</a>'
        f'<a class="{"active" if module == "profile" else ""}" href="?module=profile">我的文化档案</a>'
        "</nav>",
        unsafe_allow_html=True,
    )


def _render_module_placeholder(module: str) -> None:
    content = {
        "gift": ("非遗礼遇", "从一段故事进入一件有文化来处的礼物。"),
        "learn": ("AI 学习对话", "在这里提问、理解与继续探索非遗。"),
        "profile": ("我的文化档案", "收藏、观看足迹与文化兴趣将在这里沉淀。"),
    }
    title, copy = content.get(module, content["gift"])
    st.markdown(f"## {title}")
    st.info(f"{copy} 该板块当前为预留入口。")


def render_media_home() -> None:
    _render_community_feed()


def _navigate(space: str) -> None:
    st.query_params["space"] = space
    st.rerun()


def _render_creator_route(space: str) -> None:
    sidebar, workspace = st.columns((0.5, 2.7), gap="large")
    with sidebar:
        st.markdown(
            '<aside class="creator-sidebar"><div class="creator-logo">HAHA <span>创作中心</span></div>'
            "<strong>创作工作台</strong><span>内容管理</span><span>数据中心</span>"
            "<span>互动管理</span><span>文化审核</span></aside>",
            unsafe_allow_html=True,
        )
        if st.button("← 返回社区", width="stretch"):
            _navigate("community")
        if st.button(
            "视频投稿",
            type="primary" if space == "publish" else "secondary",
            width="stretch",
        ):
            _navigate("publish")
        if st.button(
            "图文脚本",
            type="primary" if space == "script" else "secondary",
            width="stretch",
        ):
            _navigate("script")
    with workspace:
        st.markdown(
            '<div class="workspace-top"><strong>HAHA 创作中心</strong>'
            "<span>让内容先被看见，再被理解。</span></div>",
            unsafe_allow_html=True,
        )
        if space == "publish":
            _render_video_publisher()
        else:
            _render_script_creator()


def _render_community_feed() -> None:
    category_key = str(st.query_params.get("category", "all"))
    category = CATEGORY_LABELS.get(category_key, "首页")
    _render_category_hub(category_key)
    stream, ranking = st.columns((2.25, 0.75), gap="large")
    with stream:
        st.markdown(f"### {'推荐内容' if category == '首页' else category}")
        _render_story_grid(category, st.session_state.get("media_search", ""))
        _render_published_posts()
    with ranking:
        st.markdown("### 热门榜")
        for rank, story in enumerate(STORIES[:5], start=1):
            st.markdown(
                f'<div class="ranking-item"><b>{rank:02}</b><div><strong>{story.title}</strong>'
                f"<small>{story.category} · {story.duration}</small></div></div>",
                unsafe_allow_html=True,
            )
        st.markdown("### 创作者工具")
        st.caption("视频投稿和 AI 图文脚本在上方两个创作入口中。")
    if response := st.session_state.get("media_response"):
        st.markdown("### HAHA 正在为你展开")
        st.info(response)


def _render_category_hub(active_key: str) -> None:
    chips = "".join(
        f'<a class="{"active" if key == active_key else ""}" '
        f'href="?module=media&category={key}">{label}</a>'
        for key, label in tuple(CATEGORY_LABELS.items())[2:]
    )
    st.markdown(
        '<section class="category-hub">'
        f'<a class="category-feature {"active" if active_key == "all" else ""}" '
        'href="?module=media&category=all"><i>◉</i><strong>动态</strong></a>'
        f'<a class="category-feature hot {"active" if active_key == "hot" else ""}" '
        'href="?module=media&category=hot"><i>✦</i><strong>热门</strong></a>'
        f'<div class="category-chips">{chips}</div>'
        '<div class="category-links"><span>▣ 专题</span><span>⚑ 活动</span>'
        "<span>▤ 文化地图</span><span>▶ 课堂</span></div></section>",
        unsafe_allow_html=True,
    )


def _render_story_grid(category: str, search: str) -> None:
    visible_stories = _filter_stories(category, search)
    columns = st.columns(3, gap="medium")
    for column, story in zip(columns * 2, visible_stories, strict=False):
        with column:
            with st.container(border=True):
                st.markdown(story.cover_markup, unsafe_allow_html=True)
                st.caption(f"{story.duration} · {story.category}")
                st.markdown(f"**{story.title}**")
                st.caption(story.summary)
                if st.button("播放并展开", key=f"open_{story.slug}", width="stretch"):
                    st.session_state["media_response"] = story.ai_answer
    st.caption("内容为比赛 MVP 中的原创演示文案与视觉占位，不包含旧仓库的商品、来源或图片资料。")


def _filter_stories(category: str, search: str) -> tuple:
    if category in {"首页", "热门"}:
        filtered = STORIES
    else:
        keyword_by_category = {
            "刺绣": ("刺绣", "人物"),
            "陶艺": ("陶艺", "工序"),
            "织染": ("织染", "纹样"),
            "金工": ("金工", "手艺人"),
            "木作": ("木作", "手艺人"),
            "纸艺": ("纸艺", "纹样"),
            "传统美食": ("美食",),
            "民俗影像": ("文化", "民俗"),
        }
        keywords = keyword_by_category.get(category, (category,))
        filtered = tuple(
            story for story in STORIES if any(word in story.category for word in keywords)
        )
    query = search.strip().casefold()
    if query:
        search_result = tuple(
            story
            for story in filtered
            if query in f"{story.title} {story.category} {story.summary}".casefold()
        )
        return search_result
    return filtered or STORIES


def _render_video_publisher() -> None:
    st.markdown(
        """
        <section class="creator-head">
          <span>CREATOR STUDIO</span><h2>发布一段手艺现场</h2>
          <p>把真实的创作过程交给观众。历史、地域与传承信息请在发布前核验。</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    form, rules = st.columns((1.7, 0.75), gap="large")
    with form:
        st.markdown("#### 1 · 上传视频")
        st.markdown(
            '<div class="upload-tip">支持 MP4、MOV、WebM 格式 · 建议横屏 16:9 或竖屏 9:16</div>',
            unsafe_allow_html=True,
        )
        with st.form("publish_video", border=False):
            video = st.file_uploader(
                "将视频拖到这里，或点击选择文件",
                type=("mp4", "mov", "webm"),
                label_visibility="visible",
            )
            st.markdown("#### 2 · 填写作品信息")
            title = st.text_input("视频标题", placeholder="例如：竹丝在指尖慢慢成形")
            first, second = st.columns(2)
            category = first.selectbox("投稿分区", ("手艺现场", "作品细节", "人物故事", "工序观察"))
            tags = second.text_input("内容标签", placeholder="例如：竹编、日常、手作")
            description = st.text_area(
                "创作说明", placeholder="讲讲你拍下了什么。请只写已确认的工艺、人物或作品信息。"
            )
            confirmed = st.checkbox("我确认发布内容不含未经核验的历史、传承或商业承诺。")
            submitted = st.form_submit_button("确认投稿", type="primary", width="stretch")
    with rules:
        st.markdown("#### 投稿小贴士")
        st.markdown(
            """
            <div class="creator-rule"><b>01</b><strong>前 3 秒先给细节</strong><span>手、材料或一个关键动作，比解释更能留下观众。</span></div>
            <div class="creator-rule"><b>02</b><strong>讲清一件事</strong><span>一条视频只回答一个问题，故事才不会散。</span></div>
            <div class="creator-rule"><b>03</b><strong>来源要能说明</strong><span>文化事实与商品信息须能回到创作者或可核验来源。</span></div>
            """,
            unsafe_allow_html=True,
        )
    if not submitted:
        return
    if video is None or not title.strip() or not confirmed:
        st.warning("请上传视频、填写标题，并确认内容核验说明后再投稿。")
        return
    posts = st.session_state.setdefault("published_posts", [])
    posts.insert(
        0,
        {
            "title": title.strip(),
            "description": description.strip() or "创作者暂未补充说明。",
            "category": category,
            "tags": tags.strip(),
            "video": video.getvalue(),
            "mime": video.type or "video/mp4",
        },
    )
    st.success("投稿成功，已发布到本次会话的社区内容流。正式上线时可接入账号、审核与云端存储。")
    _render_published_posts()


def _render_published_posts() -> None:
    posts = st.session_state.get("published_posts", [])
    if not posts:
        return
    st.markdown("### 新发布")
    for post in posts:
        with st.container(border=True):
            st.video(post["video"], format=post["mime"])
            st.caption(post["category"])
            st.markdown(f"**{post['title']}**")
            st.write(post["description"])
            if post["tags"]:
                st.caption("#" + post["tags"].replace("、", " #").replace("，", " #"))


def _render_script_creator() -> None:
    st.markdown("## 把一个想法变成可拍的图文脚本")
    st.caption("生成内容是创作草案；涉及历史、地域、传承或商品承诺，发布前必须由创作者补充并核验。")
    with st.form("script_creator", border=True):
        craft = st.text_input("技艺或作品", placeholder="例如：蓝染、竹编、铁画")
        story_seed = st.text_area("你想讲的一个瞬间", placeholder="例如：师傅把染好的布从水里提起")
        first, second = st.columns(2)
        audience = first.selectbox(
            "想对谁讲", ("第一次接触非遗的人", "年轻生活方式用户", "海外文化爱好者")
        )
        platform = second.selectbox("发布平台", ("小红书", "抖音", "Bilibili", "Instagram Reels"))
        tone = st.select_slider("表达气质", ("安静观察", "温暖叙事", "轻快科普"))
        generated = st.form_submit_button("生成 45 秒图文脚本", type="primary", width="stretch")
    if generated:
        try:
            st.session_state["generated_script"] = generate_content_script(
                ContentBrief(craft, story_seed, audience, platform, tone)
            )
        except ValueError as exc:
            st.warning(str(exc))
    script = st.session_state.get("generated_script")
    if isinstance(script, ContentScript):
        _render_script(script)


def _render_script(script: ContentScript) -> None:
    st.markdown(f"### {script.title}")
    st.info(f"开场钩子：{script.hook}")
    voiceover, storyboard = st.columns(2)
    with voiceover:
        st.markdown("**旁白 / 字幕**")
        for line in script.voiceover:
            st.write(f"— {line}")
    with storyboard:
        st.markdown("**分镜清单**")
        for shot in script.shots:
            st.write(f"— {shot}")
    st.markdown("**发布文案**")
    st.code(f"{script.caption}\n\n{' '.join(script.tags)}", language=None)
    st.download_button(
        "下载脚本文本",
        data=f"{script.title}\n\n{script.hook}\n\n" + "\n".join(script.voiceover),
        file_name="haha-content-script.txt",
        mime="text/plain",
    )


if __name__ == "__main__":
    main()
