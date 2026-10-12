import type {
  CommunityPerson,
  CommunityRegion,
  ContentDetail,
  ContentMetrics,
  FactClaim,
  HeritageProject,
  MediaAsset,
  ReactionCounts,
  SourceCitation,
  TrustSummary,
} from "./types";
import { LOCAL_DEMO_WORKSPACE_ID } from "./types";

const CREATED_AT = "2026-10-01T00:00:00.000Z";
const CHECKED_AT = "2026-10-01T08:00:00.000Z";

function entity(id: string) {
  return {
    id,
    workspaceId: LOCAL_DEMO_WORKSPACE_ID,
    provenance: "local_demo" as const,
    createdAt: CREATED_AT,
    updatedAt: CREATED_AT,
  };
}

export const COMMUNITY_REGIONS: CommunityRegion[] = [
  { ...entity("region-guizhou"), slug: "guizhou", name: "贵州", province: "贵州省", summary: "以山地村落、节庆与多民族手工传统为线索的演示地区档案。", featuredCrafts: ["苗绣", "银饰", "古歌"], projectCount: 116 },
  { ...entity("region-yunnan"), slug: "yunnan", name: "云南", province: "云南省", summary: "从植物染、服饰与地方生活进入多样文化传统。", featuredCrafts: ["扎染", "银饰", "民族舞蹈"], projectCount: 128 },
  { ...entity("region-sichuan"), slug: "sichuan", name: "四川", province: "四川省", summary: "材料、器物与表演传统共同构成的地方文化景观。", featuredCrafts: ["竹编", "漆器", "川剧"], projectCount: 142 },
  { ...entity("region-jiangxi"), slug: "jiangxi", name: "江西", province: "江西省", summary: "以景德镇陶瓷文化为代表的材料与窑火档案。", featuredCrafts: ["陶瓷", "制瓷", "窑作"], projectCount: 101 },
  { ...entity("region-zhejiang"), slug: "zhejiang", name: "浙江", province: "浙江省", summary: "木作、青瓷与丝织传统的演示探索入口。", featuredCrafts: ["木作", "青瓷", "丝织"], projectCount: 135 },
  { ...entity("region-jiangsu"), slug: "jiangsu", name: "江苏", province: "江苏省", summary: "从精细手工到舞台表演的江南文化档案。", featuredCrafts: ["刺绣", "云锦", "昆曲"], projectCount: 121 },
  { ...entity("region-fujian"), slug: "fujian", name: "福建", province: "福建省", summary: "沿海地区器物、戏曲与生活技艺的演示集合。", featuredCrafts: ["木偶戏", "白瓷", "茶技"], projectCount: 109 },
  { ...entity("region-guangdong"), slug: "guangdong", name: "广东", province: "广东省", summary: "节庆、戏曲与民间造物共同延续的地方现场。", featuredCrafts: ["醒狮", "粤剧", "彩扎"], projectCount: 148 },
];

export const COMMUNITY_SOURCES: SourceCitation[] = [
  { ...entity("source-national-list"), title: "国家级非物质文化遗产代表性项目名录", publisher: "中国非物质文化遗产网", url: "https://www.ihchina.cn/", sourceLevel: "official", accessedAt: CHECKED_AT, note: "本地演示只保存来源索引；上线前应逐条核对项目页。" },
  { ...entity("source-guizhou-embroidery"), title: "贵州苗绣项目资料索引", publisher: "HAHA 演示资料库", sourceLevel: "institution", accessedAt: CHECKED_AT, note: "演示资料，不替代正式机构原文。" },
  { ...entity("source-jingdezhen-ceramics"), title: "景德镇传统制瓷技艺资料索引", publisher: "HAHA 演示资料库", sourceLevel: "institution", accessedAt: CHECKED_AT, note: "演示资料，不替代正式机构原文。" },
  { ...entity("source-bai-dyeing"), title: "白族扎染技艺资料索引", publisher: "HAHA 演示资料库", sourceLevel: "institution", accessedAt: CHECKED_AT, note: "演示资料，不替代正式机构原文。" },
  { ...entity("source-bamboo-weaving"), title: "道明竹编资料索引", publisher: "HAHA 演示资料库", sourceLevel: "institution", accessedAt: CHECKED_AT, note: "演示资料，不替代正式机构原文。" },
  { ...entity("source-field-notes"), title: "手艺人口述与现场记录（演示）", publisher: "HAHA 社区编辑部", sourceLevel: "interview", accessedAt: CHECKED_AT, note: "人物、引语与场景均为界面演示内容。" },
];

export const COMMUNITY_PROJECTS: HeritageProject[] = [
  { ...entity("project-miao-embroidery"), slug: "miao-embroidery", name: "苗绣", level: "national", category: "刺绣", regionIds: ["region-guizhou"], inheritorIds: ["person-ajin"], summary: "以针线、纹样与生活记忆为入口的项目演示档案。", materials: ["棉布", "丝线"], techniques: ["平绣", "挑花"], sourceIds: ["source-national-list", "source-guizhou-embroidery"], verificationStatus: "verified" },
  { ...entity("project-jingdezhen-ceramics"), slug: "jingdezhen-ceramics", name: "景德镇手工制瓷技艺", level: "national", category: "陶瓷", regionIds: ["region-jiangxi"], inheritorIds: ["person-nanqing"], summary: "围绕材料、成形、施釉与烧成组织的制瓷技艺演示档案。", materials: ["瓷石", "高岭土", "釉料"], techniques: ["拉坯", "利坯", "施釉", "烧成"], sourceIds: ["source-national-list", "source-jingdezhen-ceramics"], verificationStatus: "verified" },
  { ...entity("project-bai-dyeing"), slug: "bai-dyeing", name: "白族扎染技艺", level: "national", category: "染织", regionIds: ["region-yunnan"], inheritorIds: ["person-shanlan"], summary: "通过扎结、防染与染色观察纹样形成的演示项目档案。", materials: ["棉布", "植物染料"], techniques: ["扎花", "浸染", "拆线"], sourceIds: ["source-national-list", "source-bai-dyeing"], verificationStatus: "verified" },
  { ...entity("project-daoming-bamboo"), slug: "daoming-bamboo", name: "道明竹编", level: "national", category: "竹编", regionIds: ["region-sichuan"], inheritorIds: ["person-qingmie"], summary: "从选竹、破竹、分丝到编织的竹编演示项目档案。", materials: ["慈竹"], techniques: ["破竹", "分丝", "起底", "收口"], sourceIds: ["source-national-list", "source-bamboo-weaving"], verificationStatus: "verified" },
];

function avatar(id: string, mark: string, tone: NonNullable<MediaAsset["placeholder"]>["tone"]): MediaAsset {
  return { id, kind: "image", alt: `${mark}的本地演示头像`, placeholder: { mark, tone } };
}

export const COMMUNITY_PEOPLE: CommunityPerson[] = [
  { ...entity("person-ajin"), slug: "ajin-demo", displayName: "阿锦（演示人物）", role: "inheritor", avatar: avatar("asset-avatar-ajin", "锦", "red"), bio: "用于展示人物主页、关注和内容关联能力的本地虚构人物。", regionId: "region-guizhou", projectIds: ["project-miao-embroidery"], verified: true, demoLabel: "本地演示人物，并非真实人物档案" },
  { ...entity("person-nanqing"), slug: "nanqing-demo", displayName: "南青（演示人物）", role: "creator", avatar: avatar("asset-avatar-nanqing", "瓷", "blue"), bio: "记录材料、器物和窑火过程的本地演示创作者。", regionId: "region-jiangxi", projectIds: ["project-jingdezhen-ceramics"], verified: true, demoLabel: "本地演示人物，并非真实人物档案" },
  { ...entity("person-shanlan"), slug: "shanlan-demo", displayName: "山蓝（演示人物）", role: "creator", avatar: avatar("asset-avatar-shanlan", "染", "green"), bio: "用于演示植物染内容、评论和知识注释的虚构创作者。", regionId: "region-yunnan", projectIds: ["project-bai-dyeing"], verified: true, demoLabel: "本地演示人物，并非真实人物档案" },
  { ...entity("person-qingmie"), slug: "qingmie-demo", displayName: "青篾（演示人物）", role: "inheritor", avatar: avatar("asset-avatar-qingmie", "竹", "gold"), bio: "用于展示竹编项目和学习意向的本地虚构人物。", regionId: "region-sichuan", projectIds: ["project-daoming-bamboo"], verified: true, demoLabel: "本地演示人物，并非真实人物档案" },
];

const peopleById = new Map(COMMUNITY_PEOPLE.map((person) => [person.id, person]));
const regionsById = new Map(COMMUNITY_REGIONS.map((region) => [region.id, region]));
const sourcesById = new Map(COMMUNITY_SOURCES.map((source) => [source.id, source]));

const contentSpecs = [
  ["content-embroidery-01", "one-thread-to-distance", "short_video", "一根线，怎样绣出远方？", "跟随一双手，看纹样如何连接山川、生活与记忆。", "person-ajin", "embroidery", "刺绣", "region-guizhou", ["project-miao-embroidery"], ["person-ajin"], ["苗绣", "纹样", "人物故事"], 138, "绣", "red", 86000, 3214, "source-guizhou-embroidery", "苗绣内容需要把具体纹样解释与可核验来源绑定。"],
  ["content-ceramics-01", "sound-remembered-by-fire", "long_video", "泥土被火记住的声音", "从原料、成形到烧成，理解器物为什么需要等待。", "person-nanqing", "ceramics", "陶瓷", "region-jiangxi", ["project-jingdezhen-ceramics"], ["person-nanqing"], ["制瓷", "窑火", "材料"], 222, "陶", "green", 62000, 2038, "source-jingdezhen-ceramics", "制瓷过程由多道工序构成，具体工序数量随产品与口径不同。"],
  ["content-dyeing-01", "why-blue-cracks", "knowledge_card", "蓝染为什么会留下冰裂纹？", "用扎结和防染的过程解释纹样如何出现。", "person-shanlan", "dyeing", "染织", "region-yunnan", ["project-bai-dyeing"], ["person-shanlan"], ["扎染", "蓝染", "纹样"], 116, "染", "blue", 58000, 1926, "source-bai-dyeing", "扎结形成的防染区域会影响拆线后的纹样边界。"],
  ["content-bamboo-01", "bamboo-thread-forms", "process_tutorial", "竹丝在指尖慢慢成形", "观察选竹、分丝与编织动作，而不是只看成品。", "person-qingmie", "bamboo", "竹编", "region-sichuan", ["project-daoming-bamboo"], ["person-qingmie"], ["竹编", "工序", "材料"], 151, "编", "gold", 49000, 1488, "source-bamboo-weaving", "竹编内容应区分材料准备、编织和收口等不同环节。"],
  ["content-papercut-01", "life-inside-window-flower", "image_story", "窗花里藏着怎样的生活？", "从生活场景观察剪纸图案，而不替观众虚构唯一寓意。", "person-ajin", "papercut", "剪纸", "region-jiangsu", [], [], ["剪纸", "窗花", "生活"], 108, "剪", "red", 41000, 1125, "source-field-notes", "纹样含义受地区、使用场景与讲述者影响，不宜给出单一结论。"],
  ["content-opera-01", "three-minutes-backstage", "inheritor_story", "后台三分钟，台上一出戏", "从候场、整理和上场前的细节进入传统表演。", "person-nanqing", "opera", "戏曲", "region-fujian", [], [], ["戏曲", "后台", "人物"], 252, "戏", "blue", 37000, 986, "source-field-notes", "演示内容不指向具体剧种、人物或真实采访。"],
  ["content-woodwork-01", "mortise-without-nail", "knowledge_card", "一榫一卯，不用一枚钉", "用结构示意理解传统木作连接方式。", "person-qingmie", "woodwork", "木作", "region-zhejiang", [], [], ["木作", "榫卯", "结构"], 166, "木", "green", 32000, 842, "source-field-notes", "并非所有传统木构都完全不使用金属连接件，标题仅用于内容切入。"],
  ["content-folklore-01", "before-lion-dance", "short_video", "醒狮之前，人们在准备什么？", "把镜头移向表演之前的器具、协作与现场秩序。", "person-ajin", "folklore", "民俗", "region-guangdong", [], [], ["醒狮", "节庆", "现场"], 188, "俗", "gold", 29000, 771, "source-field-notes", "具体仪式与流程存在地区和团队差异。"],
  ["content-embroidery-02", "other-side-of-embroidery", "long_video", "双面绣的另一面是什么？", "从正反两面的关系理解精细刺绣的观看方式。", "person-ajin", "embroidery", "刺绣", "region-jiangsu", [], ["person-ajin"], ["刺绣", "双面绣", "细节"], 124, "针", "blue", 26000, 659, "source-field-notes", "本条为演示选题，正式发布前需补充对应项目来源。"],
  ["content-ceramics-02", "porcelain-cup-process", "process_tutorial", "一只白瓷杯经过哪些工序？", "用可核验的过程卡替代夸张的固定工序数字。", "person-nanqing", "ceramics", "陶瓷", "region-fujian", ["project-jingdezhen-ceramics"], ["person-nanqing"], ["白瓷", "工序", "器物"], 320, "瓷", "green", 24000, 612, "source-jingdezhen-ceramics", "工序划分取决于统计口径，不使用未经来源支持的固定数字。"],
] as const;

function reactionCounts(interactions: number): ReactionCounts {
  return {
    bookmark: Math.round(interactions * 0.28),
    want_to_learn: Math.round(interactions * 0.19),
    respect: Math.round(interactions * 0.45),
    watch_later: Math.round(interactions * 0.08),
  };
}

function trust(sourceCount: number): TrustSummary {
  return {
    status: "verified",
    label: "来源已核验（演示）",
    sourceCount,
    checkedAt: CHECKED_AT,
    aiAssisted: false,
  };
}

function cover(id: string, mark: string, tone: "red" | "green" | "blue" | "gold", durationSeconds: number): MediaAsset {
  return {
    id: `asset-${id}-cover`,
    kind: "image",
    alt: `${mark}主题演示封面`,
    durationSeconds,
    placeholder: { mark, tone },
  };
}

export const COMMUNITY_FACTS: FactClaim[] = contentSpecs.map((spec, index) => ({
  ...entity(`fact-${String(index + 1).padStart(2, "0")}`),
  contentId: spec[0],
  text: spec[18],
  status: "verified",
  sourceIds: [spec[17]],
  checkedAt: CHECKED_AT,
  note: "本地演示事实；真实发布仍需由服务端事实库和审核流程复核。",
}));

const factsByContentId = new Map(COMMUNITY_FACTS.map((fact) => [fact.contentId, fact]));

export const COMMUNITY_CONTENTS: ContentDetail[] = contentSpecs.map((spec, index) => {
  const [
    id, slug, contentType, title, summary, creatorId, categoryId, categoryLabel,
    regionId, projectIds, personIds, tags, durationSeconds, mark, tone,
    viewCount, interactionCount, sourceId,
  ] = spec;
  const creator = peopleById.get(creatorId);
  const region = regionsById.get(regionId);
  const source = sourcesById.get(sourceId);
  const claim = factsByContentId.get(id);
  if (!creator || !region || !source || !claim) throw new Error(`Invalid demo seed: ${id}`);
  const metrics: ContentMetrics = {
    viewCount,
    interactionCount,
    commentCount: Math.max(3, Math.round(interactionCount * 0.06)),
    bookmarkCount: Math.round(interactionCount * 0.28),
  };
  const publishedAt = new Date(Date.UTC(2026, 8, 28 - index)).toISOString();
  const mediaCover = cover(id, mark, tone, durationSeconds);
  return {
    ...entity(id),
    slug,
    contentType,
    title,
    summary,
    cover: mediaCover,
    creatorId,
    creator,
    categoryId,
    categoryLabel,
    regionId,
    regionLabel: region.name,
    projectIds: [...projectIds],
    personIds: [...personIds],
    tags: [...tags],
    durationSeconds,
    metrics,
    reactionCounts: reactionCounts(interactionCount),
    trust: trust(1),
    viewer: { reactions: [], followedCreator: false, viewed: false, watchProgressSeconds: 0 },
    publishedAt,
    body: `${summary}\n\n这是 HAHA 本地演示内容，用于疏通内容详情、可信来源和社区互动闭环。它不是已发布的真实人物采访或机构档案。`,
    media: [mediaCover],
    claims: [claim],
    sources: [source],
    relatedContentIds: [],
  };
});

for (const content of COMMUNITY_CONTENTS) {
  content.relatedContentIds = COMMUNITY_CONTENTS
    .filter((candidate) => candidate.id !== content.id && (
      candidate.categoryId === content.categoryId || candidate.regionId === content.regionId
    ))
    .slice(0, 3)
    .map((candidate) => candidate.id);
}

export interface CommunitySeed {
  contents: ContentDetail[];
  projects: HeritageProject[];
  people: CommunityPerson[];
  regions: CommunityRegion[];
  sources: SourceCitation[];
  facts: FactClaim[];
}

export const COMMUNITY_SEED: CommunitySeed = {
  contents: COMMUNITY_CONTENTS,
  projects: COMMUNITY_PROJECTS,
  people: COMMUNITY_PEOPLE,
  regions: COMMUNITY_REGIONS,
  sources: COMMUNITY_SOURCES,
  facts: COMMUNITY_FACTS,
};
