"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { ConfirmDialog } from "@/components/community/ConfirmDialog";
import { ProductFrame } from "@/components/community/ProductFrame";
import { StateNotice } from "@/components/community/StateNotice";
import {
  ApiRequestError,
  askLearningTutor,
  completeLearningUnit,
  enrollLearningPath,
  getLearningCenter,
  LearningSnapshot,
  saveLearningKnowledgeCard,
  submitLearningContribution,
  submitLearningQuiz,
} from "@/lib/api";

import styles from "./learning.module.css";

type ViewState = "loading" | "success" | "error" | "forbidden";

function errorMessage(cause: unknown): string {
  return cause instanceof Error ? cause.message : "学习中心暂时不可用";
}

export function LearningCenter() {
  const [state, setState] = useState<ViewState>("loading");
  const [snapshot, setSnapshot] = useState<LearningSnapshot | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [feedback, setFeedback] = useState("");
  const [cardTopic, setCardTopic] = useState("来源与可信状态");
  const [cardBody, setCardBody] = useState("");
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [candidateId, setCandidateId] = useState("");
  const [tutorQuestion, setTutorQuestion] = useState("");
  const [pendingUnit, setPendingUnit] = useState<{ id: string; title: string; version: number } | null>(null);
  const [contribution, setContribution] = useState({ topic: "", body: "", sourceTitle: "", sourceUrl: "", sourceVersion: "网页访问日期" });

  const applySnapshot = useCallback((next: LearningSnapshot) => {
    setSnapshot(next);
    setState("success");
    const firstCard = next.cards[0];
    if (firstCard) {
      setCardTopic(firstCard.topic);
      setCardBody(firstCard.body);
    }
    setCandidateId((current) => current || next.learning_candidates[0]?.target_id || "");
  }, []);

  const applyLoadError = useCallback((cause: unknown) => {
    setError(errorMessage(cause));
    setState(cause instanceof ApiRequestError && (cause.status === 401 || cause.status === 403) ? "forbidden" : "error");
  }, []);

  const load = useCallback(async () => {
    setState("loading");
    setError("");
    try {
      applySnapshot(await getLearningCenter());
    } catch (cause) {
      applyLoadError(cause);
    }
  }, [applyLoadError, applySnapshot]);

  useEffect(() => {
    let active = true;
    void getLearningCenter()
      .then((next) => { if (active) applySnapshot(next); })
      .catch((cause: unknown) => { if (active) applyLoadError(cause); });
    return () => { active = false; };
  }, [applyLoadError, applySnapshot]);

  async function run(key: string, action: () => Promise<LearningSnapshot>, message: string): Promise<boolean> {
    setBusy(key);
    setFeedback("");
    try {
      applySnapshot(await action());
      setFeedback(message);
      return true;
    } catch (cause) {
      setFeedback(errorMessage(cause));
      return false;
    } finally {
      setBusy("");
    }
  }

  if (state === "loading") {
    return <ProductFrame><StateNotice kind="loading" title="正在恢复学习档案" description="读取服务端路径、进度、任务和成长记录。" /></ProductFrame>;
  }
  if (state === "forbidden") {
    return <ProductFrame><StateNotice kind="forbidden" title="需要学习者身份" description="学习 API 会核验持久化 learner 授权，切换前端参数不会获得权限。" actionLabel="去开通学习者" actionHref="/identity" /></ProductFrame>;
  }
  if (state === "error" || !snapshot) {
    return <ProductFrame><StateNotice kind="error" title="学习中心没有加载完成" description={error || "服务端没有返回学习档案。"} actionLabel="重试" onAction={() => void load()} /></ProductFrame>;
  }

  const activePath = snapshot.paths.find((item) => item.enrollment) ?? snapshot.paths[0];
  const lessonUnit = activePath?.units.find((item) => item.kind === "lesson");
  const savedCard = lessonUnit ? snapshot.cards.find((item) => item.unit_id === lessonUnit.id) : undefined;
  const cardDirty = Boolean(lessonUnit) && (
    cardTopic !== (savedCard?.topic ?? "来源与可信状态")
    || cardBody !== (savedCard?.body ?? "")
  );

  function resetCard() {
    setCardTopic(savedCard?.topic ?? "来源与可信状态");
    setCardBody(savedCard?.body ?? "");
  }

  function submitCard(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!lessonUnit) return;
    void run(
      "card",
      () => saveLearningKnowledgeCard(lessonUnit.id, cardTopic, cardBody, savedCard?.version ?? 0),
      savedCard ? "知识卡新版本已保存。" : "知识卡已保存，并记录真实学习事件。",
    );
  }

  function submitTutorQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const question = tutorQuestion.trim();
    if (question.length < 2 || snapshot?.ai_tutor.status !== "available") return;
    void run(
      "tutor",
      () => askLearningTutor(question),
      "AI 非遗老师已返回带来源的回答。",
    ).then((success) => { if (success) setTutorQuestion(""); });
  }

  const latestTutor = snapshot.last_tutor_result ?? snapshot.tutor_history[0];

  return <ProductFrame mainClassName={styles.main}>
    <section className={styles.hero} data-testid="learning-hero">
      <div>
        <small>LEARNING & GROWTH</small>
        <h1>学习成长中心</h1>
        <p>路径、进度、答题、每日任务与成就均由服务端保存；页面刷新不会成为新的事实源。</p>
      </div>
      <div className="learningHeroActions">
        <a className="productButton" href={activePath?.enrollment ? "#learning-workspace" : "#learning-paths"}>{activePath?.enrollment ? "继续学习" : "查看学习路径"}</a>
        <Link className="productButtonSecondary" href="/identity?tab=archive">查看用户中心成长汇总</Link>
      </div>
    </section>

    <section className={styles.metricGrid} aria-label="学习成长摘要">
      <article><b>{snapshot.summary.completed_units}</b><span>已完成节点</span></article>
      <article><b>{snapshot.summary.current_streak}</b><span>连续学习天数</span></article>
      <article><b>{snapshot.summary.achievements}</b><span>已获成就</span></article>
      <article><b>{snapshot.summary.achievement_points}</b><span>成长积分</span></article>
    </section>

    <nav className="learningJumpNav" aria-label="学习中心页内导航">
      <a href="#daily-learning">每日任务</a>
      <a href="#ai-tutor">AI 非遗老师</a>
      <a href="#learning-paths">学习路径</a>
      {activePath?.enrollment ? <a href="#learning-workspace">知识与测验</a> : null}
      <a href="#learning-achievements">成长成就</a>
      <a href="#knowledge-contributions">知识贡献</a>
    </nav>

    {snapshot.ai_tutor.status === "blocked" ? <section className={styles.boundary} data-testid="ai-tutor-boundary" id="ai-tutor">
      <span>BLOCKED</span>
      <div><h2>AI 非遗老师尚未接通</h2><p>{snapshot.ai_tutor.reason}</p></div>
    </section> : <section className={styles.tutorPanel} data-testid="ai-tutor" id="ai-tutor">
      <div className={styles.tutorIntro}>
        <div><small>GROUNDED AI TUTOR</small><h2>AI 非遗老师</h2><p>{snapshot.ai_tutor.supported_scope}</p></div>
        <span>DeepSeek · {snapshot.ai_tutor.knowledge_version} · {snapshot.ai_tutor.request_limit_24h} 次/24h</span>
      </div>
      <form className={styles.tutorForm} onSubmit={submitTutorQuestion}>
        <label htmlFor="tutor-question">想了解什么？</label>
        <div className={styles.tutorInputRow}>
          <textarea id="tutor-question" value={tutorQuestion} minLength={2} maxLength={1000} required placeholder="请写出完整项目名称，例如：中国剪纸有哪些主要特点？" onChange={(event) => setTutorQuestion(event.target.value)} />
          <button className="productButton" type="submit" disabled={busy === "tutor" || tutorQuestion.trim().length < 2}>{busy === "tutor" ? "查找来源并回答中…" : "提问"}</button>
        </div>
        <div className={styles.tutorSuggestions} aria-label="示例问题">
          {["中国剪纸有哪些主要特点？", "昆曲的表演特点是什么？"].map((item) => <button type="button" key={item} onClick={() => setTutorQuestion(item)}>{item}</button>)}
        </div>
      </form>
      {latestTutor ? <article className={styles.tutorAnswer} aria-live="polite">
        <small>{latestTutor.mode === "no_sources" ? "未命中可信来源 · 未调用模型" : `真实模型回答 · ${latestTutor.model}`}</small>
        <h3>{latestTutor.question}</h3>
        <p>{latestTutor.answer}</p>
        {latestTutor.uncertainty ? <div className={styles.uncertainty}>边界说明：{latestTutor.uncertainty}</div> : null}
        {latestTutor.citations.length ? <ul className={styles.citationList}>{latestTutor.citations.map((source) => <li key={source.source_id}><div><b>[{source.source_id}] {source.title}</b><span>{source.publisher} · {source.version} · 内部已核验</span></div><a href={source.url} target="_blank" rel="noreferrer">打开来源入口</a></li>)}</ul> : null}
        <p className={styles.tutorDisclaimer}>回答只引用当前版本化目录；“内部已核验”不等于官方认证，正式使用前请打开具体官方资料复核。</p>
      </article> : <StateNotice kind="empty" compact title="还没有提问记录" description="老师只回答能精确命中来源记录的问题；未命中时会明确拒答，不会用模型常识补写。" />}
    </section>}
    <p className={styles.catalogNotice}>{snapshot.catalog_notice}</p>

    <div className={styles.dashboardGrid}>
      <section className={styles.panel} data-testid="daily-learning-tasks" id="daily-learning">
        <header><small>TODAY</small><h2>每日任务</h2><p>只由已持久化学习事件推进。</p></header>
        <ul className={styles.taskList}>{snapshot.daily_tasks.map((task) => <li className={task.status === "completed" ? styles.done : ""} key={task.id}><span>{task.status === "completed" ? "✓" : "○"}</span><div><b>{task.title}</b><small>{task.current_count} / {task.target_count}</small></div></li>)}</ul>
      </section>
      <section className={styles.panel}>
        <header><small>WANT TO LEARN</small><h2>想学候选</h2><p>直接读取统一账户资产，不复制归属。</p></header>
        {snapshot.learning_candidates.length ? <><select aria-label="关联想学内容" value={candidateId} onChange={(event) => setCandidateId(event.target.value)}>{snapshot.learning_candidates.map((item) => <option value={item.target_id} key={item.id}>{item.title}</option>)}</select><ul className={styles.candidateList}>{snapshot.learning_candidates.slice(0, 3).map((item) => <li key={item.id}><Link href={item.target_href || "/"}>{item.title}</Link><span>账户资产</span></li>)}</ul></> : <StateNotice kind="empty" compact title="想学清单为空" description="在社区内容详情点击“想学”后，会出现在这里。" actionLabel="发现内容" actionHref="/" />}
      </section>
    </div>

    <section className={styles.pathSection} data-testid="learning-paths" id="learning-paths">
      <header className={styles.sectionHeading}><div><small>LEARNING PATHS</small><h2>学习路径与知识节点</h2><p>每个节点都保留目录版本、来源和进度版本。</p></div></header>
      {snapshot.paths.length ? snapshot.paths.map((path) => <article className={styles.pathCard} key={path.id}>
        <div className={styles.pathSummary}>
          <div><span className={styles.trust}>{path.verification_status === "demo_only" ? "内部演示 · 非权威认定" : path.verification_status}</span><h3>{path.title}</h3><p>{path.summary}</p><small>{path.source_note}</small></div>
          <div className={styles.progressBadge}><b>{path.completion_percent}%</b><span>{path.enrollment ? (path.enrollment.status === "completed" ? "路径完成" : "学习中") : "未加入"}</span></div>
        </div>
        {!path.enrollment ? <button className="productButton" type="button" disabled={Boolean(busy)} onClick={() => void run(`enroll-${path.id}`, () => enrollLearningPath(path.id, candidateId), "学习路径已加入。")}>加入学习路径</button> : null}
        <ol className={styles.unitList}>{path.units.map((unit) => <li className={unit.progress.status === "completed" ? styles.unitDone : ""} key={unit.id}>
          <span>{unit.progress.status === "completed" ? "✓" : unit.position}</span><div><small>{unit.kind === "quiz" ? "测验" : "课程节点"} · v{unit.version} · {unit.estimated_minutes} 分钟</small><h3>{unit.title}</h3><p>{unit.summary}</p><em>进度 {unit.progress.progress_percent}% · {unit.progress.status === "completed" ? "已完成" : unit.progress.status === "in_progress" ? "学习中" : "未开始"} · 记录版本 {unit.progress.version}</em></div>
          {path.enrollment && unit.kind === "lesson" && unit.progress.status !== "completed" ? <button className="productButtonSecondary" type="button" disabled={Boolean(busy)} onClick={() => setPendingUnit({ id: unit.id, title: unit.title, version: unit.progress.version })}>完成节点</button> : null}
        </li>)}</ol>
      </article>) : <StateNotice kind="empty" title="暂无学习路径" description="服务端尚未发布可用路径。" />}
    </section>

    {activePath?.enrollment && lessonUnit ? <section className={styles.workspaceGrid} id="learning-workspace">
      <form className={styles.panel} onSubmit={submitCard} data-testid="knowledge-card-form">
        <header><small>KNOWLEDGE CARD</small><h2>知识卡片</h2><p>来源、来源版本、可信状态和卡片版本随记录保存。</p><span className={cardDirty ? "learningSaveState is-unsaved" : "learningSaveState is-saved"}>{cardDirty ? "有未保存的更改" : savedCard ? "已保存" : "尚未填写"}</span></header>
        <label>主题<input value={cardTopic} maxLength={200} required onChange={(event) => setCardTopic(event.target.value)} /></label>
        <label>学习笔记<textarea value={cardBody} maxLength={4000} required placeholder="记录你确认了什么，以及哪些内容仍待核验。" onChange={(event) => setCardBody(event.target.value)} /></label>
        <div className={styles.sourceMeta}><span>来源：{snapshot.sources.find((item) => item.id === lessonUnit.source_id)?.title}</span><span>可信状态：{snapshot.sources.find((item) => item.id === lessonUnit.source_id)?.verification_status}</span><span>卡片版本：{savedCard?.version ?? 0}</span></div>
        <div className="learningFormActions"><button className="productButtonSecondary" type="button" disabled={!cardDirty || busy === "card"} onClick={resetCard}>{savedCard ? "还原已保存版本" : "清空"}</button><button className="productButton" type="submit" disabled={!cardDirty || busy === "card"}>{busy === "card" ? "保存中…" : savedCard ? "保存新版本" : "保存知识卡"}</button></div>
      </form>
      {activePath.units.filter((unit) => unit.quiz).map((unit) => <form className={styles.panel} key={unit.id} onSubmit={(event) => { event.preventDefault(); if (!unit.quiz) return; void run(`quiz-${unit.quiz.id}`, () => submitLearningQuiz(unit.quiz!.id, answers, unit.progress.version), "测验已由服务端判定并保存。"); }} data-testid="quiz-form">
        <header><small>SERVER-GRADED QUIZ</small><h2>{unit.quiz?.title}</h2><p>及格线 {unit.quiz?.pass_score} 分；答案和题目版本会形成不可变快照。</p><span className="learningAnswerProgress">已作答 {unit.quiz?.questions.filter((question) => answers[question.id] !== undefined).length ?? 0} / {unit.quiz?.questions.length ?? 0}</span></header>
        {unit.quiz?.questions.map((question) => <fieldset key={question.id}><legend>{question.position}. {question.prompt}</legend>{question.choices.map((choice, index) => <label className={styles.choice} key={choice}><input type="radio" name={question.id} checked={answers[question.id] === index} required onChange={() => setAnswers((current) => ({ ...current, [question.id]: index }))} /><span>{choice}</span></label>)}</fieldset>)}
        <div className="learningFormActions"><button className="productButtonSecondary" type="button" disabled={!unit.quiz?.questions.some((question) => answers[question.id] !== undefined) || Boolean(busy)} onClick={() => setAnswers((current) => { const next = { ...current }; unit.quiz?.questions.forEach((question) => delete next[question.id]); return next; })}>清空作答</button><button className="productButton" type="submit" disabled={Boolean(busy)}>{busy === `quiz-${unit.quiz?.id}` ? "提交中…" : "提交答案"}</button></div>
        {snapshot.last_quiz_result ? <p className={snapshot.last_quiz_result.passed ? styles.quizPassed : styles.quizFailed}>最近结果：{snapshot.last_quiz_result.score} 分 · {snapshot.last_quiz_result.passed ? "通过" : "未通过"}</p> : null}
      </form>)}
    </section> : null}

    <section className={styles.panel} data-testid="learning-achievements" id="learning-achievements">
      <header><small>ACHIEVEMENTS</small><h2>成长成就</h2><p>每个定义只授予一次，并保留触发事件和规则版本。</p></header>
      {snapshot.achievements.length ? <ul className={styles.achievementList}>{snapshot.achievements.map((item) => <li key={item.id}><span>✦</span><div><h3>{item.title}</h3><p>{item.description}</p><small>规则 v{item.definition_version} · {item.points} 分</small></div></li>)}</ul> : <StateNotice kind="empty" compact title="还没有成就" description="完成真实学习事件后，符合规则的成就会幂等授予。" />}
    </section>
    <section className={styles.panel} data-testid="knowledge-contributions" id="knowledge-contributions">
      <header><small>KNOWLEDGE GOVERNANCE</small><h2>知识贡献</h2><p>提交内容先进入隔离审核区；未经内部审核员批准，不会进入可信知识或 AI 老师检索范围。</p></header>
      <form onSubmit={(event) => { event.preventDefault(); void run("contribution", () => submitLearningContribution(contribution.topic, contribution.body, contribution.sourceTitle, contribution.sourceUrl, contribution.sourceVersion), "知识贡献已提交审核，不代表内容已获认可。") .then((success) => { if (success) setContribution({ topic: "", body: "", sourceTitle: "", sourceUrl: "", sourceVersion: "网页访问日期" }); }); }}>
        <label>主题<input required maxLength={200} value={contribution.topic} onChange={(event) => setContribution((current) => ({ ...current, topic: event.target.value }))} /></label>
        <label>待核验内容<textarea required maxLength={4000} value={contribution.body} onChange={(event) => setContribution((current) => ({ ...current, body: event.target.value }))} /></label>
        <label>来源标题<input required maxLength={300} value={contribution.sourceTitle} onChange={(event) => setContribution((current) => ({ ...current, sourceTitle: event.target.value }))} /></label>
        <label>来源链接<input required type="url" maxLength={1000} placeholder="https://…" value={contribution.sourceUrl} onChange={(event) => setContribution((current) => ({ ...current, sourceUrl: event.target.value }))} /></label>
        <label>来源版本或访问日期<input required maxLength={100} value={contribution.sourceVersion} onChange={(event) => setContribution((current) => ({ ...current, sourceVersion: event.target.value }))} /></label>
        <button className="productButton" type="submit" disabled={busy === "contribution"}>{busy === "contribution" ? "提交中…" : "提交审核"}</button>
      </form>
      {(snapshot.knowledge_contributions ?? []).length ? <ul className={styles.achievementList}>{snapshot.knowledge_contributions.map((item) => <li key={item.id}><span>{item.status === "approved" ? "✓" : item.status === "rejected" ? "×" : "○"}</span><div><h3>{item.topic}</h3><p>{item.source_title} · {item.source_version}</p><small>{item.status === "submitted" ? "待审核 · 尚未进入可信知识" : item.status === "approved" ? "已审核通过" : `未通过：${item.reviewer_note}`}</small></div></li>)}</ul> : <StateNotice kind="empty" compact title="还没有知识贡献" description="提交时必须附来源；审核通过前始终与可信知识隔离。" />}
    </section>
    <ConfirmDialog open={Boolean(pendingUnit)} title="确认完成这个学习节点？" description={pendingUnit ? `“${pendingUnit.title}”完成后会写入学习事件、更新每日任务与成就，当前版本不提供撤销。` : ""} confirmLabel="确认完成节点" busy={Boolean(pendingUnit && busy === `unit-${pendingUnit.id}`)} tone="primary" onCancel={() => setPendingUnit(null)} onConfirm={() => { if (!pendingUnit) return; void run(`unit-${pendingUnit.id}`, () => completeLearningUnit(pendingUnit.id, pendingUnit.version), "学习节点已完成。").then((success) => { if (success) setPendingUnit(null); }); }} />
    {feedback ? <div className="productToast" role="status">{feedback}</div> : null}
  </ProductFrame>;
}

export default LearningCenter;
