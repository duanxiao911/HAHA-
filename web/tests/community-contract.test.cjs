const assert = require("node:assert/strict");
const test = require("node:test");

const { createLocalCommunityAdapter } = require("../.contract-test-build/local-adapter.js");
const {
  COMMUNITY_PAGE_LIMIT_MAX,
  normalizeCommunityPageLimit,
} = require("../.contract-test-build/contract.js");

test("分页上限与服务端契约一致", () => {
  assert.equal(COMMUNITY_PAGE_LIMIT_MAX, 50);
  assert.equal(normalizeCommunityPageLimit(60), 50);
  assert.equal(normalizeCommunityPageLimit(0), 1);
  assert.equal(normalizeCommunityPageLimit(12.9), 12);
  assert.equal(normalizeCommunityPageLimit(), undefined);
});

test("本地社区适配器保持互动幂等并可撤销", async () => {
  const adapter = createLocalCommunityAdapter();
  adapter.hydrate();
  const contentId = adapter.getSnapshot().contents[0].id;
  const before = await adapter.getContent(contentId);

  const first = await adapter.setReaction(contentId, "bookmark", true);
  const repeated = await adapter.setReaction(contentId, "bookmark", true);
  assert.equal(first.reactionCounts.bookmark, before.reactionCounts.bookmark + 1);
  assert.equal(repeated.reactionCounts.bookmark, first.reactionCounts.bookmark);
  assert.deepEqual(repeated.viewer.reactions, ["bookmark"]);

  const removed = await adapter.setReaction(contentId, "bookmark", false);
  assert.equal(removed.reactionCounts.bookmark, before.reactionCounts.bookmark);
  assert.deepEqual(removed.viewer.reactions, []);
});

test("关注、正在学习与历史形成可查询闭环", async () => {
  const adapter = createLocalCommunityAdapter();
  adapter.hydrate();
  const content = adapter.getSnapshot().contents[0];

  await adapter.setPersonFollow(content.creatorId, true);
  const following = await adapter.getFeed({ mode: "following", limit: 50 });
  assert.ok(following.items.length > 0);
  assert.ok(following.items.every((item) => item.creatorId === content.creatorId));

  await adapter.setReaction(content.id, "want_to_learn", true);
  const learning = await adapter.getFeed({ mode: "learning", limit: 50 });
  assert.ok(learning.items.some((item) => item.id === content.id));

  await adapter.recordWatchHistory(content.id, 12);
  await adapter.recordWatchHistory(content.id, 31);
  const history = adapter.getSnapshot().history.filter((item) => item.contentId === content.id);
  assert.equal(history.length, 1);
  assert.equal(history[0].progressSeconds, 31);
});

test("搜索同时覆盖内容、项目、人物和地区", async () => {
  const adapter = createLocalCommunityAdapter();
  adapter.hydrate();
  const embroidery = await adapter.search({ query: "苗绣", scope: "all", limit: 50 });
  assert.ok(embroidery.items.some((item) => item.kind === "project"));
  assert.ok(embroidery.items.some((item) => item.kind === "content"));

  const guizhou = await adapter.search({ query: "贵州", scope: "all", limit: 50 });
  const region = guizhou.items.find((item) => item.kind === "region");
  assert.ok(region);
  assert.match(region.href, /^\/map\?region=/);
});

test("评论、时间点知识注释可以新增与回收", async () => {
  const adapter = createLocalCommunityAdapter();
  adapter.hydrate();
  const contentId = adapter.getSnapshot().contents[0].id;

  const comment = await adapter.createComment({ contentId, body: "材料处理过程很清楚。" });
  assert.ok(adapter.getSnapshot().comments.some((item) => item.id === comment.id));
  await adapter.deleteOwnComment(comment.id);
  assert.equal(adapter.getSnapshot().comments.find((item) => item.id === comment.id).status, "deleted");

  const annotation = await adapter.createTimedAnnotation({
    contentId,
    timestampSeconds: 18,
    body: "这里开始解释纹样来源。",
    kind: "term",
  });
  assert.equal(annotation.verificationStatus, "pending");
  await adapter.deleteOwnTimedAnnotation(annotation.id);
  assert.ok(!adapter.getSnapshot().annotations.some((item) => item.id === annotation.id));
});

test("投稿状态机阻止非法跳转并产生审核消息", async () => {
  const adapter = createLocalCommunityAdapter();
  adapter.hydrate();
  const seed = adapter.getSnapshot();
  let draft = await adapter.createSubmissionDraft({ submissionType: "article", title: "苗绣纹样记录" });
  draft = await adapter.updateSubmissionDraft(draft.id, {
    summary: "以材料和针法为线索的本地投稿演示。",
    projectIds: [seed.projects[0].id],
    sourceIds: [seed.sources[0].id],
    aiDisclosure: "assisted",
  });

  await assert.rejects(
    adapter.transitionSubmissionDraft(draft.id, "published"),
    (error) => error.code === "invalid_transition",
  );

  await adapter.transitionSubmissionDraft(draft.id, "checking");
  await adapter.transitionSubmissionDraft(draft.id, "submitted");
  await adapter.transitionSubmissionDraft(draft.id, "reviewing");
  await adapter.transitionSubmissionDraft(draft.id, "approved", "来源与披露检查完成。 ");
  const published = await adapter.transitionSubmissionDraft(draft.id, "published", "本地演示发布。 ");
  assert.equal(published.status, "published");
  assert.ok(adapter.getSnapshot().notifications.some((item) => item.kind === "review"));
});
