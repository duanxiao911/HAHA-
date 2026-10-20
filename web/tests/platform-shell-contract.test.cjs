const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const root = path.resolve(__dirname, "..");
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), "utf8");

test("desktop shell exposes exactly the four governed platform modules", () => {
  const source = read("components/community/AppHeader.tsx");
  const primaryBlock = source.match(/const primaryNavigation = \[(.*?)\] as const;/s)?.[1] ?? "";
  const links = [...primaryBlock.matchAll(/href: "([^"]+)", label: "([^"]+)"/g)].map((match) => match.slice(1));
  assert.deepEqual(links, [
    ["/community", "视频社区"],
    ["/commerce", "非遗电商"],
    ["/learning", "AI 学习"],
    ["/identity", "用户中心"],
  ]);
  assert.doesNotMatch(primaryBlock, /href: "\/"/);
  assert.match(source, /我的 HAHA/);
  assert.match(source, /专业工作台/);
  assert.doesNotMatch(source, /switchIdentityContext/);
  assert.doesNotMatch(source, /切换已开通身份/);
  assert.doesNotMatch(source, /管理与开通身份/);
  assert.match(source, /搜索非遗内容、项目、人物和地区/);
  assert.doesNotMatch(source, /搜索非遗内容、项目、人物和商品/);
  assert.match(source, /identityTriggerRef\.current\?\.focus\(\)/);
});

test("mobile shell uses home plus the four modules and no duplicate creator tab", () => {
  const source = read("components/community/MobileBottomNav.tsx");
  const navigationBlock = source.match(/const mobileNavigation = \[(.*?)\] as const;/s)?.[1] ?? "";
  const links = [...navigationBlock.matchAll(/href: "([^"]+)", label: "([^"]+)"/g)].map((match) => match.slice(1));
  assert.deepEqual(links, [
    ["/", "首页"],
    ["/community", "社区"],
    ["/learning", "学习"],
    ["/commerce", "电商"],
    ["/identity", "我的"],
  ]);
  assert.doesNotMatch(navigationBlock, /"\/creator", label: "创作"/);
});

test("root is a neutral platform home and community reuses the shared shell", () => {
  const rootPage = read("app/page.tsx");
  const home = read("app/PlatformHome.tsx");
  const community = read("app/community.tsx");
  assert.match(rootPage, /return <PlatformHome \/>/);
  assert.match(rootPage, /export default function HomePage/);
  assert.match(home, /FOUR CORE SPACES/);
  assert.match(home, /AI 非遗老师 · 受控能力/);
  assert.match(home, /AI 老师可用/);
  assert.match(home, /AI 老师受阻/);
  assert.match(home, /非遗电商 · INTERNAL SANDBOX/);
  assert.match(home, /identity-conversion-guide/);
  assert.match(home, /浏览、学习与购物不需要切换身份/);
  assert.doesNotMatch(home, /switchIdentityContext/);
  assert.match(community, /<ProductFrame className="communityV2"/);
  assert.doesNotMatch(community, /className="globalHeader"/);
  assert.doesNotMatch(community, /href="\/creator">AI 学习/);
});

test("account center separates ordinary capabilities from professional workbenches", () => {
  const source = read("app/identity/IdentityCenter.tsx");
  assert.match(source, /专业工作台/);
  assert.match(source, /普通功能不需要切换身份/);
  assert.match(source, /内部权限不会出现在这里/);
  assert.match(source, /审核员和管理员由平台内部邀请/);
  assert.match(source, /const professionalRoles = new Set<BusinessRole>\(\[\s*"creator", "contributor", "seller",\s*\]\)/);
  assert.match(source, /searchParams\.get\("manage"\) === "roles"/);
  assert.match(source, /confirmLabel: "确认开通"/);
});
