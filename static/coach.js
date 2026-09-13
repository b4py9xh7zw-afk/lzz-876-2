/* ============================================================
 * 科目一 · 教练后台（原生 JS）
 * ============================================================ */
"use strict";
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s == null ? "" : s)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
async function api(path, opts = {}) {
  const res = await fetch(path, {
    method: opts.method || (opts.body ? "POST" : "GET"),
    headers: opts.body ? { "Content-Type": "application/json" } : {},
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "请求失败");
  return data;
}
const fmtDate = (iso) => {
  if (!iso) return "-";
  const d = new Date(iso), p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
};
const L = (i) => ["A", "B", "C", "D"][i] || i;

const levelText = { ready: "建议约考", caution: "巩固后约考", not_ready: "暂不约考", insufficient: "数据不足" };

/* ---------- 学员看板 ---------- */
async function tabStudents() {
  const root = $("#root");
  root.innerHTML = frame("students") + `<div class="coach-wrap">
    <div class="coach-head"><h1>👨‍🏫 教练后台</h1>
      <p>基于章节练习、错题本与近 3 场全真模拟，给出易错法规与预约建议</p></div>
    <div id="stuBody" class="loading">加载中…</div></div>`;
  const students = await api("/api/coach/students");
  $("#stuBody").innerHTML = `<div class="stu-grid">${students.map(s => `
    <div class="stu-card" data-id="${s.id}" style="cursor:pointer">
      <h3>${esc(s.name)}<span class="pill ${s.readiness}">${levelText[s.readiness]}</span></h3>
      <div class="sub">最近模拟：${s.latest ?? "—"}分 · 共考 ${s.exam_count} 场</div>
      <div class="stu-stat">
        <div><b class="${s.avg3 == null ? "" : s.avg3 >= 90 ? "green" : s.avg3 >= 85 ? "orange" : "red"}">${s.avg3 ?? "—"}</b><span>近3场均分</span></div>
        <div><b class="${s.best >= 90 ? "green" : ""}">${s.best ?? "—"}</b><span>最高分</span></div>
        <div><b class="${s.active_wrong > 25 ? "red" : s.active_wrong > 15 ? "orange" : "green"}">${s.active_wrong}</b><span>待清错题</span></div>
      </div>
      <div class="small">易错法规：${s.weak_tags.length
        ? s.weak_tags.map(t => `<span class="tag warn">${esc(t.tag)}·${t.count}</span>`).join("")
        : '<span class="muted">暂无</span>'}</div>
      <div class="advice">💡 ${esc(s.advice)}</div>
    </div>`).join("")}</div>`;
  document.querySelectorAll("[data-id]").forEach(el =>
    el.onclick = () => location.hash = "#/student/" + el.dataset.id);
}
function frame(tab) {
  const tabs = [["students", "学员看板"], ["qbank", "题库维护"]];
  return `<div class="coach-tabs" style="max-width:960px;margin:12px auto 0;padding:0 14px">
    ${tabs.map(([k, t]) => `<button class="${tab === k ? "on" : ""}" data-tab="${k}">${t}</button>`).join("")}
  </div>`;
}

/* ---------- 学员详情 ---------- */
async function tabStudentDetail(id) {
  const root = $("#root");
  root.innerHTML = frame() + `<div class="coach-wrap" id="detailBody"><div class="loading" style="padding:40px">加载中…</div></div>`;
  document.querySelectorAll("[data-tab]").forEach(b =>
    b.onclick = () => { location.hash = "#/"; if (b.dataset.tab === "students") tabStudents(); else tabQbank(); });
  let d;
  try { d = await api("/api/coach/students/" + id); }
  catch (e) { $("#detailBody").innerHTML = `<div class="empty">${esc(e.message)}</div>`; return; }
  const { user, overview: ov, readiness, wrong_questions: wrongs } = d;
  const maxTag = Math.max(1, ...ov.weak_tags.map(t => t.count));
  const maxChap = Math.max(1, ...ov.chapters.map(c => c.total));
  const outdatedCount = wrongs.filter(w => w.outdated).length;
  $("#detailBody").innerHTML = `
    <button class="detail-back" id="back">‹ 返回学员看板</button>
    <div class="coach-head" style="border-radius:14px;margin-bottom:14px">
      <h1>${esc(user.name)} 的学习诊断</h1>
      <p>正确率 ${Math.round(ov.accuracy * 100)}% · 累计答题 ${ov.total_answers} 次 · 待清错题 ${ov.active_wrong} 题</p>
    </div>
    <div class="card">
      <div class="row">
        <b style="font-size:16px">预约考试建议</b>
        <span class="pill ${readiness.level}">${levelText[readiness.level]}</span>
      </div>
      <div class="advice" style="margin-top:10px">💡 ${esc(readiness.advice)}
        <div class="small" style="margin-top:6px">近3场均分：${readiness.avg3 ?? "数据不足"}（90分合格），
          最高 ${ov.best_score ?? "—"}，最近 ${ov.latest_score ?? "—"}</div>
      </div>
    </div>
    <div class="card">
      <b>易错法规 TOP（按当前错题本统计）</b>
      <div class="weak-bars">
        ${ov.weak_tags.length ? ov.weak_tags.map(t => `
          <div class="weak-bar"><span class="lab">${esc(t.tag)}</span>
            <span class="track"><i style="width:${Math.round(t.count / maxTag * 100)}%"></i></span>
            <span class="n">${t.count}</span></div>`).join("")
          : '<div class="muted" style="margin-top:8px">错题已清空，状态很好。</div>'}
      </div>
    </div>
    <div class="card">
      <b>章节掌握度</b>
      ${ov.chapters.map(c => {
        const pct = c.total ? Math.round(c.mastered / c.total * 100) : 0;
        const cls = pct >= 70 ? "" : pct >= 40 ? "mid" : "low";
        return `<div class="chap-row"><span class="nm">${esc(c.name)}</span>
          <span class="track"><i class="${cls}" style="width:${pct}%"></i></span>
          <span class="small" style="width:64px;text-align:right">${c.mastered}/${c.total} · ${pct}%</span></div>`;
      }).join("")}
    </div>
    <div class="card">
      <div class="row"><b>当前错题（${wrongs.length}）</b>
        <span class="small">${outdatedCount ? `含 ${outdatedCount} 道题库更新前的旧错题` : ""}</span></div>
      <div class="small" style="margin:4px 0 8px">旧错题按学员当时练习的版本回看，题库更新不影响记录。</div>
      <div id="wrongAccord">${wrongs.slice(0, 50).map((w, i) => {
        const q = w.question;
        return `<div style="border-top:1px solid var(--line);padding:10px 0">
          <div class="row" style="align-items:flex-start;gap:10px">
            <div style="flex:1;font-size:13.5px;font-weight:600">${i + 1}. ${esc(q.stem)}</div>
            <span class="tag red" style="flex:none">错${w.wrong_count}次</span></div>
          <div style="margin-top:4px">
            ${w.outdated ? `<span class="badge-outdated">旧版v${w.pinned_version}·现v${w.current_version}</span>` : `<span class="tag">v${w.pinned_version}</span>`}
            ${(q.tags || []).map(t => `<span class="tag gray">${esc(t)}</span>`).join("")}
            <button class="btn btn-sm btn-ghost" data-w="${i}" style="float:right">看解析</button>
          </div>
          <div class="expand hidden" id="wd${i}">
            ${q.options.map((op, oi) =>
              `<div class="op ${oi === q.answer ? "right" : ""}">${L(oi)}. ${esc(op)}${oi === q.answer ? " ✓" : ""}</div>`).join("")}
            <div class="why">💬 ${esc(q.explanation)}</div>
            <div class="small">最近答错：${fmtDate(w.last_wrong_at)}</div>
          </div>
        </div>`;
      }).join("") || '<div class="muted">无</div>'}</div>
    </div>`;
  $("#back").onclick = () => location.hash = "#/";
  document.querySelectorAll("[data-w]").forEach(b => b.onclick = () =>
    $("#wd" + b.dataset.w).classList.toggle("hidden"));
}

/* ---------- 题库维护 ---------- */
async function tabQbank() {
  const root = $("#root");
  root.innerHTML = frame("qbank") + `<div class="coach-wrap">
    <div class="coach-head"><h1>📚 题库维护</h1>
      <p>修改题目会生成新版本；学员的历史错题按旧版本永久保留，可随时回看</p></div>
    <div id="qbBody" class="loading">加载中…</div></div>`;
  const qs = await api("/api/admin/questions");
  $("#qbBody").innerHTML = `
    <div style="overflow-x:auto"><table class="qbank-table">
      <thead><tr><th>编号</th><th>章节</th><th>题干</th><th>答案</th><th>版本</th><th>操作</th></tr></thead>
      <tbody>${qs.map(q => `<tr>
        <td>${q.id}</td>
        <td style="white-space:nowrap">${esc(q.chapter_name.replace(/、.*/, ""))}</td>
        <td>${esc(q.stem)}<div style="margin-top:3px">${q.tags.map(t => `<span class="tag gray">${esc(t)}</span>`).join("")}</div></td>
        <td style="text-align:center;font-weight:700;color:#18a058">${L(q.answer)}</td>
        <td><span class="ver-badge ${q.version > 1 ? "v2" : ""}">v${q.version}</span></td>
        <td style="white-space:nowrap">
          <button class="btn btn-sm btn-ghost" data-edit="${q.id}">编辑</button>
          <button class="btn btn-sm" style="background:#eef0f4;color:#5b6675" data-ver="${q.id}">历史</button>
        </td></tr>`).join("")}</tbody></table></div>
    <div id="modalSlot"></div>`;
  document.querySelectorAll("[data-edit]").forEach(b => b.onclick = () => openEdit(qs.find(q => q.id === b.dataset.edit)));
  document.querySelectorAll("[data-ver]").forEach(b => b.onclick = () => openVersions(b.dataset.ver));
}

function modal(innerHtml) {
  const mask = document.createElement("div");
  mask.className = "modal-mask";
  mask.innerHTML = `<div class="modal">${innerHtml}</div>`;
  document.body.appendChild(mask);
  mask.onclick = (e) => { if (e.target === mask) mask.remove(); };
  return mask;
}

async function openEdit(q) {
  const mask = modal(`
    <h3>编辑题目 · ${q.id} <span class="ver-badge">当前 v${q.version}</span></h3>
    <div class="small">保存后生成新版本，不影响学员已有的错题快照。</div>
    <label class="fld">题干</label><textarea id="fStem">${esc(q.stem)}</textarea>
    <label class="fld">选项（每行一个）</label><textarea id="fOpts" style="min-height:120px">${q.options.map(esc).join("\n")}</textarea>
    <label class="fld">正确答案</label>
    <select id="fAnswer">${q.options.map((o, i) =>
      `<option value="${i}" ${i === q.answer ? "selected" : ""}>${L(i)}. ${esc(o)}</option>`).join("")}</select>
    <label class="fld">解析（讲人话）</label><textarea id="fExp">${esc(q.explanation)}</textarea>
    <label class="fld">标签（英文逗号分隔）</label>
    <textarea id="fTags" style="min-height:50px">${q.tags.map(esc).join(",")}</textarea>
    <div class="quiz-foot"><button class="btn btn-ghost" id="fCancel">取消</button>
      <button class="btn btn-primary" id="fSave">保存为新版本</button></div>
    <div id="fErr" style="color:#e4393c;font-size:13px;margin-top:8px"></div>`);
  // 选项变化时重建答案下拉
  const syncAnswer = () => {
    const opts = $("#fOpts", mask).value.split("\n").map(s => s.trim()).filter(Boolean);
    const cur = Number($("#fAnswer", mask).value);
    $("#fAnswer", mask).innerHTML = opts.map((o, i) =>
      `<option value="${i}" ${i === cur ? "selected" : ""}>${L(i)}. ${esc(o)}</option>`).join("");
  };
  $("#fOpts", mask).oninput = syncAnswer;
  $("#fCancel", mask).onclick = () => mask.remove();
  $("#fSave", mask).onclick = async () => {
    const options = $("#fOpts", mask).value.split("\n").map(s => s.trim()).filter(Boolean);
    if (options.length < 2) return $("#fErr", mask).textContent = "至少需要 2 个选项";
    const body = {
      stem: $("#fStem", mask).value.trim(),
      options,
      answer: Number($("#fAnswer", mask).value),
      explanation: $("#fExp", mask).value.trim(),
      tags: $("#fTags", mask).value.split(/[,，]/).map(s => s.trim()).filter(Boolean),
    };
    if (!body.stem || !body.explanation) return $("#fErr", mask).textContent = "题干和解析不能为空";
    try {
      const r = await api("/api/admin/questions/" + q.id, { method: "POST", body });
      mask.remove();
      alert(`已保存：${q.id} 升级为 v${r.version}`);
      tabQbank();
    } catch (e) { $("#fErr", mask).textContent = e.message; }
  };
}

async function openVersions(qid) {
  const vs = await api("/api/admin/questions/" + qid + "/versions");
  const mask = modal(`
    <h3>${qid} 版本历史（${vs.length} 个版本）</h3>
    ${vs.map((v, i) => `
      <div class="card" style="box-shadow:none;background:#f7f9fc;margin-bottom:10px">
        <div class="row"><b>v${v.version} ${i === 0 ? '<span class="tag">当前版本</span>' : ""}</b>
          <span class="small">${fmtDate(v.updated_at)}</span></div>
        <div style="font-size:13.5px;margin:6px 0">${esc(v.stem)}</div>
        ${v.options.map((o, oi) =>
          `<div class="op ${oi === v.answer ? "right" : ""}" style="font-size:12.5px">${L(oi)}. ${esc(o)}${oi === v.answer ? " ✓" : ""}</div>`).join("")}
        <div class="why" style="margin-top:6px;font-size:12.5px">💬 ${esc(v.explanation)}</div>
      </div>`).join("")}
    <button class="btn btn-ghost" id="vClose">关闭</button>`);
  $("#vClose", mask).onclick = () => mask.remove();
}

/* ---------- 路由 ---------- */
function coachRoute() {
  const h = (location.hash || "#/").replace(/^#/, "");
  const parts = h.split("/").filter(Boolean);
  if (parts[0] === "student") tabStudentDetail(parts[1]);
  else if (parts[0] === "qbank") { location.hash = "#/qbank"; tabQbank(); bindTabs("qbank"); }
  else { tabStudents(); bindTabs("students"); }
}
function bindTabs(active) {
  document.querySelectorAll("[data-tab]").forEach(b => {
    b.classList.toggle("on", b.dataset.tab === active);
    b.onclick = () => {
      if (b.dataset.tab === "qbank") { location.hash = "#/qbank"; tabQbank(); }
      else { location.hash = "#/"; tabStudents(); }
    };
  });
}
window.addEventListener("hashchange", coachRoute);
coachRoute();
