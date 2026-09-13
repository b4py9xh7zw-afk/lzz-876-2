# -*- coding: utf-8 -*-
"""业务逻辑：练习/错题本/模拟考试/教练看板/题库维护。"""
import json
from collections import defaultdict
from datetime import datetime, timezone, timedelta

from db import get_conn, now

EXAM_DURATION = 45 * 60       # 正式科目一 45 分钟
PASS_SCORE = 90
MOCK_MIN_QUESTIONS = 40       # 题库不足 100 时允许的最小演示规模


# ---------- 工具 ----------
def _q_public(row):
    """返回不含答案的题目（练习/考试下发给客户端）。"""
    return {"id": row["id"], "chapter_id": row["chapter_id"], "type": row["type"],
            "stem": row["stem"], "options": json.loads(row["options"]),
            "tags": json.loads(row["tags"]), "version": row["version"]}


def _snapshot(record):
    """从 answer_records 还原一次答题时刻的题目快照。"""
    return {"id": record["question_id"], "version": record["question_version"],
            "chapter_id": record["chapter_id"], "type": record["snap_type"],
            "stem": record["snap_stem"], "options": json.loads(record["snap_options"]),
            "answer": record["snap_answer"], "explanation": record["snap_explanation"],
            "tags": json.loads(record["snap_tags"])}


def _paper_item(item):
    return {"question_id": item["question_id"], "version": item["version"],
            "chapter_id": item["chapter_id"], "type": item["type"],
            "stem": item["stem"], "options": item["options"],
            "tags": item["tags"]}


# ---------- 用户 ----------
def get_or_create_user(name, role="student"):
    name = (name or "").strip()
    if not name:
        raise ValueError("请输入姓名")
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE name=?", (name,)).fetchone()
        if row:
            return dict(row)
        cur = conn.execute("INSERT INTO users(name,role,created_at) VALUES(?,?,?)",
                           (name, role, now()))
        return dict(conn.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone())


def list_users(role=None):
    sql = "SELECT * FROM users"
    args = ()
    if role:
        sql += " WHERE role=?"
        args = (role,)
    sql += " ORDER BY id"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]


def get_user(uid):
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        return dict(r) if r else None


# ---------- 章节练习 ----------
def list_chapters(uid):
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM chapters ORDER BY sort_order").fetchall()
        out = []
        for c in rows:
            total = conn.execute("SELECT COUNT(*) n FROM questions WHERE chapter_id=?",
                                 (c["id"],)).fetchone()["n"]
            stat = conn.execute("""
                SELECT COUNT(*) n,
                       SUM(CASE WHEN is_correct=1 THEN 1 ELSE 0 END) ok
                FROM (
                  SELECT question_id, is_correct,
                         ROW_NUMBER() OVER(PARTITION BY question_id ORDER BY id DESC) rn
                  FROM answer_records
                  WHERE user_id=? AND chapter_id=? AND source IN('chapter','wrongbook')
                ) WHERE rn=1""", (uid, c["id"])).fetchone()
            practiced = stat["n"] or 0
            mastered = stat["ok"] or 0
            out.append({"id": c["id"], "name": c["name"], "description": c["description"],
                        "total": total, "practiced": practiced, "mastered": mastered,
                        "progress": round(mastered / total, 3) if total else 0})
        return out


def get_practice(uid, chapter_id):
    with get_conn() as conn:
        c = conn.execute("SELECT * FROM chapters WHERE id=?", (chapter_id,)).fetchone()
        if not c:
            raise LookupError("章节不存在")
        qs = [_q_public(r) for r in conn.execute(
            "SELECT * FROM questions WHERE chapter_id=? ORDER BY id", (chapter_id,)).fetchall()]
        status = {}
        for r in conn.execute("""
            SELECT question_id, is_correct FROM answer_records ar
            WHERE id IN (SELECT MAX(id) FROM answer_records
                         WHERE user_id=? AND source IN('chapter','wrongbook')
                         GROUP BY question_id)""", (uid,)).fetchall():
            status[r["question_id"]] = r["is_correct"]
        for q in qs:
            q["last_correct"] = status.get(q["id"])  # None=未做 0=上次错 1=上次对
        return {"chapter": {"id": c["id"], "name": c["name"]}, "questions": qs}


def _record_answer(conn, uid, q, source, selected, context_id):
    correct = 0 if selected is None or selected != q["answer"] else 1
    conn.execute("""INSERT INTO answer_records
      (user_id,question_id,question_version,chapter_id,source,context_id,selected,is_correct,
       snap_type,snap_stem,snap_options,snap_answer,snap_explanation,snap_tags,created_at)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (uid, q["id"], q["version"], q["chapter_id"], source, context_id, selected, correct,
       q["type"], q["stem"], json.dumps(q["options"], ensure_ascii=False), q["answer"],
       q["explanation"], json.dumps(q["tags"], ensure_ascii=False), now()))
    if not correct:
        conn.execute("""INSERT INTO wrong_questions
            (user_id,question_id,question_version_at_wrong,last_wrong_at,wrong_count)
            VALUES(?,?,?,?,1)
            ON CONFLICT(user_id,question_id) DO UPDATE SET
              question_version_at_wrong=excluded.question_version_at_wrong,
              last_wrong_at=excluded.last_wrong_at,
              resolved_at=NULL, wrong_count=wrong_count+1""",
            (uid, q["id"], q["version"], now()))
    elif source == "wrongbook":
        conn.execute("""UPDATE wrong_questions SET resolved_at=?
            WHERE user_id=? AND question_id=? AND resolved_at IS NULL""",
            (now(), uid, q["id"]))
    return correct


def submit_chapter_answer(uid, question_id, selected):
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM questions WHERE id=?", (question_id,)).fetchone()
        if not r:
            raise LookupError("题目不存在")
        q = {"id": r["id"], "version": r["version"], "chapter_id": r["chapter_id"],
             "type": r["type"], "stem": r["stem"],
             "options": json.loads(r["options"]), "answer": r["answer"],
             "explanation": r["explanation"], "tags": json.loads(r["tags"])}
        if selected is not None and not (0 <= selected < len(q["options"])):
            raise ValueError("选项无效")
        correct = _record_answer(conn, uid, q, "chapter", selected, None)
        return {"is_correct": bool(correct), "answer": q["answer"],
                "explanation": q["explanation"], "question_version": q["version"]}


# ---------- 错题本 ----------
def _wrong_items(conn, uid, active_only):
    where = "resolved_at IS NULL" if active_only else "resolved_at IS NOT NULL"
    rows = conn.execute(f"""
        SELECT w.*, (SELECT version FROM questions WHERE id=w.question_id) cur_version,
               (SELECT COUNT(*) FROM answer_records
                WHERE user_id=w.user_id AND question_id=w.question_id AND is_correct=0) total_wrong
        FROM wrong_questions w WHERE w.user_id=? AND {where}
        ORDER BY w.last_wrong_at DESC""", (uid,)).fetchall()
    items = []
    for w in rows:
        # 优先取错题本锁定版本的最近一次答错快照；找不到再取任意最近答错记录
        snap_rec = conn.execute("""SELECT * FROM answer_records
            WHERE user_id=? AND question_id=? AND is_correct=0
              AND question_version=?
            ORDER BY id DESC LIMIT 1""",
            (uid, w["question_id"], w["question_version_at_wrong"])).fetchone()
        if snap_rec is None:
            snap_rec = conn.execute("""SELECT * FROM answer_records
                WHERE user_id=? AND question_id=? AND is_correct=0
                ORDER BY id DESC LIMIT 1""", (uid, w["question_id"])).fetchone()
        snap = _snapshot(snap_rec)
        # 兜底：极早期模拟卷冻结时未存答案/解析（题库当前题仍可补全）
        if snap["answer"] is None or not snap["explanation"]:
            cur = conn.execute("SELECT answer, explanation FROM questions WHERE id=?",
                               (w["question_id"],)).fetchone()
            if cur:
                snap["answer"] = cur["answer"]
                snap["explanation"] = cur["explanation"]
        items.append({
            "question_id": w["question_id"],
            "pinned_version": w["question_version_at_wrong"],
            "current_version": w["cur_version"] or w["question_version_at_wrong"],
            "outdated": (w["cur_version"] is not None
                         and w["cur_version"] != w["question_version_at_wrong"]),
            "wrong_count": w["total_wrong"],
            "last_wrong_at": w["last_wrong_at"],
            "resolved_at": w["resolved_at"],
            "question": {
                "id": snap["id"], "version": snap["version"],
                "chapter_id": snap["chapter_id"], "type": snap["type"],
                "stem": snap["stem"], "options": snap["options"], "tags": snap["tags"],
                "answer": snap["answer"], "explanation": snap["explanation"]},
        })
    return items


def list_wrong(uid, scope="active"):
    with get_conn() as conn:
        if scope == "resolved":
            return _wrong_items(conn, uid, False)
        return _wrong_items(conn, uid, True)


def wrong_practice_set(uid):
    """错题重做：返回错题（答错时锁定的版本），含答案解析由提交时返回。"""
    with get_conn() as conn:
        items = _wrong_items(conn, uid, True)
        out = []
        for it in items:
            q = it["question"]
            q["pinned_version"] = it["pinned_version"]
            q["outdated"] = it["outdated"]
            q["current_version"] = it["current_version"]
            out.append(q)
        return out


def submit_wrongbook_answer(uid, question_id, selected):
    with get_conn() as conn:
        w = conn.execute("""SELECT * FROM wrong_questions
            WHERE user_id=? AND question_id=? AND resolved_at IS NULL""",
                         (uid, question_id)).fetchone()
        if not w:
            raise LookupError("该题不在待重做的错题本中")
        rec = conn.execute("""SELECT * FROM answer_records
            WHERE user_id=? AND question_id=? AND question_version=?
            ORDER BY id DESC LIMIT 1""",
            (uid, question_id, w["question_version_at_wrong"])).fetchone()
        if not rec:  # 兜底：用最新错题快照
            rec = conn.execute("""SELECT * FROM answer_records
                WHERE user_id=? AND question_id=? AND is_correct=0
                ORDER BY id DESC LIMIT 1""", (uid, question_id)).fetchone()
        q = _snapshot(rec)
        correct = _record_answer(conn, uid, q, "wrongbook", selected, None)
        mastered = bool(correct)
        return {"is_correct": bool(correct), "answer": q["answer"],
                "explanation": q["explanation"], "question_version": q["version"],
                "mastered": mastered}


# ---------- 全真模拟 ----------
def mock_start(uid):
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM questions ORDER BY RANDOM()").fetchall()
        if len(rows) < MOCK_MIN_QUESTIONS:
            raise RuntimeError("题库题量不足，暂不能开考")
        existing = conn.execute("""SELECT * FROM mock_exams
            WHERE user_id=? AND status='ongoing' ORDER BY id DESC LIMIT 1""",
                                (uid,)).fetchone()
        if existing:
            started = datetime.fromisoformat(existing["started_at"])
            if datetime.now(timezone.utc) - started < timedelta(seconds=EXAM_DURATION):
                paper = [_paper_item(x) for x in json.loads(existing["questions_json"])]
                remain = EXAM_DURATION - int(
                    (datetime.now(timezone.utc) - started).total_seconds())
                return {"exam_id": existing["id"], "resumed": True,
                        "duration": EXAM_DURATION, "remain_seconds": max(0, remain),
                        "pass_score": PASS_SCORE, "questions": paper}
        # 服务端冻结全量试卷（含答案/解析，供判分和考后回看）；
        # 下发前由 _paper_item 剥离答案字段，防止前端提前看到答案。
        full_paper = []
        for r in rows:
            full_paper.append({"question_id": r["id"], "version": r["version"],
                               "chapter_id": r["chapter_id"], "type": r["type"],
                               "stem": r["stem"], "options": json.loads(r["options"]),
                               "answer": r["answer"], "explanation": r["explanation"],
                               "tags": json.loads(r["tags"])})
        cur = conn.execute("""INSERT INTO mock_exams
            (user_id,total,status,started_at,questions_json)
            VALUES(?,?,'ongoing',?,?)""",
            (uid, len(full_paper), now(), json.dumps(full_paper, ensure_ascii=False)))
        return {"exam_id": cur.lastrowid, "resumed": False, "duration": EXAM_DURATION,
                "remain_seconds": EXAM_DURATION, "pass_score": PASS_SCORE,
                "questions": [_paper_item(x) for x in full_paper]}


def mock_submit(uid, exam_id, answers, duration_seconds=None):
    """answers: {question_id: selected_index|null}"""
    with get_conn() as conn:
        e = conn.execute("SELECT * FROM mock_exams WHERE id=? AND user_id=?",
                         (exam_id, uid)).fetchone()
        if not e:
            raise LookupError("考试不存在")
        if e["status"] == "finished":
            raise RuntimeError("本场考试已交卷")
        started = datetime.fromisoformat(e["started_at"])
        if datetime.now(timezone.utc) - started >= timedelta(seconds=EXAM_DURATION):
            raise TimeoutError("考试时间已到")
        paper = json.loads(e["questions_json"])
        # 兼容旧试卷（冻结时未存答案）：从题库按冻结版本/当前题补答案
        qmap = {r["id"]: r for r in conn.execute("SELECT * FROM questions")}
        correct_count = 0
        for item in paper:
            sel = answers.get(item["question_id"])
            item["selected"] = sel
            if "answer" not in item:
                r = qmap.get(item["question_id"])
                item["answer"] = r["answer"] if r else -1
                item["explanation"] = r["explanation"] if r else ""
            if sel == item["answer"]:
                correct_count += 1
        total = len(paper)
        score = round(correct_count / total * 100)
        used = duration_seconds
        if used is None:
            used = int((datetime.now(timezone.utc) - started).total_seconds())
        conn.execute("""UPDATE mock_exams SET correct_count=?, score=?, status='finished',
            finished_at=?, duration_seconds=?, questions_json=? WHERE id=?""",
            (correct_count, score, now(), min(used, EXAM_DURATION),
             json.dumps(paper, ensure_ascii=False), exam_id))
        for item in paper:
            q = {"id": item["question_id"], "version": item["version"],
                 "chapter_id": item["chapter_id"], "type": item["type"],
                 "stem": item["stem"], "options": item["options"],
                 "answer": item["answer"], "explanation": item["explanation"],
                 "tags": item["tags"]}
            _record_answer(conn, uid, q, "mock", item["selected"], exam_id)
        return {"exam_id": exam_id, "total": total, "correct_count": correct_count,
                "score": score, "pass_score": PASS_SCORE,
                "passed": score >= PASS_SCORE,
                "duration_seconds": min(used, EXAM_DURATION)}


def mock_list(uid):
    with get_conn() as conn:
        rows = conn.execute("""SELECT id,total,correct_count,score,status,started_at,
            finished_at,duration_seconds FROM mock_exams WHERE user_id=?
            ORDER BY id DESC""", (uid,)).fetchall()
        out = [dict(r) for r in rows]
        ongoing = next((x for x in out if x["status"] == "ongoing"), None)
        if ongoing:
            started = datetime.fromisoformat(ongoing["started_at"])
            ongoing["expired"] = (datetime.now(timezone.utc) - started
                                  >= timedelta(seconds=EXAM_DURATION))
        return out


def mock_detail(uid, exam_id):
    with get_conn() as conn:
        e = conn.execute("SELECT * FROM mock_exams WHERE id=? AND user_id=?",
                         (exam_id, uid)).fetchone()
        if not e:
            raise LookupError("考试不存在")
        paper = json.loads(e["questions_json"])
        d = {k: e[k] for k in ("id", "total", "correct_count", "score", "status",
                               "started_at", "finished_at", "duration_seconds")}
        d["pass_score"] = PASS_SCORE
        d["questions"] = []
        for item in paper:
            d["questions"].append({
                "question_id": item["question_id"], "version": item["version"],
                "chapter_id": item["chapter_id"], "type": item["type"],
                "stem": item["stem"], "options": item["options"], "tags": item["tags"],
                "selected": item.get("selected"), "answer": item.get("answer"),
                "explanation": item.get("explanation"),
                "is_correct": (item.get("selected") == item.get("answer"))
                if e["status"] == "finished" else None})
        return d


# ---------- 学员总览 ----------
def overview(uid):
    with get_conn() as conn:
        r = conn.execute("""SELECT COUNT(*) n,
            SUM(CASE WHEN is_correct=1 THEN 1 ELSE 0 END) ok
            FROM answer_records WHERE user_id=?""", (uid,)).fetchone()
        answers, correct = r["n"] or 0, r["ok"] or 0
        active = conn.execute(
            "SELECT COUNT(*) n FROM wrong_questions WHERE user_id=? AND resolved_at IS NULL",
            (uid,)).fetchone()["n"]
        exams = conn.execute("""SELECT score FROM mock_exams
            WHERE user_id=? AND status='finished' ORDER BY id""", (uid,)).fetchall()
        scores = [x["score"] for x in exams]
        # 章节统计
        chapters = []
        for c in conn.execute("SELECT * FROM chapters ORDER BY sort_order"):
            stat = conn.execute("""
                SELECT COUNT(*) n, SUM(CASE WHEN is_correct=1 THEN 1 ELSE 0 END) ok
                FROM (SELECT question_id,is_correct,
                        ROW_NUMBER() OVER(PARTITION BY question_id ORDER BY id DESC) rn
                      FROM answer_records WHERE user_id=? AND chapter_id=?
                      AND source IN('chapter','wrongbook')) WHERE rn=1""",
                (uid, c["id"])).fetchone()
            total = conn.execute("SELECT COUNT(*) n FROM questions WHERE chapter_id=?",
                                 (c["id"],)).fetchone()["n"]
            chapters.append({"id": c["id"], "name": c["name"], "total": total,
                             "practiced": stat["n"] or 0, "mastered": stat["ok"] or 0})
        # 易错标签（来自当前错题本快照）
        tag_counter = defaultdict(int)
        for w in conn.execute("""SELECT question_id FROM wrong_questions
                WHERE user_id=? AND resolved_at IS NULL""", (uid,)).fetchall():
            rec = conn.execute("""SELECT snap_tags FROM answer_records
                WHERE user_id=? AND question_id=? AND is_correct=0
                ORDER BY id DESC LIMIT 1""", (uid, w["question_id"])).fetchone()
            for t in json.loads(rec["snap_tags"]):
                tag_counter[t] += 1
        weak_tags = sorted(tag_counter.items(), key=lambda x: -x[1])[:6]
        return {"total_answers": answers,
                "accuracy": round(correct / answers, 3) if answers else 0,
                "active_wrong": active,
                "exam_count": len(scores),
                "latest_score": scores[-1] if scores else None,
                "best_score": max(scores) if scores else None,
                "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
                "chapters": chapters,
                "weak_tags": [{"tag": t, "count": n} for t, n in weak_tags]}


# ---------- 教练看板 ----------
def _readiness(avg3, latest, active_wrong, exam_count):
    if exam_count < 3:
        return ("insufficient", "模拟数据不足",
                "先完成至少3场全真模拟，教练才能给出靠谱的预约判断。")
    if avg3 >= 90 and latest >= 88 and active_wrong <= 15:
        return ("ready", "可以预约考试",
                "模拟稳定在合格线以上，错题也清得差不多了，建议尽快预约科目一。")
    if avg3 >= 85 and active_wrong <= 25:
        return ("caution", "再巩固一下",
                "分数接近合格线但还不稳，重点消灭错题本里的高频法规，2-3天后再考一场。")
    return ("not_ready", "暂不建议预约",
            "模拟分数离90分差距明显或错题积压较多，先按章节把薄弱环节过一遍，别浪费一次考试机会。")


def coach_students():
    with get_conn() as conn:
        users = conn.execute("SELECT * FROM users WHERE role='student' ORDER BY id").fetchall()
        out = []
        for u in users:
            uid = u["id"]
            o = overview(uid)
            scores = [r["score"] for r in conn.execute("""SELECT score FROM mock_exams
                WHERE user_id=? AND status='finished' ORDER BY id DESC LIMIT 3""",
                (uid,)).fetchall()]
            avg3 = round(sum(scores) / len(scores), 1) if scores else None
            level, title, advice = _readiness(
                avg3 if avg3 is not None else 0,
                scores[0] if scores else None, o["active_wrong"], o["exam_count"])
            out.append({"id": uid, "name": u["name"],
                        "active_wrong": o["active_wrong"],
                        "weak_tags": o["weak_tags"][:3],
                        "exam_count": o["exam_count"], "avg3": avg3,
                        "latest": o["latest_score"], "best": o["best_score"],
                        "readiness": level, "readiness_title": title, "advice": advice})
        return out


def coach_student_detail(uid):
    u = get_user(uid)
    if not u:
        raise LookupError("学员不存在")
    o = overview(uid)
    with get_conn() as conn:
        scores = [r["score"] for r in conn.execute("""SELECT score FROM mock_exams
            WHERE user_id=? AND status='finished' ORDER BY id DESC LIMIT 3""",
            (uid,)).fetchall()]
    avg3 = round(sum(scores) / len(scores), 1) if scores else None
    level, title, advice = _readiness(avg3 if avg3 is not None else 0,
                                      scores[0] if scores else None,
                                      o["active_wrong"], o["exam_count"])
    # 易错法规（标签维度）+ 对应错题清单
    wrong = list_wrong(uid, "active")
    return {"user": {"id": u["id"], "name": u["name"]}, "overview": o,
            "readiness": {"level": level, "title": title, "advice": advice,
                          "avg3": avg3},
            "wrong_questions": wrong}


# ---------- 教练：题库维护 ----------
def admin_list_questions():
    with get_conn() as conn:
        rows = conn.execute("""SELECT q.*, c.name chapter_name
            FROM questions q JOIN chapters c ON c.id=q.chapter_id ORDER BY q.id""").fetchall()
        return [{"id": r["id"], "chapter_id": r["chapter_id"],
                 "chapter_name": r["chapter_name"], "type": r["type"],
                 "stem": r["stem"], "options": json.loads(r["options"]),
                 "answer": r["answer"], "explanation": r["explanation"],
                 "tags": json.loads(r["tags"]), "version": r["version"],
                 "updated_at": r["updated_at"]} for r in rows]


def admin_get_versions(question_id):
    with get_conn() as conn:
        rows = conn.execute("""SELECT * FROM questions_history
            WHERE question_id=? ORDER BY version DESC""", (question_id,)).fetchall()
        if not rows:
            raise LookupError("题目不存在")
        return [{"question_id": r["question_id"], "version": r["version"],
                 "chapter_id": r["chapter_id"], "type": r["type"], "stem": r["stem"],
                 "options": json.loads(r["options"]), "answer": r["answer"],
                 "explanation": r["explanation"], "tags": json.loads(r["tags"]),
                 "updated_at": r["updated_at"]} for r in rows]


def admin_update_question(qid, patch):
    allowed = {"stem", "options", "answer", "explanation", "tags", "chapter_id", "type"}
    patch = {k: v for k, v in patch.items() if k in allowed}
    if not patch:
        raise ValueError("没有可更新的字段")
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
        if not r:
            raise LookupError("题目不存在")
        old = {"question_id": r["id"], "version": r["version"],
               "chapter_id": r["chapter_id"], "type": r["type"], "stem": r["stem"],
               "options": r["options"], "answer": r["answer"],
               "explanation": r["explanation"], "tags": r["tags"],
               "updated_at": r["updated_at"]}
        conn.execute("""INSERT OR IGNORE INTO questions_history
            (question_id,version,chapter_id,type,stem,options,answer,explanation,tags,updated_at)
            VALUES(:question_id,:version,:chapter_id,:type,:stem,:options,:answer,
                   :explanation,:tags,:updated_at)""", old)
        newv = {
            "chapter_id": patch.get("chapter_id", r["chapter_id"]),
            "type": patch.get("type", r["type"]),
            "stem": patch.get("stem", r["stem"]),
            "options": (json.dumps(patch["options"], ensure_ascii=False)
                        if "options" in patch else r["options"]),
            "answer": patch.get("answer", r["answer"]),
            "explanation": patch.get("explanation", r["explanation"]),
            "tags": (json.dumps(patch["tags"], ensure_ascii=False)
                     if "tags" in patch else r["tags"]),
        }
        opts = json.loads(newv["options"])
        if not (2 <= len(opts) <= 6) or not (0 <= newv["answer"] < len(opts)):
            raise ValueError("选项或正确答案不合法")
        ts = now()
        newv["updated_at"] = ts
        newv["qid"] = qid
        conn.execute("""UPDATE questions SET chapter_id=:chapter_id,type=:type,stem=:stem,
            options=:options,answer=:answer,explanation=:explanation,tags=:tags,
            version=version+1,updated_at=:updated_at WHERE id=:qid""", newv)
        return {"id": qid, "version": r["version"] + 1, "updated_at": ts}
