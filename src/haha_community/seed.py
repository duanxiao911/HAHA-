"""Versioned, explicitly non-authoritative catalog used by internal C2 environments."""

from __future__ import annotations

from copy import deepcopy

CATALOG_VERSION = "c2-demo-2026-10-15"
CREATED_AT = "2026-10-01T00:00:00.000Z"
CHECKED_AT = "2026-10-01T08:00:00.000Z"

REGIONS = [
    ("region-guizhou", "guizhou", "贵州", "贵州省", ["苗绣", "银饰", "古歌"], 116),
    ("region-yunnan", "yunnan", "云南", "云南省", ["扎染", "银饰", "民族舞蹈"], 128),
    ("region-sichuan", "sichuan", "四川", "四川省", ["竹编", "漆器", "川剧"], 142),
    ("region-jiangxi", "jiangxi", "江西", "江西省", ["陶瓷", "制瓷", "窑作"], 101),
    ("region-zhejiang", "zhejiang", "浙江", "浙江省", ["木作", "青瓷", "丝织"], 135),
    ("region-jiangsu", "jiangsu", "江苏", "江苏省", ["刺绣", "云锦", "昆曲"], 121),
    ("region-fujian", "fujian", "福建", "福建省", ["木偶戏", "白瓷", "茶技"], 109),
    ("region-guangdong", "guangdong", "广东", "广东省", ["醒狮", "粤剧", "彩扎"], 148),
]

SOURCES = [
    ("source-national-list", "国家级非物质文化遗产代表性项目名录", "中国非物质文化遗产网", "official", "https://www.ihchina.cn/"),
    ("source-guizhou-embroidery", "贵州苗绣项目资料索引", "HAHA 演示资料库", "institution", ""),
    ("source-jingdezhen-ceramics", "景德镇传统制瓷技艺资料索引", "HAHA 演示资料库", "institution", ""),
    ("source-bai-dyeing", "白族扎染技艺资料索引", "HAHA 演示资料库", "institution", ""),
    ("source-bamboo-weaving", "道明竹编资料索引", "HAHA 演示资料库", "institution", ""),
    ("source-field-notes", "手艺人口述与现场记录（演示）", "HAHA 社区编辑部", "interview", ""),
]

PROJECTS = [
    ("project-miao-embroidery", "miao-embroidery", "苗绣", "刺绣", "region-guizhou", "person-ajin", ["棉布", "丝线"], ["平绣", "挑花"], ["source-national-list", "source-guizhou-embroidery"]),
    ("project-jingdezhen-ceramics", "jingdezhen-ceramics", "景德镇手工制瓷技艺", "陶瓷", "region-jiangxi", "person-nanqing", ["瓷石", "高岭土", "釉料"], ["拉坯", "利坯", "施釉", "烧成"], ["source-national-list", "source-jingdezhen-ceramics"]),
    ("project-bai-dyeing", "bai-dyeing", "白族扎染技艺", "染织", "region-yunnan", "person-shanlan", ["棉布", "植物染料"], ["扎花", "浸染", "拆线"], ["source-national-list", "source-bai-dyeing"]),
    ("project-daoming-bamboo", "daoming-bamboo", "道明竹编", "竹编", "region-sichuan", "person-qingmie", ["慈竹"], ["破竹", "分丝", "起底", "收口"], ["source-national-list", "source-bamboo-weaving"]),
]

PEOPLE = [
    ("person-ajin", "ajin-demo", "阿锦（演示人物）", "inheritor", "region-guizhou", "project-miao-embroidery", "锦", "red"),
    ("person-nanqing", "nanqing-demo", "南青（演示人物）", "creator", "region-jiangxi", "project-jingdezhen-ceramics", "瓷", "blue"),
    ("person-shanlan", "shanlan-demo", "山蓝（演示人物）", "creator", "region-yunnan", "project-bai-dyeing", "染", "green"),
    ("person-qingmie", "qingmie-demo", "青篾（演示人物）", "inheritor", "region-sichuan", "project-daoming-bamboo", "竹", "gold"),
]

CONTENT_SPECS = [
    ("content-embroidery-01", "one-thread-to-distance", "short_video", "一根线，怎样绣出远方？", "跟随一双手，看纹样如何连接山川、生活与记忆。", "person-ajin", "embroidery", "刺绣", "region-guizhou", ["project-miao-embroidery"], ["person-ajin"], ["苗绣", "纹样", "人物故事"], 138, "绣", "red", 86000, 3214, "source-guizhou-embroidery", "苗绣内容需要把具体纹样解释与可核验来源绑定。"),
    ("content-ceramics-01", "sound-remembered-by-fire", "long_video", "泥土被火记住的声音", "从原料、成形到烧成，理解器物为什么需要等待。", "person-nanqing", "ceramics", "陶瓷", "region-jiangxi", ["project-jingdezhen-ceramics"], ["person-nanqing"], ["制瓷", "窑火", "材料"], 222, "陶", "green", 62000, 2038, "source-jingdezhen-ceramics", "制瓷过程由多道工序构成，具体工序数量随产品与口径不同。"),
    ("content-dyeing-01", "why-blue-cracks", "knowledge_card", "蓝染为什么会留下冰裂纹？", "用扎结和防染的过程解释纹样如何出现。", "person-shanlan", "dyeing", "染织", "region-yunnan", ["project-bai-dyeing"], ["person-shanlan"], ["扎染", "蓝染", "纹样"], 116, "染", "blue", 58000, 1926, "source-bai-dyeing", "扎结形成的防染区域会影响拆线后的纹样边界。"),
    ("content-bamboo-01", "bamboo-thread-forms", "process_tutorial", "竹丝在指尖慢慢成形", "观察选竹、分丝与编织动作，而不是只看成品。", "person-qingmie", "bamboo", "竹编", "region-sichuan", ["project-daoming-bamboo"], ["person-qingmie"], ["竹编", "工序", "材料"], 151, "编", "gold", 49000, 1488, "source-bamboo-weaving", "竹编内容应区分材料准备、编织和收口等不同环节。"),
    ("content-papercut-01", "life-inside-window-flower", "image_story", "窗花里藏着怎样的生活？", "从生活场景观察剪纸图案，而不替观众虚构唯一寓意。", "person-ajin", "papercut", "剪纸", "region-jiangsu", [], [], ["剪纸", "窗花", "生活"], 108, "剪", "red", 41000, 1125, "source-field-notes", "纹样含义受地区、使用场景与讲述者影响，不宜给出单一结论。"),
    ("content-opera-01", "three-minutes-backstage", "inheritor_story", "后台三分钟，台上一出戏", "从候场、整理和上场前的细节进入传统表演。", "person-nanqing", "opera", "戏曲", "region-fujian", [], [], ["戏曲", "后台", "人物"], 252, "戏", "blue", 37000, 986, "source-field-notes", "演示内容不指向具体剧种、人物或真实采访。"),
    ("content-woodwork-01", "mortise-without-nail", "knowledge_card", "一榫一卯，不用一枚钉", "用结构示意理解传统木作连接方式。", "person-qingmie", "woodwork", "木作", "region-zhejiang", [], [], ["木作", "榫卯", "结构"], 166, "木", "green", 32000, 842, "source-field-notes", "并非所有传统木构都完全不使用金属连接件，标题仅用于内容切入。"),
    ("content-folklore-01", "before-lion-dance", "short_video", "醒狮之前，人们在准备什么？", "把镜头移向表演之前的器具、协作与现场秩序。", "person-ajin", "folklore", "民俗", "region-guangdong", [], [], ["醒狮", "节庆", "现场"], 188, "俗", "gold", 29000, 771, "source-field-notes", "具体仪式与流程存在地区和团队差异。"),
    ("content-embroidery-02", "other-side-of-embroidery", "long_video", "双面绣的另一面是什么？", "从正反两面的关系理解精细刺绣的观看方式。", "person-ajin", "embroidery", "刺绣", "region-jiangsu", [], ["person-ajin"], ["刺绣", "双面绣", "细节"], 124, "针", "blue", 26000, 659, "source-field-notes", "本条为演示选题，正式发布前需补充对应项目来源。"),
    ("content-ceramics-02", "porcelain-cup-process", "process_tutorial", "一只白瓷杯经过哪些工序？", "用可核验的过程卡替代夸张的固定工序数字。", "person-nanqing", "ceramics", "陶瓷", "region-fujian", ["project-jingdezhen-ceramics"], ["person-nanqing"], ["白瓷", "工序", "器物"], 320, "瓷", "green", 24000, 612, "source-jingdezhen-ceramics", "工序划分取决于统计口径，不使用未经来源支持的固定数字。"),
]


def _base(entity_id: str, workspace_id: str) -> dict[str, object]:
    return {
        "id": entity_id,
        "workspaceId": workspace_id,
        "provenance": "demo_seed",
        "createdAt": CREATED_AT,
        "updatedAt": CREATED_AT,
    }


def seed_entities(workspace_id: str) -> list[dict[str, object]]:
    """Return a fresh, self-consistent catalog for one workspace."""
    entities: list[dict[str, object]] = []
    regions: dict[str, dict[str, object]] = {}
    sources: dict[str, dict[str, object]] = {}
    people: dict[str, dict[str, object]] = {}

    for entity_id, slug, name, province, crafts, count in REGIONS:
        payload = {
            **_base(entity_id, workspace_id),
            "slug": slug,
            "name": name,
            "province": province,
            "summary": f"以{name}地方生活与手工传统为线索的内部演示地区档案。",
            "featuredCrafts": crafts,
            "projectCount": count,
        }
        regions[entity_id] = payload
        entities.append({"kind": "region", "slug": slug, "title": name, "status": "active", "payload": payload})

    for entity_id, title, publisher, level, url in SOURCES:
        payload = {
            **_base(entity_id, workspace_id),
            "title": title,
            "publisher": publisher,
            "sourceLevel": level,
            "accessedAt": CHECKED_AT,
            "note": "内部演示来源索引；正式发布前必须逐条复核原始资料。",
        }
        if url:
            payload["url"] = url
        sources[entity_id] = payload
        entities.append({"kind": "source", "slug": entity_id, "title": title, "status": "active", "payload": payload})

    for entity_id, slug, name, category, region_id, person_id, materials, techniques, source_ids in PROJECTS:
        payload = {
            **_base(entity_id, workspace_id),
            "slug": slug,
            "name": name,
            "level": "national",
            "category": category,
            "regionIds": [region_id],
            "inheritorIds": [person_id],
            "summary": f"围绕材料、技艺与生活语境组织的{name}内部演示档案。",
            "materials": materials,
            "techniques": techniques,
            "sourceIds": source_ids,
            "verificationStatus": "pending",
        }
        entities.append({"kind": "project", "slug": slug, "title": name, "status": "active", "payload": payload})

    for entity_id, slug, name, role, region_id, project_id, mark, tone in PEOPLE:
        payload = {
            **_base(entity_id, workspace_id),
            "slug": slug,
            "displayName": name,
            "role": role,
            "avatar": {
                "id": f"asset-avatar-{entity_id}",
                "kind": "image",
                "alt": f"{name}的内部演示头像",
                "placeholder": {"mark": mark, "tone": tone},
            },
            "bio": "用于验证人物、项目、关注与内容关系的虚构演示人物。",
            "regionId": region_id,
            "projectIds": [project_id],
            "verified": False,
            "demoLabel": "内部演示人物，并非真实人物档案",
        }
        people[entity_id] = payload
        entities.append({"kind": "person", "slug": slug, "title": name, "status": "active", "payload": payload})

    content_payloads: list[dict[str, object]] = []
    for index, spec in enumerate(CONTENT_SPECS, 1):
        (
            entity_id, slug, content_type, title, summary, creator_id, category_id,
            category_label, region_id, project_ids, person_ids, tags, duration, mark,
            tone, view_count, interaction_count, source_id, fact_text,
        ) = spec
        cover = {
            "id": f"asset-{entity_id}-cover",
            "kind": "image",
            "alt": f"{mark}主题内部演示封面",
            "durationSeconds": duration,
            "placeholder": {"mark": mark, "tone": tone},
        }
        fact_id = f"fact-{index:02d}"
        fact = {
            **_base(fact_id, workspace_id),
            "contentId": entity_id,
            "text": fact_text,
            "status": "pending",
            "sourceIds": [source_id],
            "checkedAt": CHECKED_AT,
            "note": "内部演示事实；需由服务端事实库和人工审核复核。",
        }
        entities.append({"kind": "fact", "slug": fact_id, "title": fact_text, "status": "pending", "payload": fact})
        payload = {
            **_base(entity_id, workspace_id),
            "slug": slug,
            "contentType": content_type,
            "title": title,
            "summary": summary,
            "cover": cover,
            "creatorId": creator_id,
            "creator": deepcopy(people[creator_id]),
            "categoryId": category_id,
            "categoryLabel": category_label,
            "regionId": region_id,
            "regionLabel": regions[region_id]["name"],
            "projectIds": list(project_ids),
            "personIds": list(person_ids),
            "tags": list(tags),
            "durationSeconds": duration,
            "metrics": {
                "viewCount": view_count,
                "interactionCount": interaction_count,
                "commentCount": max(3, round(interaction_count * 0.06)),
                "bookmarkCount": round(interaction_count * 0.28),
            },
            "reactionCounts": {
                "bookmark": round(interaction_count * 0.28),
                "want_to_learn": round(interaction_count * 0.19),
                "respect": round(interaction_count * 0.45),
                "watch_later": round(interaction_count * 0.08),
            },
            "trust": {
                "status": "pending",
                "label": "演示资料 · 待正式复核",
                "sourceCount": 1,
                "checkedAt": CHECKED_AT,
                "aiAssisted": False,
            },
            "viewer": {
                "reactions": [],
                "followedCreator": False,
                "viewed": False,
                "watchProgressSeconds": 0,
            },
            "publishedAt": f"2026-09-{max(1, 29 - index):02d}T00:00:00.000Z",
            "body": f"{summary}\n\n这是 HAHA 内部演示内容，用于验证真实 API、账户与创作者闭环；不是已发布的真实人物采访或机构档案。",
            "media": [cover],
            "claims": [fact],
            "sources": [deepcopy(sources[source_id])],
            "relatedContentIds": [],
        }
        content_payloads.append(payload)

    for payload in content_payloads:
        payload["relatedContentIds"] = [
            item["id"]
            for item in content_payloads
            if item["id"] != payload["id"]
            and (
                item["categoryId"] == payload["categoryId"]
                or item["regionId"] == payload["regionId"]
            )
        ][:3]
        entities.append({
            "kind": "content",
            "slug": payload["slug"],
            "title": payload["title"],
            "status": "published",
            "payload": payload,
        })
    return entities
