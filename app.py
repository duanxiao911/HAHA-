"""Clean-slate HAHA cultural media MVP."""

from __future__ import annotations

from html import escape

import streamlit as st

from haha_media.feed import STORIES
from haha_media.script_writer import ContentBrief, ContentScript, generate_content_script
from haha_media.theme import apply_theme

CATEGORY_LABELS = {
    "all": "首页",
    "hot": "热门",
    "embroidery": "刺绣",
    "dyeing": "蓝染",
    "pottery": "陶艺",
    "wood": "木雕",
    "paper": "剪纸",
    "opera": "戏曲",
    "folk": "民俗",
    "craft": "传统工艺",
}


def main() -> None:
    st.set_page_config(page_title="HAHA · 非遗影像馆", page_icon="◇", layout="wide")
    apply_theme()
    space = str(st.query_params.get("space", "community"))
    if space in {"publish", "script"}:
        _render_creator_route(space)
        return
    module = str(st.query_params.get("module", "media"))
    channel = str(st.query_params.get("channel", "all"))
    _render_navigation_system(module, channel)
    if module == "media":
        render_media_home()
    else:
        _render_module_placeholder(module)


def _render_navigation_system(module: str, channel: str) -> None:
    def page_link(key: str, label: str) -> str:
        current = ' class="active" aria-current="page"' if module == key else ""
        return f'<a{current} href="?module={key}">{label}</a>'

    def channel_link(key: str, label: str, *, icon: str = "") -> str:
        current = ' class="active" aria-current="page"' if channel == key else ""
        return f'<a{current} href="?module=media&channel={key}">{icon}{label}</a>'

    primary_channels = tuple(CATEGORY_LABELS.items())[2:7]
    extra_channels = tuple(CATEGORY_LABELS.items())[7:]
    primary_markup = "".join(channel_link(key, label) for key, label in primary_channels)
    extra_markup = "".join(channel_link(key, label) for key, label in extra_channels)
    st.markdown(
        '<header class="header-system">'
        '<div class="global-header">'
        '<a class="header-brand" href="?module=media">HAHA</a>'
        '<nav class="global-links" aria-label="全局导航">'
        f'{page_link("media", "首页")}<a href="?module=media">非遗影像</a>'
        f'{page_link("gift", "非遗礼遇")}<a href="?module=media&channel=folk">文化地图</a>'
        f"{page_link('learn', 'AI 学习')}</nav>"
        '<form class="header-search" method="get"><input type="hidden" name="module" value="media">'
        '<input name="q" aria-label="搜索视频、非遗项目、传承人或地区" '
        'placeholder="搜一搜：竹编、蓝染、手艺人的一天"><button type="submit">⌕</button></form>'
        '<nav class="user-links" aria-label="用户功能"><span>消息</span><span>动态</span>'
        '<span>收藏</span><span>历史</span><a href="?module=profile">文化档案</a>'
        '<a href="?space=script">AI 脚本</a></nav>'
        '<a class="publish-button" href="?space=publish">＋ 投稿</a></div>'
        '<div class="header-visual" aria-label="HAHA 非遗影像品牌视觉">'
        '<div class="visual-brand"><b>HAHA</b><span>HERITAGE IN MOTION</span></div>'
        '<div class="visual-copy"><strong>让手艺被看见，让故事继续发生</strong>'
        "<span>非遗影像 · 文化故事 · 青年共创</span></div>"
        '<i class="visual-seal">哈</i></div>'
        '<div class="channel-nav"><nav class="channel-main" aria-label="内容频道">'
        f"{channel_link('all', '动态', icon='◎ ')}{channel_link('hot', '热门', icon='🔥 ')}"
        f'<span class="channel-divider" aria-hidden="true"></span>{primary_markup}'
        '<details class="more-menu"><summary aria-label="展开更多非遗分类">更多⌄</summary>'
        '<div class="mega-menu"><section><strong>工艺</strong><a href="?module=media&channel=embroidery">刺绣</a>'
        '<a href="?module=media&channel=dyeing">蓝染</a><a href="?module=media&channel=wood">木雕</a>'
        '<a href="?module=media&channel=pottery">陶艺</a><a href="?module=media&channel=paper">剪纸</a></section>'
        '<section><strong>表演</strong><a href="?module=media&channel=opera">戏曲</a><span>舞蹈</span>'
        "<span>音乐</span><span>曲艺</span></section><section><strong>生活</strong><span>饮食</span>"
        '<span>节庆</span><a href="?module=media&channel=folk">民俗</a><span>服饰</span></section>'
        "<section><strong>探索</strong><span>文化地图</span><span>传承人</span><span>项目</span>"
        "<span>专题</span></section></div></details></nav>"
        '<nav class="channel-expanded" aria-label="扩展频道">'
        f'{extra_markup}<a href="?module=media">舞蹈</a><a href="?module=media">音乐</a>'
        '<a href="?module=media">饮食</a><a href="?module=media">节庆</a>'
        '<span class="channel-divider" aria-hidden="true"></span><a href="?module=media">专栏</a>'
        '<a href="?module=media">活动</a><a href="?module=media&channel=folk">文化地图</a>'
        '<a href="?module=learn">课堂</a></nav></div></header>',
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
    category_key = str(st.query_params.get("channel", "all"))
    search = str(st.query_params.get("q", ""))
    if category_key != "all" or search.strip():
        category = CATEGORY_LABELS.get(category_key, "首页")
        st.markdown(f"## {category if not search.strip() else '搜索结果'}")
        _render_card_row(_filter_stories(category, search), prefix="filtered")
        return
    _render_daily_feature()
    _render_channel_section("🔥 正在热门", STORIES, "hot")
    _render_channel_section("刺绣 · 一针一线里的故事", STORIES, "embroidery")
    _render_channel_section("陶艺 · 泥土与火的相遇", tuple(reversed(STORIES)), "pottery")
    _render_region_discovery()
    _render_special_topics()
    _render_ai_learning()
    _render_published_posts()
    if response := st.session_state.get("media_response"):
        st.markdown("### HAHA 正在为你展开")
        st.info(response)


def _render_daily_feature() -> None:
    st.markdown(
        '<div class="section-title"><h2>今日非遗</h2><span>编辑精选</span></div>',
        unsafe_allow_html=True,
    )
    featured, recommendations = st.columns((1.15, 1.85), gap="large")
    with featured:
        story = STORIES[0]
        with st.container(border=True):
            st.markdown(_video_thumbnail(story, featured=True), unsafe_allow_html=True)
            st.caption(f"今日大推荐 · {story.duration}")
            st.markdown(f"### {story.title}")
            st.caption(
                f"{getattr(story, 'author', 'HAHA 文化记录者')} · "
                f"{getattr(story, 'region', '中国')}"
            )
    with recommendations:
        stories = (STORIES[1:] + STORIES[:2])[:6]
        columns = st.columns(3, gap="medium")
        for index, story in enumerate(stories):
            with columns[index % 3]:
                _render_compact_card(story, f"daily_{index}")


def _render_channel_section(title: str, stories: tuple, prefix: str) -> None:
    st.markdown(
        f'<div class="section-title"><h2>{title}</h2><a href="?module=media">换一换 ↻</a></div>',
        unsafe_allow_html=True,
    )
    _render_card_row(stories, prefix=prefix)


def _render_card_row(stories: tuple, *, prefix: str) -> None:
    items = (stories + STORIES)[:5]
    columns = st.columns(5, gap="medium")
    for index, (column, story) in enumerate(zip(columns, items, strict=False)):
        with column:
            _render_compact_card(story, f"{prefix}_{index}")


def _render_compact_card(story, key: str) -> None:
    st.markdown(
        '<article class="video-card">'
        f"{_video_thumbnail(story)}<h3>{escape(story.title)}</h3>"
        f"<p>{escape(getattr(story, 'author', 'HAHA 文化记录者'))} · "
        f"{escape(getattr(story, 'region', '中国'))}</p></article>",
        unsafe_allow_html=True,
    )


def _video_thumbnail(story, *, featured: bool = False) -> str:
    cover = story.cover_markup
    if featured:
        cover = cover.replace('class="cover ', 'class="cover featured-cover ', 1)
    overlay = (
        '<div class="video-overlay"><span>'
        f"▶ {escape(getattr(story, 'views', '1.2万'))}　"
        f"♡ {escape(getattr(story, 'interactions', '326'))}</span>"
        f'<b>{escape(story.duration)}</b></div><div class="play-mark">▶</div>'
    )
    return cover.replace("</div>", f"{overlay}</div>", 1)


def _render_region_discovery() -> None:
    st.markdown(
        '<div class="section-title"><h2>按地区发现非遗</h2>'
        '<a href="?module=media">进入文化地图 ></a></div>',
        unsafe_allow_html=True,
    )
    regions = (
        ("云南", "扎染与民族纹样", "24 个项目"),
        ("贵州", "苗绣与银饰", "19 个项目"),
        ("四川", "竹编与蜀绣", "27 个项目"),
        ("浙江", "木作与织造", "31 个项目"),
        ("福建", "漆艺与传统建筑", "22 个项目"),
    )
    columns = st.columns(5, gap="medium")
    for column, (name, craft, count) in zip(columns, regions, strict=True):
        with column:
            st.markdown(
                f'<article class="region-card"><span>{escape(count)}</span>'
                f"<h3>{escape(name)}</h3><p>{escape(craft)}</p></article>",
                unsafe_allow_html=True,
            )


def _render_special_topics() -> None:
    st.markdown(
        '<div class="section-title"><h2>专题策展</h2><a href="?module=media">查看全部 ></a></div>',
        unsafe_allow_html=True,
    )
    topics = (
        ("中国蓝染地图", "从植物染料到地方生活", "indigo"),
        ("100 位年轻传承人", "传统技艺的新一代表达", "vermilion"),
        ("从泥土到瓷器", "跟随火候看见时间", "earth"),
    )
    columns = st.columns(3, gap="large")
    for column, (title, copy, tone) in zip(columns, topics, strict=True):
        with column:
            st.markdown(
                f'<article class="topic-card {tone}"><span>HAHA CURATION</span>'
                f"<h3>{escape(title)}</h3><p>{escape(copy)}</p></article>",
                unsafe_allow_html=True,
            )


def _render_ai_learning() -> None:
    st.markdown('<div class="section-title"><h2>跟 AI 学非遗</h2></div>', unsafe_allow_html=True)
    tools = (
        ("问 AI", "苗绣和苏绣有什么区别？", "问一个文化问题"),
        ("学习专题", "5 分钟认识蓝染", "从一条学习路径开始"),
        ("AI 识图", "拍一件器物，看看它可能来自哪里", "识别结果仅作探索提示"),
    )
    columns = st.columns(3, gap="large")
    for column, (title, example, note) in zip(columns, tools, strict=True):
        with column:
            st.markdown(
                '<article class="ai-tool"><span>AI CULTURE TOOL</span>'
                f"<h3>{escape(title)}</h3><strong>{escape(example)}</strong>"
                f"<p>{escape(note)}</p></article>",
                unsafe_allow_html=True,
            )
    st.markdown(
        '<footer class="site-footer"><strong>HAHA 飞颐</strong>'
        "<span>让非遗被看见、被理解、被继续创造。</span>"
        "<small>比赛 MVP · 演示内容</small></footer>",
        unsafe_allow_html=True,
    )


def _filter_stories(category: str, search: str) -> tuple:
    if category in {"首页", "热门"}:
        filtered = STORIES
    else:
        keyword_by_category = {
            "刺绣": ("刺绣", "人物"),
            "蓝染": ("织染", "纹样"),
            "陶艺": ("陶艺", "工序"),
            "木雕": ("木作", "手艺人"),
            "剪纸": ("纸艺", "纹样"),
            "戏曲": ("人物", "文化"),
            "民俗": ("文化", "民俗"),
            "传统工艺": ("手艺人", "工序"),
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
