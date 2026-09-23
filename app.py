"""Clean-slate HAHA cultural media MVP."""

from __future__ import annotations

import sys
from html import escape
from pathlib import Path

# Keep the local ``src`` package importable when Streamlit launches this file
# directly (including desktop preview sessions that do not set PYTHONPATH).
SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import streamlit as st  # noqa: E402
import streamlit.components.v1 as components  # noqa: E402

from haha_media.feed import STORIES  # noqa: E402
from haha_media.script_writer import (  # noqa: E402
    ContentBrief,
    ContentScript,
    generate_content_script,
)
from haha_media.theme import apply_theme  # noqa: E402

CATEGORY_LABELS = {
    "all": "首页",
    "hot": "热门",
    "embroidery": "刺绣",
    "textile": "染织",
    "ceramics": "陶瓷",
    "woodcraft": "木作",
    "bamboo": "竹编",
    "papercut": "剪纸",
    "opera": "戏曲",
    "folk-custom": "民俗",
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
    elif module == "map":
        _render_culture_map()
    else:
        _render_module_placeholder(module)


def _render_navigation_system(module: str, channel: str) -> None:
    def page_link(key: str, label: str) -> str:
        current = ' class="active" aria-current="page"' if module == key else ""
        return f'<a{current} href="?module={key}">{label}</a>'

    def channel_link(key: str, label: str, *, icon: str = "") -> str:
        current = ' class="active" aria-current="page"' if channel == key else ""
        return f'<a{current} href="?module=media&channel={key}">{icon}{label}</a>'

    home_channels = tuple(CATEGORY_LABELS.items())[2:]
    channel_markup = "".join(channel_link(key, label) for key, label in home_channels)
    st.markdown(
        '<header class="header-system">'
        '<div class="global-header">'
        '<a class="header-brand" href="?module=media">HAHA</a>'
        '<nav class="global-links" aria-label="全局导航">'
        f'{page_link("media", "首页")}<a href="?module=media">非遗影像</a>'
        f"{page_link('gift', '非遗礼遇')}"
        f"{page_link('learn', 'AI 学习')}</nav>"
        '<form class="header-search" method="get"><input type="hidden" name="module" value="media">'
        '<input name="q" aria-label="搜索视频、非遗项目、传承人或地区" '
        'placeholder="搜一搜：竹编、蓝染、手艺人的一天"><button type="submit">⌕</button></form>'
        '<nav class="user-links" aria-label="用户功能"><span>消息</span><span>收藏</span>'
        '<span>历史</span><a href="?module=profile">用户</a></nav>'
        '<nav class="creator-actions" aria-label="创作功能">'
        '<a class="script-button" href="?space=script">AI 脚本</a>'
        '<a class="publish-button" href="?space=publish">＋ 投稿</a></nav></div>'
        '<div class="header-visual" aria-label="HAHA 非遗影像品牌视觉">'
        '<div class="visual-brand"><b>HAHA</b><span>HERITAGE IN MOTION</span></div>'
        '<div class="visual-copy"><strong>让手艺被看见，让故事继续发生</strong>'
        "<span>非遗影像 · 文化故事 · 青年共创</span></div>"
        '<i class="visual-seal">哈</i></div>'
        '<div class="channel-nav"><nav class="channel-featured" aria-label="推荐频道">'
        f"{channel_link('all', '动态', icon='◎ ')}{channel_link('hot', '热门', icon='🔥 ')}"
        '</nav><nav class="channel-grid" aria-label="内容频道">'
        f"{channel_markup}"
        '<details class="more-menu"><summary aria-label="展开更多非遗分类">更多⌄</summary>'
        '<div class="mega-menu"><section><strong>传统美术</strong><a href="?module=media&channel=embroidery">刺绣</a>'
        '<a href="?module=media&channel=papercut">剪纸</a><span>年画</span><span>雕刻</span><span>漆艺</span></section>'
        '<section><strong>传统技艺</strong><a href="?module=media&channel=textile">染织</a>'
        '<a href="?module=media&channel=ceramics">陶瓷</a><a href="?module=media&channel=woodcraft">木作</a>'
        '<a href="?module=media&channel=bamboo">竹编</a><span>金工</span><span>制茶</span></section>'
        '<section><strong>传统表演</strong><a href="?module=media&channel=opera">戏曲</a><span>曲艺</span>'
        "<span>传统音乐</span><span>传统舞蹈</span><span>杂技</span></section>"
        '<section><strong>民俗生活</strong><a href="?module=media&channel=folk-custom">民俗</a>'
        "<span>节庆</span><span>礼俗</span><span>饮食技艺</span><span>服饰</span><span>传统医药</span>"
        '</section></div></details></nav><nav class="channel-utilities" aria-label="社区服务">'
        '<a href="?module=media">▤ 专栏</a><a href="?module=media">⚑ 活动</a>'
        '<a href="?module=map">▣ 文化地图</a><a href="?module=media">▶ 直播</a>'
        '<a href="?module=learn">✦ 课堂</a><a href="?module=media&channel=hot">♪ 非遗热榜</a>'
        "</nav></div></header>",
        unsafe_allow_html=True,
    )
    _install_scroll_navigation()


def _install_scroll_navigation() -> None:
    components.html(
        """
        <script>
        (() => {
          const host = window.parent;
          const doc = host.document;
          if (host.__hahaNavCleanup) host.__hahaNavCleanup();
          const scroller = doc.querySelector('[data-testid="stMain"]');
          const header = doc.querySelector('.header-system');
          if (!scroller || !header) return;
          let compact = scroller.scrollTop > 120;
          const render = () => {
            const y = scroller.scrollTop;
            if (!compact && y > 120) compact = true;
            if (compact && y < 60) compact = false;
            header.classList.toggle('is-scrolled', compact);
          };
          scroller.addEventListener('scroll', render, {passive: true});
          render();
          host.__hahaNavCleanup = () => scroller.removeEventListener('scroll', render);
        })();
        </script>
        """,
        height=0,
        scrolling=False,
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


def _render_culture_map() -> None:
    region = str(st.query_params.get("region", "all"))
    regions = {
        "all": "全国",
        "yunnan": "云南",
        "guizhou": "贵州",
        "sichuan": "四川",
        "zhejiang": "浙江",
        "jiangsu": "江苏",
        "fujian": "福建",
        "guangdong": "广东",
        "xinjiang": "新疆",
    }
    region_links = "".join(
        f'<a class="{"active" if key == region else ""}" href="?module=map&region={key}">{label}</a>'
        for key, label in regions.items()
    )
    st.markdown("## 文化地图")
    st.caption("先选择一个地方，再发现当地的手艺、表演与生活传统。")
    st.markdown(
        f'<nav class="filter-row region-first"><b>地域</b>{region_links}</nav>'
        '<nav class="filter-row"><b>内容类型</b><span>刺绣</span><span>染织</span>'
        "<span>陶瓷</span><span>木作</span><span>竹编</span><span>戏曲</span><span>民俗</span></nav>",
        unsafe_allow_html=True,
    )
    _render_region_discovery()


def render_media_home() -> None:
    _render_community_feed()


def _navigate(space: str) -> None:
    st.query_params["space"] = space
    st.rerun()


def _render_creator_route(space: str) -> None:
    if space == "script":
        _render_script_workspace_shell()
        return
    sidebar, workspace = st.columns((0.5, 2.7), gap="large")
    with sidebar:
        st.markdown(
            '<aside class="creator-sidebar"><div class="creator-logo">HAHA <span>创作中心</span></div>'
            "<strong>✦　创作工作台</strong><span>▤　内容管理</span><span>⌁　数据中心</span>"
            "<span>◌　互动管理</span><span>◇　文化审核</span></aside>",
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
            '<div class="project-status"><span>● 已自动保存</span><b>未命名项目</b><button>•••</button></div></div>',
            unsafe_allow_html=True,
        )
        _render_video_publisher()


def _render_script_workspace_shell() -> None:
    stage = str(st.session_state.get("creator_stage", "settings"))
    stage_order = {"settings": 1, "judgment": 2, "master": 3, "storyboard": 4, "publish": 5, "audit": 6}
    requested_stage = str(st.query_params.get("stage", ""))
    if requested_stage in stage_order and stage_order[requested_stage] <= stage_order.get(stage, 1):
        stage = requested_stage
        st.session_state["creator_stage"] = stage
    st.markdown(
        '<header class="script-app-header"><div class="script-topbar">'
        '<details class="drawer-menu"><summary aria-label="打开导航菜单">☰</summary>'
        '<div class="drawer-scrim"></div><div class="drawer-panel"><div class="drawer-brand">HAHA<span>创作中心</span></div>'
        '<a class="active" href="?space=script">✦ 创作工作台</a><a>▤ 内容管理</a>'
        '<a>⌁ 数据中心</a><a>◌ 互动管理</a><a>◇ 文化审核</a><div class="drawer-divider"></div>'
        '<a href="?space=community">← 返回社区</a><a href="?space=publish">视频投稿</a>'
        '<a class="primary" href="?space=script">图文脚本</a></div></details>'
        '<div class="script-header-brand"><b>HAHA 创作中心</b><span>人工智能创意工作室 · V2.0</span></div>'
        '<div class="project-status"><span><i></i>已自动保存</span><b>未命名项目</b>'
        '<button aria-label="更多项目操作">•••</button></div></div>'
        '<div class="script-header-copy"><h1>把一个想法变成可拍、可审、可发布的内容</h1>'
        "<p>事实库 × 创作方法库 × 运营策略库</p></div></header>",
        unsafe_allow_html=True,
    )
    _render_creator_steps(stage)
    _render_script_creator_horizontal()


def _render_script_creator_horizontal() -> None:
    script = st.session_state.get("generated_script")
    canvas, review = st.columns((1, 0.38), gap="large")
    with canvas:
        st.markdown(
            '<div class="studio-column-title workspace-marker"><b><i>02</i>AI 创作工作区</b>'
            "<span>从创作判断开始，逐步完成脚本、分镜与发布适配。</span></div>",
            unsafe_allow_html=True,
        )
        if isinstance(script, ContentScript):
            _render_script(script)
        else:
            st.markdown(
                '<div class="studio-empty"><div class="weave-icon">✦</div><b>从一个想法开始</b>'
                "<span>完成下方创作设定后，AI 会先分析内容方向，再生成完整创作方案。</span>"
                '<div class="ability-grid"><em>◇<b>创作判断</b></em><em>⌁<b>结构规划</b></em>'
                "<em>▦<b>分镜生成</b></em><em>↗<b>发布适配</b></em></div></div>",
                unsafe_allow_html=True,
            )
    with review:
        st.markdown(
            '<div class="studio-column-title review-marker"><b><i>03</i>判断与审核</b>'
            "<span>核对事实来源、文化风险与平台适配度。</span></div>",
            unsafe_allow_html=True,
        )
        _render_review_panel(script if isinstance(script, ContentScript) else None)

    st.markdown(
        '<div class="settings-console-head settings-console-marker"><b><i>01</i>创作设定</b>'
        "<span>定义这次内容要讲什么、讲给谁、用什么规格生成。</span></div>",
        unsafe_allow_html=True,
    )
    with st.form("script_creator_horizontal", border=False):
        core, audience_panel, spec_panel, style_panel = st.columns(4, gap="large")
        with core:
            st.markdown('<div class="form-group-title">A · 创作核心</div>', unsafe_allow_html=True)
            craft = st.text_input("创作主题", placeholder="白族扎染、龙泉青瓷、竹编或某位传承人")
            story_seed = st.text_area(
                "想讲的一个瞬间", placeholder="师傅把刚染好的布从染缸里缓慢提起。", height=104
            )
        with audience_panel:
            st.markdown(
                '<div class="form-group-title">B · 受众与平台</div>', unsafe_allow_html=True
            )
            goals = st.multiselect(
                "内容目标（最多两项）",
                (
                    "文化科普",
                    "人物故事",
                    "工艺展示",
                    "情绪表达",
                    "活动宣传",
                    "商品故事",
                    "引流涨粉",
                    "收藏型内容",
                ),
                default=("文化科普",),
                max_selections=2,
            )
            audience = st.selectbox(
                "目标受众",
                (
                    "第一次接触非遗的人",
                    "年轻学生",
                    "传统文化爱好者",
                    "手作爱好者",
                    "旅游人群",
                    "亲子家庭",
                    "设计师 / 创作者",
                    "海外中国文化兴趣用户",
                ),
            )
            platform = st.selectbox(
                "发布平台", ("抖音", "小红书", "B站", "视频号", "TikTok"), index=1
            )
        with spec_panel:
            st.markdown('<div class="form-group-title">C · 成片规格</div>', unsafe_allow_html=True)
            spec_a, spec_b = st.columns(2)
            duration = spec_a.selectbox(
                "成片时长", ("15秒", "30秒", "45秒", "60秒", "90秒"), index=2
            )
            aspect = spec_b.selectbox("画幅", ("9:16", "16:9", "1:1", "3:4"))
            content_count = st.selectbox("内容数量", ("单条内容", "3条系列", "5条系列"))
        with style_panel:
            st.markdown(
                '<div class="form-group-title">D · 风格与生成</div>', unsafe_allow_html=True
            )
            tone = st.selectbox(
                "表达气质",
                (
                    "安静观察",
                    "纪录片",
                    "年轻轻快",
                    "人物纪实",
                    "诗意东方",
                    "工艺满足感",
                    "悬念探索",
                    "知识科普",
                    "温暖治愈",
                    "真实粗粝",
                ),
            )
            fact_level = st.select_slider(
                "事实严格度", ("创意优先", "平衡", "严格考据"), value="平衡"
            )
            model_tier = st.radio("生成模式", ("快速", "标准", "精创"), index=1, horizontal=True)
            generated = st.form_submit_button("✦ 生成本次创作判断", type="primary", width="stretch")
    if generated:
        try:
            st.session_state["generated_script"] = generate_content_script(
                ContentBrief(
                    craft,
                    story_seed,
                    audience,
                    platform,
                    tone,
                    " + ".join(goals) or "文化科普",
                    duration,
                    aspect,
                    content_count,
                    fact_level,
                    model_tier,
                )
            )
            st.session_state["creator_stage"] = "judgment"
            st.rerun()
        except ValueError as exc:
            st.warning(str(exc))


def _render_community_feed() -> None:
    category_key = str(st.query_params.get("channel", "all"))
    search = str(st.query_params.get("q", ""))
    if category_key != "all" or search.strip():
        category = CATEGORY_LABELS.get(category_key, "首页")
        st.markdown(f"## {category if not search.strip() else '搜索结果'}")
        if category_key not in {"all", "hot"}:
            _render_channel_filters(category_key)
        _render_card_row(_filter_stories(category, search), prefix="filtered")
        return
    _render_daily_feature()
    _render_channel_section("🔥 正在热门", STORIES, "hot")
    _render_channel_section("刺绣 · 一针一线里的故事", STORIES, "embroidery")
    _render_channel_section("陶瓷 · 泥土与火的相遇", tuple(reversed(STORIES)), "ceramics")
    _render_region_discovery()
    _render_special_topics()
    _render_ai_learning()
    _render_published_posts()
    if response := st.session_state.get("media_response"):
        st.markdown("### HAHA 正在为你展开")
        st.info(response)


def _render_channel_filters(channel: str) -> None:
    selected = {
        "region": str(st.query_params.get("region", "all")),
        "content": str(st.query_params.get("content", "all")),
        "level": str(st.query_params.get("level", "all")),
    }

    def links(name: str, options: tuple[tuple[str, str], ...]) -> str:
        return "".join(
            f'<a class="{"active" if key == selected[name] else ""}" '
            f'href="?module=media&channel={channel}&{name}={key}">{label}</a>'
            for key, label in options
        )

    region_links = links(
        "region",
        (
            ("all", "全国"),
            ("jiangsu", "江苏"),
            ("zhejiang", "浙江"),
            ("hunan", "湖南"),
            ("guizhou", "贵州"),
            ("yunnan", "云南"),
            ("sichuan", "四川"),
            ("more", "更多"),
        ),
    )
    content_links = links(
        "content",
        (
            ("all", "全部"),
            ("video", "视频"),
            ("project", "项目"),
            ("inheritor", "传承人"),
            ("topic", "专题"),
        ),
    )
    level_links = links(
        "level",
        (("all", "全部"), ("national", "国家级"), ("provincial", "省级"), ("city", "市级")),
    )
    st.markdown(
        f'<section class="channel-filters"><div><b>地域</b>{region_links}</div>'
        f"<div><b>内容</b>{content_links}</div><div><b>级别</b>{level_links}</div></section>",
        unsafe_allow_html=True,
    )


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
    st.markdown(
        '<section class="creator-head studio-v2-head"><div class="studio-kicker">人工智能创意工作室 · V2.0</div>'
        '<div class="studio-title">把一个想法变成可拍、可审、可发布的内容</div>'
        '<div class="studio-description">事实库 × 创作方法库 × 运营策略库</div></section>',
        unsafe_allow_html=True,
    )
    _render_creator_steps(str(st.session_state.get("creator_stage", "settings")))
    settings, canvas, review = st.columns((0.9, 1.9, 0.9), gap="medium")
    with settings:
        st.markdown(
            '<div class="studio-column-title settings-marker"><b><i>01</i>创作设定</b>'
            "<span>定义这次内容要讲什么、讲给谁、在哪里发布。</span></div>",
            unsafe_allow_html=True,
        )
        with st.form("script_creator", border=False):
            st.markdown('<div class="form-group-title">A · 创作核心</div>', unsafe_allow_html=True)
            craft = st.text_input("创作主题", placeholder="白族扎染、龙泉青瓷、竹编或某位传承人")
            story_seed = st.text_area(
                "想讲的一个瞬间", placeholder="师傅把刚染好的布从染缸里缓慢提起。", height=110
            )
            goals = st.multiselect(
                "内容目标（最多两项）",
                (
                    "文化科普",
                    "人物故事",
                    "工艺展示",
                    "情绪表达",
                    "活动宣传",
                    "商品故事",
                    "引流涨粉",
                    "收藏型内容",
                ),
                default=("文化科普",),
                max_selections=2,
            )
            st.markdown(
                '<div class="form-group-title">B · 受众与平台</div>', unsafe_allow_html=True
            )
            audience = st.selectbox(
                "目标受众",
                (
                    "第一次接触非遗的人",
                    "年轻学生",
                    "传统文化爱好者",
                    "手作爱好者",
                    "旅游人群",
                    "亲子家庭",
                    "设计师 / 创作者",
                    "海外中国文化兴趣用户",
                ),
            )
            platform = st.selectbox(
                "发布平台", ("抖音", "小红书", "B站", "视频号", "TikTok"), index=1
            )
            st.markdown('<div class="form-group-title">C · 成片规格</div>', unsafe_allow_html=True)
            spec_a, spec_b = st.columns(2)
            duration = spec_a.selectbox(
                "成片时长", ("15秒", "30秒", "45秒", "60秒", "90秒"), index=2
            )
            aspect = spec_b.selectbox("画幅", ("9:16", "16:9", "1:1", "3:4"))
            content_count = st.selectbox("内容数量", ("单条内容", "3条系列", "5条系列"))
            st.markdown(
                '<div class="form-group-title">D · 风格与生成</div>', unsafe_allow_html=True
            )
            tone = st.selectbox(
                "表达气质",
                (
                    "安静观察",
                    "纪录片",
                    "年轻轻快",
                    "人物纪实",
                    "诗意东方",
                    "工艺满足感",
                    "悬念探索",
                    "知识科普",
                    "温暖治愈",
                    "真实粗粝",
                ),
            )
            fact_level = st.select_slider(
                "事实严格度", ("创意优先", "平衡", "严格考据"), value="平衡"
            )
            model_tier = st.radio("生成模式", ("快速", "标准", "精创"), index=1, horizontal=True)
            generated = st.form_submit_button("✦ 生成本次创作判断", type="primary", width="stretch")
    if generated:
        try:
            with st.status("正在理解你的创意……", expanded=True) as progress:
                progress.write("✓ 正在查找相关非遗资料")
                progress.write("✓ 正在匹配创作方法")
                progress.write("✓ 正在匹配平台运营策略")
                st.session_state["generated_script"] = generate_content_script(
                    ContentBrief(
                        craft,
                        story_seed,
                        audience,
                        platform,
                        tone,
                        " + ".join(goals) or "文化科普",
                        duration,
                        aspect,
                        content_count,
                        fact_level,
                        model_tier,
                    )
                )
                progress.write("✓ 正在设计内容结构并进行文化核验")
                progress.update(label="创作判断已完成", state="complete", expanded=False)
            st.session_state["creator_stage"] = "judgment"
        except ValueError as exc:
            st.warning(str(exc))
    script = st.session_state.get("generated_script")
    with canvas:
        st.markdown(
            '<div class="studio-column-title workspace-marker"><b><i>02</i>AI 创作工作区</b>'
            "<span>从创作判断开始，逐步完成脚本、分镜与发布适配。</span></div>",
            unsafe_allow_html=True,
        )
        if isinstance(script, ContentScript):
            _render_script(script)
        else:
            st.markdown(
                '<div class="studio-empty"><div class="weave-icon">✦</div><b>从一个想法开始</b>'
                "<span>完成左侧设定后，AI 会先分析内容方向，再生成完整创作方案。</span>"
                '<div class="ability-grid"><em>◇<b>创作判断</b></em><em>⌁<b>结构规划</b></em>'
                "<em>▦<b>分镜生成</b></em><em>↗<b>发布适配</b></em></div></div>",
                unsafe_allow_html=True,
            )
    with review:
        st.markdown(
            '<div class="studio-column-title review-marker"><b><i>03</i>判断与审核</b>'
            "<span>核对事实来源、文化风险与平台适配度。</span></div>",
            unsafe_allow_html=True,
        )
        _render_review_panel(script if isinstance(script, ContentScript) else None)


def _render_creator_steps(stage: str) -> None:
    current = {
        "settings": 1,
        "judgment": 2,
        "master": 3,
        "storyboard": 4,
        "publish": 5,
        "audit": 6,
        "script": 6,
    }.get(stage, 1)
    steps = (
        (1, "settings", "创作设定"),
        (2, "judgment", "创作判断"),
        (3, "master", "主脚本"),
        (4, "storyboard", "结构化分镜"),
        (5, "publish", "发布包"),
        (6, "audit", "文化审核"),
    )
    markup = "".join(
        f'<a class="step-node {"done" if number < current else "active" if number == current else "pending"}" '
        f'{f"href=?space=script&amp;stage={key}" if number < current else "aria-disabled=true"}>'
        f'<i>{"✓" if number < current else f"{number:02d}"}</i><b>{number:02d} {label}</b></a>'
        for number, key, label in steps
    )
    st.markdown(
        f'<nav class="creator-steps" aria-label="创作流程">{markup}</nav>',
        unsafe_allow_html=True,
    )


def _render_script(script: ContentScript) -> None:
    stage = st.session_state.get("creator_stage", "judgment")
    st.markdown("### 本次创作判断")
    st.markdown(
        '<div class="judgment-grid">'
        + "".join(
            f"<div><span>{escape(label)}</span><b>{escape(value)}</b></div>"
            for label, value in script.judgment
        )
        + "</div>",
        unsafe_allow_html=True,
    )
    if stage == "judgment":
        confirm, reset = st.columns(2)
        if confirm.button("确认并生成完整脚本", type="primary", width="stretch"):
            st.session_state["creator_stage"] = "script"
            st.rerun()
        if reset.button("修改设定 / 重新判断", width="stretch"):
            st.session_state.pop("generated_script", None)
            st.rerun()
        return

    st.markdown(
        '<section class="studio-result-card"><h3>内容结构</h3><div class="story-arc">'
        "<span><b>01 Hook</b><small>0–3 秒</small></span><span><b>02 建立情境</b><small>3–10 秒</small></span>"
        "<span><b>03 工艺过程</b><small>10–28 秒</small></span><span><b>04 文化信息</b><small>28–38 秒</small></span>"
        "<span><b>05 情绪收尾</b><small>38–45 秒</small></span></div></section>",
        unsafe_allow_html=True,
    )
    st.markdown("**快速调整**")
    st.markdown(
        '<div class="rewrite-chips"><button>更短一点</button><button>更有故事感</button>'
        "<button>更年轻</button><button>更克制</button><button>更知识型</button>"
        "<button>加强前三秒</button><button>减少旁白</button><button>增加画面表现</button>"
        "<button>改成抖音版</button><button>改成小红书版</button><button>改成 B 站版</button>"
        "<button>改成视频号版</button></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<section class="studio-result-card"><div class="result-card-head"><h3>Master Script</h3><span>复制　编辑　重新生成</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(f"#### {script.title}")
    st.info(f"前 3 秒 Hook：{script.hook}")
    master_html = "<br>".join(escape(line) for line in script.voiceover)
    st.markdown(
        f'<div class="rich-script" contenteditable="true"><b>一句话主题</b><p>让观众从一个真实动作进入手艺的过程与人物状态。</p>'
        f"<b>正文</b><p>{master_html}</p><b>结尾</b><p>你还想继续了解哪一步？</p></div></section>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="zone-note"><b>FACT ZONE</b> 历史、地域、级别和人物必须有来源。<br><b>CREATIVE ZONE</b> 镜头、节奏、情绪与比喻允许创意表达。</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<section class="studio-result-card"><div class="result-card-head"><h3>结构化分镜</h3><span>表格视图　卡片视图　复制　导出</span></div>',
        unsafe_allow_html=True,
    )
    headers = (
        "镜号",
        "时间",
        "场景",
        "景别",
        "镜头运动",
        "画面描述",
        "人物情绪",
        "旁白/字幕",
        "声音",
        "素材",
        "事实来源",
    )
    st.data_editor(
        [dict(zip(headers, row, strict=True)) for row in script.storyboard],
        hide_index=True,
        width="stretch",
    )
    st.markdown("</section>", unsafe_allow_html=True)
    st.markdown('<section class="studio-result-card"><h3>发布包</h3>', unsafe_allow_html=True)
    st.markdown("**标题建议**")
    for number, item in enumerate(script.titles, start=1):
        st.write(f"{number:02d}　{item}")
    st.markdown("**封面文案**")
    st.write("　/　".join(script.covers))
    st.markdown("**发布简介**")
    st.text_area(
        "发布简介（可编辑）", value=script.caption, height=140, label_visibility="collapsed"
    )
    st.markdown("**标签**")
    st.code(" ".join(script.tags), language=None)
    st.markdown("</section>", unsafe_allow_html=True)
    save, export_col, continue_make, publish = st.columns(4)
    if save.button("保存草稿", width="stretch"):
        projects = st.session_state.setdefault("creator_projects", [])
        projects.append(script)
        st.success("项目已保存到本次会话。")
    export_col.download_button(
        "导出脚本",
        data=f"{script.title}\n\n" + "\n".join(script.voiceover),
        file_name="HAHA-Master-Script.txt",
        mime="text/plain",
        width="stretch",
    )
    continue_make.button("继续制作", width="stretch")
    if publish.button("进入视频投稿", type="primary", width="stretch"):
        _navigate("publish")


def _render_review_panel(script: ContentScript | None) -> None:
    if script is None:
        st.markdown(
            '<section class="run-evidence idle"><div class="run-evidence-head">'
            '<span><i></i>RUN 未运行</span><b>等待生成</b></div>'
            '<p>点击“生成本次创作判断”后，这里会显示双知识库的真实检索记录。</p></section>'
            '<div class="review-empty"><span>生成后将在这里显示</span>'
            "<div>◇ <b>方法依据</b><small>创作方法知识库</small></div>"
            "<div>↗ <b>策略依据</b><small>运营策略知识库</small></div>"
            "<div>⚠ <b>待事实核验</b><small>当前未接入事实知识库</small></div>"
            "<div>◆ <b>运营建议</b><small>平台与内容判断</small></div></div>",
            unsafe_allow_html=True,
        )
        return
    _render_run_evidence(script)
    st.markdown(f"#### 方法依据 · {len(script.method_sources)} 条")
    for chunk_id, title in script.method_sources:
        st.markdown(
            f'<div class="source-item"><b>[{escape(chunk_id)}]</b> {escape(title)}</div>',
            unsafe_allow_html=True,
        )
    st.markdown(f"#### 策略依据 · {len(script.strategy_sources)} 条")
    for chunk_id, title in script.strategy_sources:
        st.markdown(
            f'<div class="source-item"><b>[{escape(chunk_id)}]</b> {escape(title)}</div>',
            unsafe_allow_html=True,
        )
    st.markdown("#### 待事实核验")
    st.caption("当前未接入非遗事实知识库，以下内容不得作为确定事实直接发布。")
    for item in script.fact_checks:
        st.markdown(
            f'<div class="audit-item risk"><b>待核验</b><span>{escape(item)}</span></div>',
            unsafe_allow_html=True,
        )
    st.markdown("#### 运营建议")
    st.markdown(
        '<div class="operation-grid">'
        + "".join(
            f"<span>{escape(label)}<b>{escape(value)}</b></span>"
            for label, value in script.operation_scores
        )
        + "</div>",
        unsafe_allow_html=True,
    )
    st.info("建议先展示关键动作，再进入文化背景，避免前三秒信息量过大。")


def _render_run_evidence(script: ContentScript) -> None:
    trace = script.retrieval_trace
    if trace is None:
        st.error("本次生成没有检索证据，请勿将结果视为已调用知识库。")
        return
    score_lookup = dict(trace.rerank_scores)
    method_rows = "".join(
        f'<li><b>{escape(chunk_id)}</b><span>{escape(title)}</span>'
        f'<em>{score_lookup.get(chunk_id, 0):.3f}</em></li>'
        for chunk_id, title in script.method_sources
    )
    strategy_rows = "".join(
        f'<li><b>{escape(chunk_id)}</b><span>{escape(title)}</span>'
        f'<em>{score_lookup.get(chunk_id, 0):.3f}</em></li>'
        for chunk_id, title in script.strategy_sources
    )
    st.markdown(
        '<section class="run-evidence verified">'
        '<div class="run-evidence-head"><span><i></i>RUN 已验证</span><b>双库调用成功</b></div>'
        '<div class="run-evidence-stats">'
        f'<span><b>{len(script.method_sources)}</b>方法命中</span>'
        f'<span><b>{len(script.strategy_sources)}</b>策略命中</span>'
        '<span><b>2</b>独立查询</span></div>'
        f'<dl><dt>Run ID</dt><dd>{escape(trace.generation_id)}</dd>'
        f'<dt>知识版本</dt><dd>{escape(trace.document_version)}</dd>'
        f'<dt>运行时间</dt><dd>{escape(trace.created_at)}</dd></dl>'
        '<div class="run-query"><b>Creative Query</b>'
        f'<p>{escape(trace.creative_query)}</p></div>'
        '<div class="run-query"><b>Operation Query</b>'
        f'<p>{escape(trace.operation_query)}</p></div>'
        '<div class="run-hit-group"><b>创作方法库命中与 Rerank 分</b>'
        f'<ul>{method_rows}</ul></div>'
        '<div class="run-hit-group"><b>运营策略库命中与 Rerank 分</b>'
        f'<ul>{strategy_rows}</ul></div>'
        '<footer>来源：HAHA飞颐项目营销端总材料包(1).docx · 两库独立检索</footer>'
        "</section>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
