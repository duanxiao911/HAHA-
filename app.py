"""Clean-slate HAHA cultural media MVP."""

from __future__ import annotations

import os
import re
import sys
import time
import traceback
from dataclasses import replace
from html import escape
from pathlib import Path

# Keep the local ``src`` package importable when Streamlit launches this file
# directly (including desktop preview sessions that do not set PYTHONPATH).
SRC_DIR = Path(__file__).resolve().parent / "src"
SRC_PATH = str(SRC_DIR)
if SRC_PATH in sys.path:
    sys.path.remove(SRC_PATH)
sys.path.insert(0, SRC_PATH)

import streamlit as st  # noqa: E402
from streamlit.errors import StreamlitSecretNotFoundError  # noqa: E402

from haha_media.asset_context import build_asset_context, extract_asset  # noqa: E402
from haha_media.feed import STORIES  # noqa: E402
from haha_media.knowledge import load_heritage_facts  # noqa: E402
from haha_media.model_router import (  # noqa: E402
    DEFAULT_TEXT_MODEL_LABEL,
    TEXT_MODEL_OPTIONS,
    ModelCallError,
    get_model_router,
)
from haha_media.project_store import list_projects, load_project, save_project  # noqa: E402
from haha_media.script_writer import (  # noqa: E402
    ContentBrief,
    ContentScript,
    generate_content_script,
    generate_content_script_for_mode,
    generate_content_script_with_model,
)
from haha_media.theme import apply_theme  # noqa: E402

CREATOR_STATE_VERSION = "parameter-pipeline-v6"
CREATOR_STATE_KEYS = (
    "generated_script",
    "creator_messages",
    "creator_stage",
    "model_run_mode",
    "creator_model_status",
    "creator_model_status_choice",
    "creator_run_attempt",
    "creator_brief",
    "creator_assets",
    "creator_parameter_sync_pending",
    "creator_param_craft",
    "creator_param_story_seed",
    "creator_param_goals",
    "creator_param_audience",
    "creator_param_platform",
    "creator_param_duration",
    "creator_param_aspect",
    "creator_param_tone",
    "creator_asset_context",
    "creator_project_id",
    "creator_first_frames",
    "creator_image_evidence",
    "creator_parameter_feedback",
    "creator_submitted_parameters",
)

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
    _load_local_model_secrets()
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


def _load_local_model_secrets() -> None:
    """Load optional local Streamlit secrets without overriding process configuration."""
    for key in (
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_MODEL",
        "ARK_API_KEY",
        "SEEDREAM_BASE_URL",
        "SEEDREAM_MODEL",
        "MODEL_API_TIMEOUT",
    ):
        if os.getenv(key):
            continue
        try:
            value = st.secrets.get(key)
        except StreamlitSecretNotFoundError:
            return
        if value is not None and str(value).strip():
            os.environ[key] = str(value).strip()


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
    _install_scroll_state(
        selector=".header-system",
        class_name="is-scrolled",
        enter_at=120,
        exit_at=60,
        cleanup_name="__hahaNavCleanup",
    )


def _install_scroll_state(
    *, selector: str, class_name: str, enter_at: int, exit_at: int, cleanup_name: str
) -> None:
    """Keep sticky headers stable without injecting rerun-sensitive JavaScript.

    Streamlit owns the page DOM and may replace nodes after a slow model call. A
    script that retains references to those nodes can race React reconciliation
    and surface ``removeChild`` errors. Sticky positioning remains handled by the
    page stylesheet; compact-on-scroll is intentionally disabled until it can be
    implemented as a lifecycle-safe component.
    """
    del selector, class_name, enter_at, exit_at, cleanup_name


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
    stale_state = st.session_state.get("creator_state_version") != CREATOR_STATE_VERSION
    new_conversation = str(st.query_params.get("new", "")) == "1"
    if stale_state or new_conversation:
        for key in CREATOR_STATE_KEYS:
            st.session_state.pop(key, None)
        st.session_state["creator_state_version"] = CREATOR_STATE_VERSION
        if new_conversation:
            st.query_params.pop("new", None)
        st.rerun()
    requested_model = str(st.query_params.get("model", ""))
    model_from_query = {
        "local": "本地演示",
        "flash": "DeepSeek-V4.1-Flash",
        "pro": "DeepSeek-V4-Pro",
    }.get(requested_model)
    if model_from_query and "creator_model_choice" not in st.session_state:
        st.session_state["creator_model_choice"] = model_from_query
    stage = str(st.session_state.get("creator_stage", "settings"))
    stage_order = {"settings": 1, "judgment": 2, "master": 3, "storyboard": 4, "publish": 5, "audit": 6}
    requested_stage = str(st.query_params.get("stage", ""))
    if requested_stage in stage_order and stage_order[requested_stage] <= stage_order.get(stage, 1):
        stage = requested_stage
        st.session_state["creator_stage"] = stage
    asset_count = len(st.session_state.get("creator_assets", []) or [])
    model_router = get_model_router()
    model_choice = st.session_state.get("creator_model_choice", DEFAULT_TEXT_MODEL_LABEL)
    latest_attempt = st.session_state.get("creator_run_attempt")
    try:
        active_model_mode = model_router.resolve_text_mode(model_choice)
        model_status = None
        if isinstance(latest_attempt, dict) and latest_attempt.get("choice") == model_choice:
            model_status = latest_attempt.get("status_label")
        if model_status is None:
            model_status = (
                f"模型可用 · {model_router.resolve_text_model(model_choice)}"
                if active_model_mode == "deepseek"
                else "本地演示 · 未调用模型 API"
            )
    except ModelCallError:
        model_status = "DeepSeek 未配置密钥"
    st.markdown(
        '<header class="ai-workbench-header"><div class="workbench-brand">'
        '<details class="drawer-menu"><summary aria-label="打开导航菜单">☰</summary>'
        '<div class="drawer-scrim"></div><div class="drawer-panel"><div class="drawer-brand">HAHA<span>创作中心</span></div>'
        '<a class="active" href="?space=script">✦ 创作工作台</a><a>▤ 内容管理</a>'
        '<a>⌁ 数据中心</a><a>◌ 互动管理</a><a>◇ 文化审核</a><div class="drawer-divider"></div>'
        '<a href="?space=community">← 返回社区</a><a href="?space=publish">视频投稿</a>'
        '<a class="primary" href="?space=script">智能工作台</a></div></details>'
        '<div><b>HAHA AI创作台</b><span>智能对话工作台</span></div></div>'
        '<nav class="workbench-actions"><a href="?space=script&amp;new=1">＋ <i>新建对话</i><em>新建</em></a>'
        '<a href="?space=script&amp;history=1"><i>历史会话</i><em>历史</em></a>'
        '</nav>'
        f'<div class="workbench-meta"><span><i></i><strong>{escape(model_status)}</strong><em>{escape(model_status)}</em></span>'
        f'<b>知识库 <i>3</i></b><b>素材 <i>{asset_count}</i></b>'
        '<details class="compact-more"><summary>•••</summary><div><a href="?space=script&amp;new=1">新建对话</a>'
        '<a href="?space=script&amp;history=1">历史会话</a><span>知识库 3</span>'
        f'<span>素材 {asset_count}</span></div></details></div></header>',
        unsafe_allow_html=True,
    )
    _install_workbench_header_scroll()
    if str(st.query_params.get("history", "")) == "1":
        _render_conversation_history()
    _render_script_creator_horizontal()


def _install_workbench_header_scroll() -> None:
    _install_scroll_state(
        selector=".ai-workbench-header",
        class_name="is-compact",
        enter_at=96,
        exit_at=32,
        cleanup_name="__hahaWorkbenchHeaderCleanup",
    )


def _render_script_creator_horizontal() -> None:
    _sync_creator_parameter_state()
    script = st.session_state.get("generated_script")
    st.markdown('<div class="conversation-marker"></div>', unsafe_allow_html=True)
    messages = st.session_state.setdefault("creator_messages", [])
    main, inspector = st.columns((1, 0.36), gap="large")
    with inspector:
        st.markdown('<div class="inspector-marker"></div>', unsafe_allow_html=True)
        parameter_tab, asset_tab, run_tab = st.tabs(("创作参数", "素材资产", "知识与 Run"))
        with parameter_tab:
            generated, draft_brief = _render_compact_creator_settings(
                has_result=isinstance(script, ContentScript)
            )
        with asset_tab:
            st.markdown("#### 当前会话素材")
            assets = st.file_uploader(
                "拖拽或选择参考资料",
                type=("png", "jpg", "jpeg", "webp", "txt", "md", "pdf", "docx"),
                accept_multiple_files=True,
                key="creator_assets",
            )
            if assets:
                extracted_assets = [
                    extract_asset(asset.name, asset.getvalue()) for asset in assets
                ]
                st.session_state["creator_asset_context"] = build_asset_context(
                    extracted_assets
                )
                for asset in extracted_assets:
                    st.markdown(
                        f'<div class="asset-row"><b>{escape(asset.name)}</b>'
                        f'<span>{escape(asset.status)}</span></div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.session_state["creator_asset_context"] = ""
                st.markdown(
                    '<div class="asset-empty">尚未挂载素材<br><span>参考图、文档和脚本片段会进入当前对话上下文</span></div>',
                    unsafe_allow_html=True,
                )
        with run_tab:
            _render_review_panel(
                script if isinstance(script, ContentScript) else None,
                st.session_state.get("creator_run_attempt"),
            )

    with main:
        st.markdown('<div class="conversation-thread-marker"></div>', unsafe_allow_html=True)
        brief_state = st.session_state.get("creator_brief")
        if isinstance(brief_state, ContentBrief):
            summary = (
                f'<b>当前结果：{escape(brief_state.craft)}</b>'
                f'<span>平台 {escape(brief_state.platform)}</span>'
                f'<span>{escape(brief_state.goal)}</span>'
                f'<span>{escape(brief_state.duration)}</span>'
                f'<span>{escape(brief_state.aspect_ratio)}</span>'
                f'<span>{escape(brief_state.tone)}</span>'
                f'<span>{escape(brief_state.audience)}</span>'
            )
        else:
            summary = '<b>当前结果：尚未生成</b><span>请在右侧设置参数</span>'
        st.markdown(f'<div class="task-summary">{summary}</div>', unsafe_allow_html=True)

        if not messages and not isinstance(script, ContentScript):
            st.markdown(
                '<section class="conversation-empty"><h2>今天想创作什么？</h2>'
                '<p>可以直接输入，也可以从一个示例开始</p>'
                '<div><em>白族扎染科普</em><em>故事改成 45 秒视频</em>'
                '<em>生成分镜和首帧</em><em>参考图保持人物一致</em></div></section>',
                unsafe_allow_html=True,
            )

        for message in messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if isinstance(script, ContentScript):
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown("我已经结合非遗事实库、创作方法库和运营策略库完成了本轮内容方案。")
                _render_script(script)
                if st.session_state.get("creator_stage") != "judgment":
                    _render_visual_production_cards(script)

        asset_count = len(st.session_state.get("creator_assets", []) or [])
        context_brief = brief_state if isinstance(brief_state, ContentBrief) else draft_brief
        context_status = "当前结果参数" if isinstance(brief_state, ContentBrief) else "待应用参数"
        st.markdown('<div class="composer-marker"></div>', unsafe_allow_html=True)
        with st.container(border=True):
            model_option, context_space = st.columns((2, 6), gap="small")
            model_option.selectbox(
                "生成模型",
                (*TEXT_MODEL_OPTIONS.keys(), "本地演示"),
                key="creator_model_choice",
                label_visibility="collapsed",
                help="Flash 响应更快、成本更低；Pro 适合复杂策划。选择会直接控制本次 API 请求使用的模型。",
            )
            context_space.markdown(
                f'<div class="composer-context">{context_status}：非遗事实库 · 创作方法库 · 运营策略库 · '
                f'{escape(context_brief.platform)} · {escape(context_brief.duration)} · '
                f'{escape(context_brief.aspect_ratio)} · {escape(context_brief.tone)} · 素材 {asset_count}</div>',
                unsafe_allow_html=True,
            )
            prompt = st.chat_input("按右侧当前参数生成，或继续修改当前方案……")

    if generated:
        _run_creator_generation(draft_brief)
    if prompt:
        messages.append({"role": "user", "content": prompt})
        current_script = st.session_state.get("generated_script")
        if isinstance(current_script, ContentScript):
            _run_creator_revision(prompt)
        else:
            brief = _brief_from_conversation(prompt, base=draft_brief)
            _run_creator_generation(brief)
        st.rerun()


def _sync_creator_parameter_state() -> None:
    pending = st.session_state.pop("creator_parameter_sync_pending", None)
    current = pending if isinstance(pending, ContentBrief) else st.session_state.get("creator_brief")
    if not isinstance(current, ContentBrief):
        current = ContentBrief(
            "",
            "",
            "第一次接触非遗的人",
            "小红书",
            "安静观察",
        )
    defaults = {
        "creator_param_craft": current.craft,
        "creator_param_story_seed": current.story_seed,
        "creator_param_goals": current.goal.split(" + "),
        "creator_param_audience": current.audience,
        "creator_param_platform": current.platform,
        "creator_param_duration": current.duration,
        "creator_param_aspect": current.aspect_ratio,
        "creator_param_tone": current.tone,
    }
    for key, value in defaults.items():
        if pending is not None or key not in st.session_state:
            st.session_state[key] = value


def _capture_creator_parameter_submission() -> None:
    """Freeze the browser widget values before Streamlit starts the submit rerun."""
    st.session_state["creator_submitted_parameters"] = {
        "craft": str(st.session_state.get("creator_param_craft", "")),
        "story_seed": str(st.session_state.get("creator_param_story_seed", "")),
        "audience": str(st.session_state.get("creator_param_audience", "")),
        "platform": str(st.session_state.get("creator_param_platform", "")),
        "tone": str(st.session_state.get("creator_param_tone", "")),
        "goal": " + ".join(st.session_state.get("creator_param_goals", ())) or "文化科普",
        "duration": str(st.session_state.get("creator_param_duration", "")),
        "aspect_ratio": str(st.session_state.get("creator_param_aspect", "")),
    }


def _render_compact_creator_settings(*, has_result: bool) -> tuple[bool, ContentBrief]:
    st.caption(f"参数链路版本：{CREATOR_STATE_VERSION}")
    st.caption(
        "每次选择会立即同步；点击按钮时冻结当前参数，再检索知识库并调用模型。"
    )
    craft = st.text_input(
        "创作主题", placeholder="白族扎染、龙泉青瓷、竹编", key="creator_param_craft"
    )
    story_seed = st.text_area(
        "想讲的一个瞬间", height=84, key="creator_param_story_seed"
    )
    goals = st.multiselect(
        "内容目标",
        ("文化科普", "人物故事", "工艺展示", "情绪表达", "商品故事", "收藏型内容"),
        max_selections=2,
        key="creator_param_goals",
    )
    audience = st.selectbox(
        "目标受众",
        ("第一次接触非遗的人", "年轻学生", "传统文化爱好者", "手作爱好者", "海外中国文化兴趣用户"),
        key="creator_param_audience",
    )
    first, second = st.columns(2)
    platform = first.selectbox(
        "发布平台",
        ("抖音", "小红书", "B站", "视频号", "TikTok"),
        key="creator_param_platform",
    )
    duration = second.selectbox(
        "时长", ("15秒", "30秒", "45秒", "60秒", "90秒"), key="creator_param_duration"
    )
    aspect = first.selectbox(
        "画幅", ("9:16", "16:9", "1:1", "3:4"), key="creator_param_aspect"
    )
    tone = second.selectbox(
        "表达气质",
        ("安静观察", "纪录片", "年轻轻快", "人物纪实", "诗意东方", "工艺满足感"),
        key="creator_param_tone",
    )
    st.info(
        f"本次待提交：{platform} · {duration} · {aspect} · {tone}",
        icon=":material/tune:",
    )
    generated = st.button(
        "应用参数并重新生成" if has_result else "应用参数并生成创作判断",
        key="apply-creator-parameters",
        type="primary",
        width="stretch",
        on_click=_capture_creator_parameter_submission,
    )
    feedback = st.session_state.get("creator_parameter_feedback")
    if has_result and isinstance(feedback, dict):
        message = str(feedback.get("message", ""))
        if message:
            if feedback.get("status") == "success":
                st.success(message, icon="✅")
            else:
                st.error(message, icon="⚠️")
    submitted = st.session_state.get("creator_submitted_parameters") if generated else None
    draft = (
        ContentBrief(**submitted)
        if isinstance(submitted, dict)
        else ContentBrief(
            craft,
            story_seed,
            audience,
            platform,
            tone,
            " + ".join(goals) or "文化科普",
            duration,
            aspect,
        )
    )
    return generated, draft


def _brief_from_conversation(prompt: str, *, base: ContentBrief | None = None) -> ContentBrief:
    clean_prompt = prompt.strip()
    known_names = sorted(
        (fact.name for fact in load_heritage_facts() if fact.name in clean_prompt),
        key=len,
        reverse=True,
    )
    topic = known_names[0] if known_names else ((base.craft if base else "") or clean_prompt[:32])
    platform = next(
        (name for name in ("小红书", "抖音", "B站", "视频号", "TikTok") if name in clean_prompt),
        base.platform if base else "小红书",
    )
    duration_match = re.search(r"(15|30|45|60|90)\s*秒", clean_prompt)
    duration = (
        f"{duration_match.group(1)}秒"
        if duration_match
        else (base.duration if base else "45秒")
    )
    goal = next(
        (name for name in ("文化科普", "人物故事", "工艺展示", "情绪表达", "商品故事") if name in clean_prompt),
        base.goal if base else "文化科普",
    )
    return ContentBrief(
        topic,
        (base.story_seed if base and base.story_seed.strip() else clean_prompt),
        base.audience if base else "第一次接触非遗的人",
        platform,
        base.tone if base else "安静观察",
        goal,
        duration,
        base.aspect_ratio if base else "9:16",
        base.content_count if base else "单条内容",
        base.fact_level if base else "平衡",
        base.model_tier if base else "标准",
        asset_context=base.asset_context if base else "",
    )


def _run_creator_generation(brief: ContentBrief) -> None:
    started = time.perf_counter()
    choice = st.session_state.get("creator_model_choice", DEFAULT_TEXT_MODEL_LABEL)
    had_result = isinstance(st.session_state.get("generated_script"), ContentScript)
    st.session_state.pop("creator_parameter_feedback", None)
    st.session_state.pop("creator_submitted_parameters", None)
    brief = _rebuild_content_brief(
        brief,
        asset_context=str(st.session_state.get("creator_asset_context", "")),
    )
    try:
        router = get_model_router()
        script, run_mode = generate_content_script_for_mode(brief, choice, router=router)
        trace = script.retrieval_trace
        model = script.model_evidence
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        st.session_state["model_run_mode"] = run_mode
        st.session_state["creator_model_status_choice"] = choice
        if run_mode == "api":
            model_name = model.model if model else router.status().text_model
            st.session_state["creator_model_status"] = f"DeepSeek 已调用 · {model_name}"
        else:
            st.session_state["creator_model_status"] = "本地演示生成 · 未调用模型 API"
        st.session_state["creator_run_attempt"] = {
            "status": "success",
            "status_label": "生成成功",
            "choice": choice,
            "provider": model.provider if model else "local-demo",
            "model": model.model if model else (trace.model if trace else "local-demo-generator"),
            "mode": "API" if model else "本地演示",
            "request_id": model.request_id if model else "",
            "latency_ms": model.latency_ms if model else elapsed_ms,
            "input_tokens": model.input_tokens if model else None,
            "output_tokens": model.output_tokens if model else None,
            "knowledge_called": trace is not None,
            "knowledge_bases": tuple(
                name
                for name, used in (
                    ("非遗事实库", bool(trace and trace.fact_chunks_used)),
                    ("创作方法库", bool(trace and trace.creative_chunks_used)),
                    ("运营策略库", bool(trace and trace.operation_chunks_used)),
                )
                if used
            ),
            "run_id": trace.generation_id if trace else "",
            "created_at": trace.created_at if trace else "",
            "error": "",
            "debug_error": "",
        }
        st.session_state["generated_script"] = script
        st.session_state["creator_brief"] = brief
        st.session_state["creator_parameter_sync_pending"] = brief
        st.session_state["creator_stage"] = "judgment"
        action = "已应用参数并重新生成" if had_result else "已应用参数并生成"
        st.session_state["creator_parameter_feedback"] = {
            "status": "success",
            "message": (
                f"{action}：{brief.platform} · {brief.duration} · "
                f"{brief.aspect_ratio} · {brief.tone}。已创建新的 Run 记录。"
            ),
        }
        completion = (
            f"已按“{brief.revision_instruction}”完成新版本，并生成了新的 Run 证据。"
            if brief.revision_instruction
            else "已完成创作判断。请确认方向，或直接告诉我需要怎样修改。"
        )
        st.session_state.setdefault("creator_messages", []).append(
            {"role": "assistant", "content": completion}
        )
        _persist_current_project(script, brief)
        st.rerun()
    except (ValueError, ModelCallError) as exc:
        evidence = exc.evidence if isinstance(exc, ModelCallError) else None
        trace = exc.retrieval_trace if isinstance(exc, ModelCallError) else None
        try:
            selected_mode = get_model_router().resolve_text_mode(choice)
        except ModelCallError:
            selected_mode = "unavailable"
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        st.session_state["creator_model_status_choice"] = st.session_state.get(
            "creator_model_choice", DEFAULT_TEXT_MODEL_LABEL
        )
        st.session_state["creator_model_status"] = "模型调用失败"
        debug_error = (
            exc.detail if isinstance(exc, ModelCallError) else str(exc)
        ) + "\n\n" + traceback.format_exc()
        st.session_state["creator_run_attempt"] = {
            "status": "failed",
            "status_label": "生成失败",
            "choice": choice,
            "provider": evidence.provider if evidence else (
                "deepseek" if selected_mode in {"deepseek", "unavailable"} else "local-demo"
            ),
            "model": evidence.model if evidence else (
                get_model_router().resolve_text_model(choice)
                if selected_mode in {"deepseek", "unavailable"}
                else "local-demo-generator"
            ),
            "mode": "API" if evidence or selected_mode == "deepseek" else "未调用 API",
            "request_id": evidence.request_id if evidence else "",
            "latency_ms": evidence.latency_ms if evidence else elapsed_ms,
            "input_tokens": evidence.input_tokens if evidence else None,
            "output_tokens": evidence.output_tokens if evidence else None,
            "knowledge_called": trace is not None,
            "knowledge_bases": tuple(
                name
                for name, used in (
                    ("非遗事实库", bool(trace and trace.fact_chunks_used)),
                    ("创作方法库", bool(trace and trace.creative_chunks_used)),
                    ("运营策略库", bool(trace and trace.operation_chunks_used)),
                )
                if used
            ),
            "run_id": trace.generation_id if trace else "",
            "created_at": trace.created_at if trace else "",
            "error": str(exc),
            "debug_error": _redact_sensitive_text(debug_error),
        }
        st.session_state["creator_parameter_feedback"] = {
            "status": "failed",
            "message": f"参数已提交，但生成失败：{exc}",
        }
        st.rerun()
    except Exception:
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        debug_error = _redact_sensitive_text(traceback.format_exc())
        st.session_state["creator_model_status_choice"] = choice
        st.session_state["creator_model_status"] = "模型调用失败"
        st.session_state["creator_run_attempt"] = {
            "status": "failed",
            "status_label": "生成失败",
            "choice": choice,
            "provider": "unknown",
            "model": "unknown",
            "mode": "调用未完成",
            "request_id": "",
            "latency_ms": elapsed_ms,
            "input_tokens": None,
            "output_tokens": None,
            "knowledge_called": False,
            "knowledge_bases": (),
            "run_id": "",
            "created_at": "",
            "error": "生成失败，请查看诊断详情。",
            "debug_error": debug_error,
        }
        st.session_state["creator_parameter_feedback"] = {
            "status": "failed",
            "message": "参数已提交，但生成失败。请在“知识与 Run”中查看诊断详情。",
        }
        st.rerun()


def _run_creator_revision(instruction: str) -> None:
    """Regenerate the current result through the selected route."""
    brief = st.session_state.get("creator_brief")
    if not isinstance(brief, ContentBrief):
        st.warning("请先生成一版内容，再进行快速调整。")
        return
    platform = brief.platform
    for name in ("抖音", "小红书", "B站", "视频号", "TikTok"):
        if name in instruction:
            platform = name
            break
    revised = _rebuild_content_brief(
        brief, platform=platform, revision_instruction=instruction.strip()
    )
    _run_creator_generation(revised)


def _rebuild_content_brief(value: object, **changes: str) -> ContentBrief:
    """Upgrade a brief left in Session State by an older hot-reloaded module."""
    defaults = ContentBrief("", "", "第一次接触非遗的人", "小红书", "安静观察")
    data = {
        name: getattr(value, name, getattr(defaults, name))
        for name in ContentBrief.__dataclass_fields__
    }
    data.update(changes)
    return ContentBrief(**data)


def _persist_current_project(
    script: ContentScript | None = None, brief: ContentBrief | None = None
) -> str | None:
    script = script or st.session_state.get("generated_script")
    brief = brief or st.session_state.get("creator_brief")
    if not isinstance(script, ContentScript) or not isinstance(brief, ContentBrief):
        return None
    project_id = save_project(
        project_id=st.session_state.get("creator_project_id"),
        brief=brief,
        script=script,
        messages=list(st.session_state.get("creator_messages", [])),
        run_attempt=st.session_state.get("creator_run_attempt"),
        model_choice=str(
            st.session_state.get("creator_model_choice", DEFAULT_TEXT_MODEL_LABEL)
        ),
    )
    st.session_state["creator_project_id"] = project_id
    return project_id


def _render_conversation_history() -> None:
    with st.container(border=True):
        heading, close = st.columns((5, 1))
        heading.markdown("### 历史会话")
        if close.button("关闭", key="close-history", width="stretch"):
            st.query_params.pop("history", None)
            st.rerun()
        projects = list_projects()
        if not projects:
            st.caption("还没有已保存的创作项目。生成第一版内容后会自动保存在这里。")
            return
        for project in projects:
            info, action = st.columns((5, 1))
            info.markdown(
                f"**{project['title']}**  \n{project['model_choice']} · {project['updated_at']}"
            )
            if action.button(
                "恢复",
                key=f"restore-project-{project['id']}",
                width="stretch",
            ):
                restored = load_project(project["id"])
                if restored is None:
                    st.error("该历史项目已不存在。")
                    return
                st.session_state["creator_project_id"] = restored["project_id"]
                st.session_state["creator_brief"] = restored["brief"]
                st.session_state["creator_parameter_sync_pending"] = restored["brief"]
                st.session_state["generated_script"] = restored["script"]
                st.session_state["creator_messages"] = restored["messages"]
                st.session_state["creator_run_attempt"] = restored["run_attempt"]
                st.session_state["creator_model_choice"] = restored["model_choice"]
                st.session_state["creator_stage"] = "master"
                st.session_state["creator_asset_context"] = restored["brief"].asset_context
                st.query_params.pop("history", None)
                st.rerun()


def _redact_sensitive_text(value: str) -> str:
    for key_name in ("DEEPSEEK_API_KEY", "ARK_API_KEY", "LAS_API_KEY"):
        secret = os.getenv(key_name, "")
        if secret:
            value = value.replace(secret, "[REDACTED]")
    return value


def _render_visual_production_cards(script: ContentScript) -> None:
    router = get_model_router()
    image_ready = router.status().image_ready
    st.markdown("### 继续制作")
    st.markdown(
        '<div class="production-flow">'
        '<article class="ready"><i>05</i><b>视觉资产</b><span>参考图与角色资产</span><em>可配置</em></article>'
        '<article><i>06</i><b>分镜首帧</b><span>Seedream 图片任务</span><em>待生成</em></article>'
        '<article><i>07</i><b>镜头视频</b><span>逐镜头视频任务</span><em>待生成</em></article>'
        '<article><i>08</i><b>成片制作</b><span>配音、字幕与剪辑</span><em>待制作</em></article>'
        '</div>',
        unsafe_allow_html=True,
    )
    shot_count = len(script.storyboard)
    st.caption(f"当前方案包含 {shot_count} 个结构化镜头。先确认参考资产，再批量生成首帧。")
    first, second, third = st.columns(3)
    generate_frames = first.button(
        "生成全部首帧",
        width="stretch",
        disabled=not image_ready,
        help="需要配置 ARK_API_KEY" if not image_ready else "调用 Seedream 生成分镜首帧",
    )
    second.button("创建视频任务", width="stretch", disabled=True, help="待接入视频生成模型")
    third.button("进入成片制作", width="stretch", disabled=True, help="待接入配音与剪辑流水线")
    if not image_ready:
        st.caption("首帧生成尚未配置 ARK_API_KEY；脚本、分镜和历史功能不受影响。")
    if generate_frames:
        prompt = (
            f"为非遗短视频《{script.title}》生成 {shot_count} 张连续分镜首帧。"
            "保持人物、服装、工坊、材料与色彩统一；画面真实克制，不添加文字或水印。\n"
            + "\n".join(
                f"镜头 {row[0]}：{row[5]}；景别 {row[3]}；情绪 {row[6]}"
                for row in script.storyboard
            )
        )
        try:
            with st.spinner("正在调用 Seedream 生成首帧……"):
                result = router.generate_image(prompt, count=max(1, min(shot_count, 15)))
            st.session_state["creator_first_frames"] = result.images
            st.session_state["creator_image_evidence"] = result.evidence
            st.success(
                f"已生成 {len(result.images)} 张首帧 · {result.evidence.model} · "
                f"{result.evidence.latency_ms} ms"
            )
        except (ValueError, ModelCallError) as exc:
            st.error(str(exc))
    frames = st.session_state.get("creator_first_frames", ())
    if frames:
        st.image(list(frames), caption=[f"首帧 {index}" for index in range(1, len(frames) + 1)])


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
                brief = ContentBrief(
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
                try:
                    st.session_state["generated_script"] = generate_content_script_with_model(brief)
                    st.session_state["model_run_mode"] = "api"
                except ValueError:
                    st.session_state["generated_script"] = generate_content_script(brief)
                    st.session_state["model_run_mode"] = "local"
                progress.write("✓ 正在设计内容结构并进行文化核验")
                progress.update(label="创作判断已完成", state="complete", expanded=False)
            st.session_state["creator_stage"] = "judgment"
        except (ValueError, ModelCallError) as exc:
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
    script_changed = False
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
            st.session_state["creator_stage"] = "master"
            st.rerun()
        if reset.button("修改设定 / 重新判断", width="stretch"):
            st.session_state.pop("generated_script", None)
            st.rerun()
        return

    arc_labels = ("Hook", "建立情境", "工艺过程", "文化信息", "情绪收尾")
    arc_times = tuple(row[1] for row in script.storyboard[:5])
    arc_markup = "".join(
        f"<span><b>{index:02d} {escape(label)}</b><small>{escape(time_range)}</small></span>"
        for index, (label, time_range) in enumerate(zip(arc_labels, arc_times, strict=True), 1)
    )
    st.markdown(
        f'<section class="studio-result-card"><h3>内容结构</h3><div class="story-arc">{arc_markup}</div></section>',
        unsafe_allow_html=True,
    )
    st.markdown("**快速调整**")
    quick_revisions = (
        "更短一点",
        "更有故事感",
        "更年轻",
        "更克制",
        "更知识型",
        "加强前三秒",
        "减少旁白",
        "增加画面表现",
        "改成抖音版",
        "改成小红书版",
        "改成 B 站版",
        "改成视频号版",
    )
    run_id = script.retrieval_trace.generation_id if script.retrieval_trace else "draft"
    for row_start in range(0, len(quick_revisions), 4):
        columns = st.columns(4)
        for column, instruction in zip(columns, quick_revisions[row_start : row_start + 4], strict=True):
            if column.button(
                instruction,
                key=f"quick-revision-{run_id}-{row_start}-{instruction}",
                width="stretch",
            ):
                st.session_state.setdefault("creator_messages", []).append(
                    {"role": "user", "content": instruction}
                )
                _run_creator_revision(instruction)
    st.markdown(
        '<section class="studio-result-card"><div class="result-card-head"><h3>Master Script</h3><span>复制　编辑　重新生成</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(f"#### {script.title}")
    st.info(f"前 3 秒 Hook：{script.hook}")
    edited_voiceover = st.text_area(
        "主脚本正文（每行一段）",
        value="\n".join(script.voiceover),
        height=220,
        key=f"master-script-{run_id}",
    )
    voiceover = tuple(line.strip() for line in edited_voiceover.splitlines() if line.strip())
    if voiceover and voiceover != script.voiceover:
        script = replace(script, voiceover=voiceover)
        st.session_state["generated_script"] = script
        script_changed = True
    st.markdown("</section>", unsafe_allow_html=True)
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
    edited_storyboard = st.data_editor(
        [dict(zip(headers, row, strict=True)) for row in script.storyboard],
        hide_index=True,
        width="stretch",
        key=f"storyboard-{run_id}",
    )
    storyboard = tuple(
        tuple(str(row.get(header, "")) for header in headers)
        for row in edited_storyboard
    )
    if storyboard != script.storyboard:
        script = replace(script, storyboard=storyboard)
        st.session_state["generated_script"] = script
        script_changed = True
    st.markdown("</section>", unsafe_allow_html=True)
    st.markdown('<section class="studio-result-card"><h3>发布包</h3>', unsafe_allow_html=True)
    st.markdown("**标题建议**")
    for number, item in enumerate(script.titles, start=1):
        st.write(f"{number:02d}　{item}")
    st.markdown("**封面文案**")
    st.write("　/　".join(script.covers))
    st.markdown("**发布简介**")
    edited_caption = st.text_area(
        "发布简介（可编辑）",
        value=script.caption,
        height=140,
        label_visibility="collapsed",
        key=f"publish-caption-{run_id}",
    )
    if edited_caption != script.caption:
        script = replace(script, caption=edited_caption)
        st.session_state["generated_script"] = script
        script_changed = True
    st.markdown("**标签**")
    st.code(" ".join(script.tags), language=None)
    st.markdown("</section>", unsafe_allow_html=True)
    if script_changed:
        _persist_current_project(script)
    save, export_col, continue_make, publish = st.columns(4)
    if save.button("保存草稿", width="stretch"):
        _persist_current_project(script)
        st.success("草稿已保存到本地项目库，重启网页后仍可恢复。")
    export_col.download_button(
        "导出脚本",
        data=(
            f"{script.title}\n\n"
            + "\n".join(script.voiceover)
            + f"\n\n发布简介\n{script.caption}\n\n结构化分镜\n"
            + "\n".join(" | ".join(row) for row in script.storyboard)
        ),
        file_name="HAHA-Master-Script.txt",
        mime="text/plain",
        width="stretch",
    )
    if continue_make.button("继续制作", width="stretch"):
        st.session_state["creator_stage"] = "storyboard"
        st.rerun()
    if publish.button("进入视频投稿", type="primary", width="stretch"):
        _navigate("publish")


def _render_review_panel(
    script: ContentScript | None,
    run_attempt: dict[str, object] | None = None,
) -> None:
    if run_attempt and run_attempt.get("status") == "failed":
        _render_run_evidence(script, run_attempt)
        st.error(str(run_attempt.get("error") or "生成失败。"))
        if detail := str(run_attempt.get("debug_error") or ""):
            with st.expander("开发诊断详情"):
                st.code(detail, language="text")
        return
    if script is None:
        if run_attempt and run_attempt.get("status") == "success":
            st.error("本次 Run 标记成功，但没有对应的生成结果。")
            return
        st.markdown(
            '<section class="run-evidence idle"><div class="run-evidence-head">'
            '<span><i></i>RUN 未运行</span><b>等待生成</b></div>'
            '<p>点击“生成本次创作判断”后，这里会显示三套知识库的真实检索记录。</p></section>'
            '<div class="review-empty"><span>生成后将在这里显示</span>'
            "<div>◇ <b>方法依据</b><small>创作方法知识库</small></div>"
            "<div>↗ <b>策略依据</b><small>运营策略知识库</small></div>"
            "<div>✓ <b>事实依据</b><small>非遗事实知识库</small></div>"
            "<div>◆ <b>运营建议</b><small>平台与内容判断</small></div></div>",
            unsafe_allow_html=True,
        )
        return
    if run_attempt and run_attempt.get("run_id") != (
        script.retrieval_trace.generation_id if script.retrieval_trace else ""
    ):
        st.error("当前结果与最近一次 Run 不匹配，已隐藏旧证据。")
        return
    _render_run_evidence(script, run_attempt)
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
    st.markdown(f"#### 事实依据 · {len(script.fact_sources)} 条")
    if script.fact_sources:
        for chunk_id, title, source_url in script.fact_sources:
            st.markdown(
                f'<div class="source-item"><b>[{escape(chunk_id)}]</b> {escape(title)} '
                f'<a href="{escape(source_url)}" target="_blank">权威来源</a></div>',
                unsafe_allow_html=True,
            )
    else:
        st.caption("事实库未命中准确项目，以下内容仍需人工核验。")
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


def _render_run_evidence(
    script: ContentScript | None,
    run_attempt: dict[str, object] | None = None,
) -> None:
    if run_attempt and run_attempt.get("status") == "failed":
        knowledge_called = bool(run_attempt.get("knowledge_called"))
        st.markdown(
            '<section class="run-evidence failed">'
            '<div class="run-evidence-head"><span>RUN 失败</span><b>本次调用未完成</b></div>'
            f'<dl><dt>Provider</dt><dd>{escape(str(run_attempt.get("provider", "unknown")))}</dd>'
            f'<dt>模型</dt><dd>{escape(str(run_attempt.get("model", "unknown")))}</dd>'
            f'<dt>模式</dt><dd>{escape(str(run_attempt.get("mode", "unknown")))}</dd>'
            f'<dt>状态</dt><dd>{escape(str(run_attempt.get("status_label", "生成失败")))}</dd>'
            f'<dt>请求 ID</dt><dd>{escape(str(run_attempt.get("request_id") or "Provider 未返回"))}</dd>'
            f'<dt>耗时</dt><dd>{escape(str(run_attempt.get("latency_ms", "未知")))} ms</dd>'
            f'<dt>输入 / 输出 Token</dt><dd>{escape(str(run_attempt.get("input_tokens") if run_attempt.get("input_tokens") is not None else "未提供"))} / '
            f'{escape(str(run_attempt.get("output_tokens") if run_attempt.get("output_tokens") is not None else "未提供"))}</dd>'
            f'<dt>知识库</dt><dd>{"已调用：" + escape("、".join(run_attempt.get("knowledge_bases", ()))) if knowledge_called else "未调用"}</dd>'
            f'<dt>Run ID</dt><dd>{escape(str(run_attempt.get("run_id") or "未生成"))}</dd></dl>'
            '</section>',
            unsafe_allow_html=True,
        )
        return
    if script is None:
        st.error("没有可展示的本次生成证据。")
        return
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
    fact_rows = "".join(
        f'<li><b>{escape(chunk_id)}</b><span>{escape(title)}</span>'
        f'<em>{score_lookup.get(chunk_id, 0):.3f}</em></li>'
        for chunk_id, title, _ in script.fact_sources
    )
    model = script.model_evidence
    provider = str(run_attempt.get("provider")) if run_attempt else (
        model.provider if model else "local-demo"
    )
    model_name = str(run_attempt.get("model")) if run_attempt else (
        model.model if model else trace.model
    )
    run_mode = str(run_attempt.get("mode")) if run_attempt else (
        "API" if model else "本地演示"
    )
    run_id = str(run_attempt.get("run_id")) if run_attempt else trace.generation_id
    run_status = str(run_attempt.get("status_label", "生成成功")) if run_attempt else "生成成功"
    request_id = str(run_attempt.get("request_id", "")) if run_attempt else (
        model.request_id if model else ""
    )
    latency_ms = run_attempt.get("latency_ms") if run_attempt else (
        model.latency_ms if model else None
    )
    input_tokens = run_attempt.get("input_tokens") if run_attempt else (
        model.input_tokens if model else None
    )
    output_tokens = run_attempt.get("output_tokens") if run_attempt else (
        model.output_tokens if model else None
    )
    knowledge_called = bool(run_attempt.get("knowledge_called")) if run_attempt else True
    model_evidence = (
        f'<div class="model-evidence {"verified" if model else "local"}">'
        f'<b>{"真实模型 API" if model else "本地演示生成"}</b>'
        f'<span>{escape(provider)} · {escape(model_name)} · {escape(run_mode)}</span>'
        f'<dl><dt>请求 ID</dt><dd>{escape(request_id or "Provider 未返回")}</dd>'
        f'<dt>输入 / 输出 Token</dt><dd>{escape(str(input_tokens if input_tokens is not None else "未提供"))} / '
        f'{escape(str(output_tokens if output_tokens is not None else "未提供"))}</dd>'
        f'<dt>耗时</dt><dd>{escape(str(latency_ms if latency_ms is not None else "未知"))} ms</dd>'
        f'<dt>知识库调用</dt><dd>{"已调用" if knowledge_called else "未调用"}</dd></dl></div>'
    )
    st.markdown(
        f'<section class="run-evidence {"verified" if run_attempt is None or run_attempt.get("status") == "success" else "failed"}">'
        f'<div class="run-evidence-head"><span>RUN {escape(run_status)}</span><b>{"Knowledge & Context 检索完成" if knowledge_called else "未调用知识库"}</b></div>'
        '<div class="run-evidence-stats">'
        f'<span><b>{len(script.method_sources)}</b>方法命中</span>'
        f'<span><b>{len(script.strategy_sources)}</b>策略命中</span>'
        f'<span><b>{len(script.fact_sources)}</b>事实命中</span>'
        f'<span><b>{3 if knowledge_called else 0}</b>独立查询</span></div>'
        + model_evidence
        + f'<dl><dt>Run ID</dt><dd>{escape(run_id)}</dd>'
        f'<dt>知识版本</dt><dd>{escape(trace.document_version)}</dd>'
        f'<dt>运行时间</dt><dd>{escape(trace.created_at)}</dd></dl>'
        '<div class="run-query"><b>Creative Query</b>'
        f'<p>{escape(trace.creative_query)}</p></div>'
        '<div class="run-query"><b>Operation Query</b>'
        f'<p>{escape(trace.operation_query)}</p></div>'
        '<div class="run-query"><b>Fact Query</b>'
        f'<p>{escape(trace.fact_query)}</p></div>'
        '<div class="run-hit-group"><b>创作方法库命中与 Rerank 分</b>'
        f'<ul>{method_rows}</ul></div>'
        '<div class="run-hit-group"><b>运营策略库命中与 Rerank 分</b>'
        f'<ul>{strategy_rows}</ul></div>'
        '<div class="run-hit-group"><b>非遗事实库命中与 Rerank 分</b>'
        f'<ul>{fact_rows or "<li><span>未命中准确事实项目</span></li>"}</ul></div>'
        '<footer>来源：haha非遗项目类别细化.docx + HAHA飞颐项目营销端总材料包(1).docx · 三库独立检索</footer>'
        "</section>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
