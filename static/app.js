/* ============================================================
 * 科目一 · 学员端 SPA（原生 JS，无依赖）
 * ============================================================ */
"use strict";

/* ---------- 基础工具 ---------- */
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s == null ? "" : s)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;");

async function api(path, opts = {}) {
  const res = await fetch(path, {
    method: opts.method || (opts.body ? "POST" : "GET"),
    headers: opts.body ? { "Content-Type": "application/json" } : {},
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "网络异常，请重试");
  return data;
}
const withUid = (p) => p + (p.includes("?") ? "&" : "?") + "user_id=" + State.user.id;
const fmtDate = (iso) => {
  if (!iso) return "";
  const d = new Date(iso), p = (n) => String(n).padStart(2, "0");
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
};
const toast = (msg) => {
  const t = document.createElement("div");
  t.className = "toast"; t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 1800);
};

/* ---------- 全局状态 ---------- */
const State = {
  user: JSON.parse(localStorage.getItem("km1_user") || "null"),
  practice: null,       // {list, idx, chapterName}
  wrong: { scope: "active", items: null },
  redo: null,           // {list, idx}
  exam: null,           // 进行中的考试运行时
};

/* ---------- 路由 ---------- */
function go(hash) { location.hash = hash; }
function route() {
  const h = location.hash.replace(/^#/, "") || "/";
  const [path, query] = h.split("?");
  const parts = path.split("/").filter(Boolean); // ['practice','ch1']
  window.scrollTo(0, 0);
  if (!State.user) return renderLogin();
  if (parts.length === 0) return renderHome();
  if (parts[0] === "chapters") return renderChapters();
  if (parts[0] === "practice") return renderPractice(parts[1]);
  if (parts[0] === "wrong") return renderWrongList();
  if (parts[0] === "redo") return renderRedo();
  if (parts[0] === "mock") return renderMockHome();
  if (parts[0] === "exam") return renderExam(parts[1]);
  if (parts[0] === "result") return renderResult(parts[1]);
  if (parts[0] === "review") return renderReview(parts[1]);
  renderHome();
}
window.addEventListener("hashchange", route);

/* ---------- 框架 ---------- */
function shell(contentHtml, active) {
  const tabs = [
    { k: "/", ico: "🏠", t: "首页" },
    { k: "/chapters", ico: "📚", t: "章节" },
    { k: "/wrong", ico: "📝", t: "错题" },
    { k: "/mock", ico: "🎯", t: "模拟" },
  ].map(t => `<a class="tab ${active === t.k ? "active" : ""}" href="#${t.k}">
      <span class="ico">${t.ico}</span>${t.t}</a>`).join("");
  return `<div class="app">${contentHtml}<nav class="tabbar">${tabs}</nav></div>`;
}
function topbar(title) {
  return `<div class="topbar"><h1>${title}</h1>
    <div class="me"><span class="avatar">${esc((State.user.name || "?")[0])}</span>${esc(State.user.name)}</div></div>`;
}
function mount(html) { $("#root").innerHTML = html; }

/* ---------- 登录 ---------- */
function renderLogin() {
  mount(`<div class="login-wrap">
    <div class="login-logo">🚗</div>
    <div class="login-title">科目一模拟考试</div>
    <div class="login-sub">碎片时间刷一刷，考试心里不慌</div>
    <div class="login-card">
      <label>输入你的姓名登录</label>
      <input id="loginName" placeholder="如：李雷" autocomplete="off">
      <button class="btn btn-primary" id="loginBtn">登录 / 注册</button>
      <div class="login-hint">演示账号（点击直接填入）：<br>
        <b id="quick1">李雷</b>（待加强） · <b id="quick2">韩梅梅</b>（临界线）<br>
        新姓名将自动注册为学员</div>
    </div>
  </div>`);
  const input = $("#loginName");
  const doLogin = async () => {
    const name = input.value.trim();
    if (!name) return toast("请输入姓名");
    try {
      const u = await api("/api/users", { body: { name, role: "student" } });
      State.user = u;
      localStorage.setItem("km1_user", JSON.stringify(u));
      go("/"); route();
    } catch (e) { toast(e.message); }
  };
  $("#loginBtn").onclick = doLogin;
  input.onkeydown = (e) => { if (e.key === "Enter") doLogin(); };
  $("#quick1").onclick = () => { input.value = "李雷"; };
  $("#quick2").onclick = () => { input.value = "韩梅梅"; };
}

/* ---------- 首页 ---------- */
async function renderHome() {
  mount(shell(topbar("驾考刷题"), "/"));
  const root = $(".app");
  root.insertAdjacentHTML("beforeend", `<div class="page" id="pageBody"><div class="loading">加载中…</div></div>`);
  const [ov, chapters, wrongCount] = await Promise.all([
    api(withUid("/api/overview")),
    api(withUid("/api/chapters")),
    api(withUid("/api/wrong")).then(d => d.length).catch(() => 0),
  ]);
  const today = new Date(), week = "日一二三四五六"[today.getDay()];
  const greet = `你好，${esc(State.user.name)}`;
  const masteredAll = chapters.reduce((s, c) => s + c.mastered, 0);
  const totalAll = chapters.reduce((s, c) => s + c.total, 0);
  $("#pageBody").innerHTML = `
    <div class="hello">${greet}<span class="date">今天是星期${week}，刷 10 分钟也是进步 💪</span></div>
    <div class="stat-grid">
      <div class="stat"><b class="blue">${Math.round(ov.accuracy * 100)}%</b><span>答题正确率</span></div>
      <div class="stat"><b class="red">${ov.active_wrong}</b><span>待攻克错题</span></div>
      <div class="stat"><b class="green">${ov.latest_score ?? "--"}</b><span>最近模拟分</span></div>
    </div>
    <div class="big-actions">
      <button class="action-tile" id="goWrong">
        <span class="emo">📝</span><b>错题重做</b>
        <span>错哪补哪，最高效</span>
        ${wrongCount ? `<span class="badge">${wrongCount}</span>` : ""}
      </button>
      <button class="action-tile" id="goMock">
        <span class="emo">🎯</span><b>全真模拟</b>
        <span>45分钟 · 90分合格</span>
      </button>
    </div>
    <div class="section-title">章节练习 <span class="muted">已掌握 ${masteredAll}/${totalAll}</span></div>
    ${chapters.map((c, i) => chapterCardHtml(c, i + 1)).join("")}
    ${ov.weak_tags.length ? `
    <div class="section-title">你的易错法规</div>
    <div class="card">${ov.weak_tags.map(t => `<span class="tag warn">${esc(t.tag)} · ${t.count}次</span>`).join("")}
      <div class="muted" style="margin-top:8px">这些标签的题最容易栽，点「错题重做」集中消灭。</div></div>` : ""}
    <button class="btn btn-ghost" id="logoutBtn" style="margin-top:8px">退出登录</button>`;
  $("#goWrong").onclick = () => go("/wrong");
  $("#goMock").onclick = () => go("/mock");
  $("#logoutBtn").onclick = () => {
    localStorage.removeItem("km1_user"); State.user = null;
    location.hash = ""; mount(""); route();
  };
  root.querySelectorAll("[data-ch]").forEach(el =>
    el.onclick = () => go("/practice/" + el.dataset.ch));
}
function chapterCardHtml(c, idx) {
  return `<div class="card chapter-item" data-ch="${c.id}" style="cursor:pointer">
    <div class="chapter-idx">${idx}</div>
    <div class="chapter-main">
      <b>${esc(c.name)}</b>
      <span class="small">${esc(c.description)}</span>
      <div class="progress"><i style="width:${Math.round(c.progress * 100)}%"></i></div>
    </div>
    <div class="small" style="text-align:right;flex:none">${c.mastered}/${c.total}<br><span class="chev">›</span></div>
  </div>`;
}

/* ---------- 章节列表 ---------- */
async function renderChapters() {
  mount(shell(topbar("章节练习"), "/chapters"));
  $("#root .app").insertAdjacentHTML("beforeend",
    `<div class="page"><div class="loading">加载中…</div></div>`);
  const chapters = await api(withUid("/api/chapters"));
  $("#root .page").innerHTML =
    `<div class="muted" style="margin:0 2px 10px">按顺序逐章攻克，做过的题会记录对错状态</div>` +
    chapters.map((c, i) => chapterCardHtml(c, i + 1)).join("");
  document.querySelectorAll("[data-ch]").forEach(el =>
    el.onclick = () => go("/practice/" + el.dataset.ch));
}

/* ---------- 做题通用组件 ---------- */
function optionLetter(i) { return ["A", "B", "C", "D", "E", "F"][i]; }
function typeLabel(t) { return t === "judge" ? "判断题" : "单选题"; }

function questionCardHtml(q, selected, graded, answer, idxText) {
  const opts = q.options.map((op, i) => {
    let cls = "opt";
    if (selected === i) cls += " sel";
    if (graded) {
      if (i === answer) cls += " correct";
      else if (i === selected) cls += " wrong";
      cls += " disabled";
    }
    return `<button class="${cls}" data-i="${i}">
      <span class="key">${optionLetter(i)}</span><span>${esc(op)}</span></button>`;
  }).join("");
  return `<div class="quiz-head"><span class="quiz-pos">${idxText || ""}</span></div>
    <div><span class="q-type">${typeLabel(q.type)}</span>
      ${(q.tags || []).map(t => `<span class="tag gray">${esc(t)}</span>`).join("")}</div>
    <div class="q-stem">${esc(q.stem)}</div>
    <div id="optBox">${opts}</div>
    <div id="explainSlot"></div>`;
}

/* ---------- 章节练题 ---------- */
async function renderPractice(chId) {
  mount(shell("", "/chapters"));
  $("#root .app").insertAdjacentHTML("beforeend",
    `<div class="page"><div class="loading">题目加载中…</div></div>`);
  let data;
  try { data = await api(withUid("/api/practice/" + chId)); }
  catch (e) { $("#root .page").innerHTML = `<div class="empty">${esc(e.message)}</div>`; return; }
  State.practice = { list: data.questions, idx: 0, name: data.chapter.name, chId, ans: {} };
  drawPracticeQuestion();
}
function drawPracticeQuestion() {
  const P = State.practice;
  const q = P.list[P.idx];
  const graded = P.ans[q.id] && P.ans[q.id].graded;
  const saved = P.ans[q.id];
  mount(shell("", "/chapters"));
  $("#root .app").innerHTML = `<div class="page">
    <div class="quiz-head">
      <button class="back" id="backBtn">‹</button>
      <span class="t">${esc(P.name)}</span>
      <span class="quiz-pos">${P.idx + 1}/${P.list.length}</span>
    </div>
    ${questionCardHtml(q, saved ? saved.selected : null, !!graded,
        graded ? saved.answer : null)}
    <div class="quiz-foot">
      ${P.idx > 0 ? `<button class="btn btn-ghost" id="prevBtn">上一题</button>` : ""}
      <button class="btn btn-primary" id="nextBtn">${P.idx === P.list.length - 1 ? "完成本章" : "下一题"}</button>
    </div>
  </div>`;
  if (graded) showPracticeExplain(q, saved, true);
  $("#backBtn").onclick = () => go("/chapters");
  $("#root").querySelectorAll("#optBox .opt").forEach(btn => {
    btn.onclick = () => answerPractice(q, Number(btn.dataset.i));
  });
  if ($("#prevBtn")) $("#prevBtn").onclick = () => { P.idx--; drawPracticeQuestion(); };
  $("#nextBtn").onclick = () => {
    if (P.idx === P.list.length - 1) {
      toast("本章练习完成 🎉"); go("/chapters");
    } else { P.idx++; drawPracticeQuestion(); }
  };
}
async function answerPractice(q, selected) {
  const P = State.practice;
  try {
    const r = await api("/api/answers/chapter",
      { body: { user_id: State.user.id, question_id: q.id, selected } });
    P.ans[q.id] = { selected, graded: true, ...r };
    drawPracticeQuestion();
  } catch (e) { toast(e.message); }
}
function showPracticeExplain(q, saved, noAnimate) {
  const r = saved;
  const slot = $("#explainSlot");
  if (!slot) return;
  slot.innerHTML = `<div class="explain ${r.is_correct ? "ok" : "no"}">
    <b>${r.is_correct ? "✅ 回答正确" : "❌ 答错了，正确答案是 " + optionLetter(r.answer)}</b>
    <span class="human">${esc(r.explanation)}</span></div>`;
}

/* ---------- 错题本列表 ---------- */
async function renderWrongList() {
  mount(shell(topbar("错题本"), "/wrong"));
  $("#root .app").insertAdjacentHTML("beforeend", `<div class="page">
    <div class="seg">
      <button data-scope="active">待重做</button>
      <button data-scope="resolved">已掌握（历史回看）</button>
    </div>
    <div id="wrongBody"><div class="loading">加载中…</div></div>
    <button class="btn btn-primary" id="redoAll">开始错题重做</button>
  </div>`);
  const segBtns = document.querySelectorAll(".seg button");
  segBtns.forEach(b => b.onclick = () => loadWrong(b.dataset.scope));
  $("#redoAll").onclick = () => go("/redo");
  loadWrong(State.wrong.scope);
}
async function loadWrong(scope) {
  State.wrong.scope = scope;
  document.querySelectorAll(".seg button").forEach(b =>
    b.classList.toggle("on", b.dataset.scope === scope));
  $("#redoAll").style.display = scope === "active" ? "" : "none";
  const body = $("#wrongBody");
  body.innerHTML = `<div class="loading">加载中…</div>`;
  const items = await api(withUid("/api/wrong" + (scope === "resolved" ? "&scope=resolved" : "")));
  State.wrong.items = items;
  if (!items.length) {
    body.innerHTML = `<div class="empty"><span class="emo">${scope === "active" ? "🎉" : "📭"}</span>
      ${scope === "active" ? "还没有错题，先去章节练一练吧" : "还没有已掌握的错题记录"}</div>`;
    return;
  }
  body.innerHTML = items.map((it, i) => {
    const q = it.question;
    return `<div class="card wrong-item">
      <div class="stem-line">${i + 1}. ${esc(q.stem)}</div>
      <div class="meta">
        ${it.outdated ? `<span class="badge-outdated">题库已更新 v${it.pinned_version}→v${it.current_version}</span>`
                       : `<span class="tag">v${it.pinned_version}</span>`}
        <span class="tag red">错过 ${it.wrong_count} 次</span>
        ${(q.tags || []).slice(0, 2).map(t => `<span class="tag gray">${esc(t)}</span>`).join("")}
        <span class="small" style="margin-left:auto">${fmtDate(it.last_wrong_at)}</span>
      </div>
      <div class="fav-row">
        <button class="btn btn-sm btn-ghost" data-expand="${i}">展开回看</button>
        ${it.outdated ? `<button class="btn btn-sm" style="background:#fff4e3;color:#f28200" data-latest="${i}">查看最新版本题目</button>` : ""}
      </div>
      <div id="exp${i}" class="expand hidden"></div>
    </div>`;
  }).join("");
  body.querySelectorAll("[data-expand]").forEach(b => b.onclick = () => {
    const i = Number(b.dataset.expand), box = $("#exp" + i);
    if (!box.classList.contains("hidden")) { box.classList.add("hidden"); return; }
    const it = items[i], q = it.question;
    box.innerHTML = `<div>${q.options.map((op, oi) =>
      `<div class="op ${oi === q.answer ? "right" : ""}">${optionLetter(oi)}. ${esc(op)}${oi === q.answer ? " ✓ 正确答案" : ""}</div>`).join("")}</div>
      <div class="why">💬 ${esc(q.explanation)}</div>
      ${it.outdated ? `<div class="explain" style="background:#fff4e3;border-left:4px solid #f28200;margin-top:10px">
        <b>📌 你当时练的是 v${it.pinned_version} 旧题</b>
        <span>题库已更新到 v${it.current_version}，但你当时的作答记录原样保留在上面。</span></div>` : ""}
      ${it.resolved_at ? `<div class="small" style="margin-top:8px">已于 ${fmtDate(it.resolved_at)} 重做答对，移出错题本</div>` : ""}`;
    box.classList.remove("hidden");
  });
  body.querySelectorAll("[data-latest]").forEach(b => b.onclick = () =>
    showLatestVersion(items[Number(b.dataset.latest)]));
}
async function showLatestVersion(it) {
  // 从教练端版本接口拉取该题所有版本
  const versions = await api(`/api/admin/questions/${it.question_id}/versions`);
  const latest = versions[0], old = versions.find(v => v.version === it.pinned_version) || versions[versions.length - 1];
  const mask = document.createElement("div");
  mask.className = "modal-mask";
  mask.innerHTML = `<div class="modal">
    <h3>题目版本对比</h3>
    <div class="small" style="margin-bottom:8px">错题原记录不受影响，这里只做学习参考。</div>
    <div class="explain no"><b>你答错时 · v${old.version}</b><span>${esc(old.stem)}</span></div>
    <div class="explain ok" style="margin-top:10px"><b>题库最新版 · v${latest.version}（${fmtDate(latest.updated_at)}）</b>
      <span>${esc(latest.stem)}</span></div>
    <div id="diffBody"></div>
    <button class="btn btn-primary" id="closeMask">知道了</button></div>`;
  document.body.appendChild(mask);
  const diff = [];
  ["stem", "explanation", "answer"].forEach(k => {
    if (JSON.stringify(old[k]) !== JSON.stringify(latest[k])) diff.push(k);
  });
  $("#diffBody", mask).innerHTML = diff.length
    ? `<div class="card" style="box-shadow:none;background:#f7f9fc;margin-top:10px">
         <b style="font-size:13px">本次更新内容：</b>
         ${diff.map(k => `<div class="small" style="margin-top:4px">· ${ {stem:"题干",explanation:"解析",answer:"正确答案"}[k] }有调整</div>`).join("")}
         <div class="why" style="margin-top:8px">💬 最新解析：${esc(latest.explanation)}</div></div>`
    : `<div class="muted" style="margin-top:10px">题干和答案未变，仅优化了解析表述。</div>`;
  $("#closeMask", mask).onclick = () => mask.remove();
  mask.onclick = (e) => { if (e.target === mask) mask.remove(); };
}

/* ---------- 错题重做 ---------- */
async function renderRedo() {
  $("#root").innerHTML = `<div class="app"><div class="page"><div class="loading">加载错题…</div></div></div>`;
  const list = await api(withUid("/api/wrong/practice"));
  if (!list.length) {
    mount(shell("", "/wrong"));
    $("#root .app").innerHTML = `<div class="page"><div class="empty">
      <span class="emo">🎉</span>错题都被你消灭光了！</div>
      <button class="btn btn-primary" id="b">返回错题本</button></div>`;
    $("#b").onclick = () => go("/wrong");
    return;
  }
  State.redo = { list, idx: 0, results: {} };
  drawRedoQuestion();
}
function drawRedoQuestion() {
  const R = State.redo, q = R.list[R.idx];
  const done = R.results[q.id];
  mount(shell("", "/wrong"));
  $("#root .app").innerHTML = `<div class="page">
    <div class="quiz-head">
      <button class="back" id="backBtn">‹</button>
      <span class="t">错题重做 · 答对即移出错题本</span>
      <span class="quiz-pos">${R.idx + 1}/${R.list.length}</span>
    </div>
    ${q.outdated ? `<div class="explain" style="background:#fff4e3;border-left:4px solid #f28200;margin-bottom:12px">
      <b>📌 这道题题库已更新（你练的是 v${q.pinned_version}，当前 v${q.current_version}）</b>
      <span>重做按你答错时的旧题判分；做完后可在错题本查看最新版。</span></div>` : ""}
    ${questionCardHtml(q, done ? done.selected : null, !!done, done ? done.answer : null, "")}
    <div class="quiz-foot">
      <button class="btn btn-primary" id="nextBtn">${R.idx === R.list.length - 1 ? "完成" : "下一题"}</button>
    </div></div>`;
  if (done) {
    const slot = $("#explainSlot");
    slot.innerHTML = `<div class="explain ${done.is_correct ? "ok" : "no"}">
      <b>${done.is_correct ? "✅ 答对了，已移出错题本" : "❌ 还是错，再看一遍解析"}</b>
      <span class="human">${esc(done.explanation)}</span></div>`;
  }
  $("#backBtn").onclick = () => go("/wrong");
  document.querySelectorAll("#optBox .opt").forEach(btn =>
    btn.onclick = () => answerRedo(q, Number(btn.dataset.i)));
  $("#nextBtn").onclick = () => {
    if (R.idx === R.list.length - 1) { toast("本轮重做完成"); go("/wrong"); }
    else { R.idx++; drawRedoQuestion(); }
  };
}
async function answerRedo(q, selected) {
  const R = State.redo;
  try {
    const r = await api("/api/answers/wrongbook",
      { body: { user_id: State.user.id, question_id: q.id, selected } });
    R.results[q.id] = { selected, ...r };
    drawRedoQuestion();
  } catch (e) { toast(e.message); }
}

/* ---------- 模拟考试首页 ---------- */
async function renderMockHome() {
  mount(shell(topbar("全真模拟"), "/mock"));
  $("#root .app").insertAdjacentHTML("beforeend", `<div class="page" id="mp"><div class="loading">加载中…</div></div>`);
  const exams = await api(withUid("/api/mock"));
  const ongoing = exams.find(e => e.status === "ongoing" && !e.expired);
  $("#mp").innerHTML = `
    <div class="mock-hero">
      <h2>🚦 全真模拟考试</h2>
      <p>题库当前共 60 道演示题（正式考试为 100 题），系统按比例折算为百分制</p>
      <div class="mock-meta"><span>⏱ 45 分钟</span><span>📋 满分100</span><span>✅ 90分合格</span></div>
      <button class="btn" style="background:#fff;color:#1668dc" id="startBtn">
        ${ongoing ? "继续未完成的考试" : "开始模拟考试"}
      </button>
    </div>
    <div class="section-title">历史成绩</div>
    ${exams.length ? `<div>${exams.filter(e => e.status === "finished").map(e => `
      <div class="card exam-list row" data-exam="${e.id}" style="cursor:pointer">
        <div><div class="score ${e.score >= e.score && e.score >= 90 ? "pass" : "fail"}">${e.score}分</div>
        <div class="small">${fmtDate(e.finished_at)} · 用时${Math.round((e.duration_seconds || 0) / 60)}分钟 · ${e.correct_count}/${e.total}题</div></div>
        <div><span class="pill ${e.score >= 90 ? "ready" : "not_ready"}">${e.score >= 90 ? "合格" : "不合格"}</span>
        <div class="chev" style="margin-top:6px">›</div></div>
      </div>`).join("") || '<div class="empty"><span class="emo">📊</span>还没有考完的模拟</div>'}</div>`
      : `<div class="empty"><span class="emo">📊</span>还没有模拟记录，先来一场吧</div>`}`;
  $("#startBtn").onclick = async () => {
    try {
      const data = await api("/api/mock/start", { body: { user_id: State.user.id } });
      go("/exam/" + data.exam_id);
    } catch (e) { toast(e.message); }
  };
  document.querySelectorAll("[data-exam]").forEach(el =>
    el.onclick = () => go("/review/" + el.dataset.exam));
}

/* ---------- 考试进行页 ---------- */
async function renderExam(examId) {
  mount(`<div class="app" style="padding-bottom:0"><div id="examBody" class="loading" style="padding-top:80px">试卷加载中…</div></div>`);
  let data;
  try { data = await api("/api/mock/start", { body: { user_id: State.user.id } }); }
  catch (e) { $("#examBody").textContent = e.message; return; }
  // 若服务端返回的是其他进行中考试，对齐 examId
  examId = data.exam_id;
  const saved = JSON.parse(localStorage.getItem("km1_exam_" + State.user.id + "_" + examId) || "null");
  const E = {
    examId, questions: data.questions,
    answers: saved && saved.answers ? saved.answers : {},
    startTs: saved && saved.startTs ? saved.startTs : Date.now(),
    serverRemain: data.remain_seconds,
    submitted: false,
  };
  // 剩余时间以服务端开始时间为准
  const serverStart = Date.now() - (data.duration - data.remain_seconds) * 1000;
  E.startTs = saved && saved.serverStart ? saved.serverStart : serverStart;
  E.remain = Math.max(0, data.duration - Math.floor((Date.now() - E.startTs) / 1000));
  State.exam = E;
  E.idx = saved && saved.idx ? saved.idx : 0;
  drawExamQuestion();
  startTimer();
}
function saveExam() {
  const E = State.exam;
  localStorage.setItem("km1_exam_" + State.user.id + "_" + E.examId, JSON.stringify({
    answers: E.answers, idx: E.idx, startTs: E.startTs, serverStart: E.startTs,
  }));
}
let examTimer = null;
function startTimer() {
  clearInterval(examTimer);
  examTimer = setInterval(() => {
    const E = State.exam;
    if (!E || E.submitted) return clearInterval(examTimer);
    E.remain--;
    const el = $("#timerTxt"), bar = $("#timerBar");
    if (el) {
      const m = Math.floor(E.remain / 60), s = E.remain % 60;
      el.textContent = `⏱ ${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
      if (E.remain <= 300 && bar) bar.classList.add("warn");
    }
    if (E.remain <= 0) { clearInterval(examTimer); submitExam(true); }
  }, 1000);
}
function drawExamQuestion() {
  const E = State.exam, q = E.questions[E.idx];
  const answered = E.answers[q.question_id] !== undefined;
  $("#root").innerHTML = `<div class="app" style="padding-bottom:20px">
    <div class="timer-bar" id="timerBar">
      <span id="timerTxt">⏱ --:--</span>
      <span>${answered ? "已作答" : "未作答"} ${Object.keys(E.answers).length}/${E.questions.length}</span>
    </div>
    <div class="page">
      <div class="quiz-head">
        <span class="t">全真模拟</span>
        <span class="quiz-pos">第 ${E.idx + 1}/${E.questions.length} 题</span>
      </div>
      ${questionCardHtml(q, answered ? E.answers[q.question_id] : null, false, null)}
      <div class="quiz-foot">
        ${E.idx > 0 ? `<button class="btn btn-ghost" id="prevBtn">上一题</button>` : ""}
        <button class="btn btn-ghost" id="sheetBtn">答题卡</button>
        <button class="btn btn-primary" id="nextBtn">${E.idx === E.questions.length - 1 ? "检查交卷" : "下一题"}</button>
      </div>
    </div></div>`;
  const m = String(Math.floor(E.remain / 60)).padStart(2, "0"),
        s = String(E.remain % 60).padStart(2, "0");
  $("#timerTxt").textContent = `⏱ ${m}:${s}`;
  if (E.remain <= 300) $("#timerBar").classList.add("warn");
  document.querySelectorAll("#optBox .opt").forEach(btn =>
    btn.onclick = () => {
      E.answers[q.question_id] = Number(btn.dataset.i);
      saveExam(); drawExamQuestion();
    });
  if ($("#prevBtn")) $("#prevBtn").onclick = () => { E.idx--; saveExam(); drawExamQuestion(); };
  $("#nextBtn").onclick = () => {
    if (E.idx === E.questions.length - 1) openSheet(true);
    else { E.idx++; saveExam(); drawExamQuestion(); }
  };
  $("#sheetBtn").onclick = () => openSheet(false);
}
function openSheet(fromLast) {
  const E = State.exam;
  const mask = document.createElement("div");
  mask.className = "modal-mask";
  const cells = E.questions.map((q, i) =>
    `<i data-jump="${i}" class="${E.answers[q.question_id] !== undefined ? "done" : ""} ${i === E.idx ? "cur" : ""}">${i + 1}</i>`
  ).join("");
  mask.innerHTML = `<div class="modal">
    <h3>答题卡</h3>
    <div class="muted">已答 <b style="color:#1668dc">${Object.keys(E.answers).length}</b> / ${E.questions.length}，未答 ${E.questions.length - Object.keys(E.answers).length} 题（按未答计错）</div>
    <div class="qmap">${cells}</div>
    <div class="quiz-foot">
      <button class="btn btn-ghost" id="sheetBack">继续答题</button>
      <button class="btn btn-danger" id="sheetSubmit">交卷</button>
    </div></div>`;
  document.body.appendChild(mask);
  mask.querySelectorAll("[data-jump]").forEach(c => c.onclick = () => {
    E.idx = Number(c.dataset.jump); saveExam(); mask.remove(); drawExamQuestion();
  });
  $("#sheetBack", mask).onclick = () => {
    if (fromLast && E.idx > 0) { E.idx--; saveExam(); }
    mask.remove(); drawExamQuestion();
  };
  $("#sheetSubmit", mask).onclick = () => {
    const unanswered = E.questions.length - Object.keys(E.answers).length;
    if (unanswered > 0 && !confirm(`还有 ${unanswered} 题未作答，确定交卷？未答按错误计算。`)) return;
    mask.remove(); submitExam(false);
  };
}
async function submitExam(auto) {
  const E = State.exam;
  if (!E || E.submitted) return;
  E.submitted = true;
  clearInterval(examTimer);
  mount(`<div class="app"><div class="loading" style="padding-top:120px">${auto ? "时间到，自动交卷中…" : "正在交卷…"}</div></div>`);
  try {
    const duration = Math.min(2700, Math.floor((Date.now() - E.startTs) / 1000));
    const r = await api(`/api/mock/${E.examId}/submit`, {
      body: { user_id: State.user.id, answers: E.answers, duration_seconds: duration }
    });
    localStorage.removeItem("km1_exam_" + State.user.id + "_" + E.examId);
    State.exam = null;
    go("/result/" + r.exam_id);
  } catch (e) {
    E.submitted = false;
    toast(e.message);
    go("/mock");
  }
}

/* ---------- 结果页 ---------- */
async function renderResult(examId) {
  mount(shell(topbar("考试成绩"), "/mock"));
  $("#root .app").insertAdjacentHTML("beforeend", `<div class="page" id="rb"><div class="loading">加载中…</div></div>`);
  let d;
  try { d = await api(withUid("/api/mock/" + examId)); }
  catch (e) { $("#rb").textContent = e.message; return; }
  const color = d.score >= 90 ? "#18a058" : (d.score >= 80 ? "#f28200" : "#e4393c");
  const wrongList = d.questions.filter(q => !q.is_correct);
  $("#rb").innerHTML = `
    <div class="card" style="text-align:center;padding:24px 16px">
      <div class="result-ring" style="background:${color}">
        <b>${d.score}</b><span>${d.passed ? "合格" : "未达90分"}</span></div>
      <div class="verdict" style="color:${color}">${d.passed ? "🎉 恭喜，达到预约考试水平！" : "还差一点，继续加油"}</div>
      <div class="muted">答对 ${d.correct_count} 题 / 共 ${d.total} 题 · 用时 ${Math.round(d.duration_seconds / 60)} 分钟</div>
      <div class="quiz-foot">
        <button class="btn btn-ghost" id="toMock">返回</button>
        <button class="btn btn-primary" id="toReview">查看答卷与解析</button>
      </div>
    </div>
    <div class="card">
      <b>本场错题（${wrongList.length}）已自动收入错题本</b>
      <div class="muted" style="margin-top:6px">去「错题 → 错题重做」再打一遍，答对就会移出错题本。</div>
      <button class="btn btn-ghost" id="toWrong" style="margin-top:10px">去错题重做</button>
    </div>`;
  $("#toMock").onclick = () => go("/mock");
  $("#toReview").onclick = () => go("/review/" + examId);
  $("#toWrong").onclick = () => go("/wrong");
}

/* ---------- 答卷回看 ---------- */
async function renderReview(examId) {
  mount(shell(topbar("答卷回看"), "/mock"));
  $("#root .app").insertAdjacentHTML("beforeend", `<div class="page" id="rv"><div class="loading">加载中…</div></div>`);
  const d = await api(withUid("/api/mock/" + examId));
  $("#rv").innerHTML = `
    <button class="detail-back" id="rbBtn">‹ 返回</button>
    <div class="card row"><div><b style="font-size:16px">${d.score}分 · ${d.score >= 90 ? "合格" : "不合格"}</b>
      <div class="small">${fmtDate(d.finished_at)}</div></div>
      <div class="small">${d.correct_count}/${d.total} 正确</div></div>
    <div class="card">
      ${d.questions.map((q, i) => `
        <div class="review-item">
          <div class="review-stem">${i + 1}. ${esc(q.stem)}
            <span class="pill ${q.is_correct ? "ready" : "not_ready"}" style="margin-left:4px">
              ${q.selected == null ? "未答" : (q.is_correct ? "对" : "错")}</span>
            <span class="tag gray" style="margin-left:4px">v${q.version}</span></div>
          <div class="review-opts">
            ${q.options.map((op, oi) => {
              let cls = "";
              if (oi === q.answer) cls = "r";
              else if (oi === q.selected) cls = "w";
              return `<div class="${cls}">${optionLetter(oi)}. ${esc(op)}${oi === q.answer ? " ✓" : ""}${oi === q.selected ? "（你的选择）" : ""}</div>`;
            }).join("")}
          </div>
          <div class="why" style="margin-top:6px">💬 ${esc(q.explanation)}</div>
        </div>`).join("")}
    </div>`;
  $("#rbBtn").onclick = () => history.back();
}

/* ---------- 启动 ---------- */
route();
