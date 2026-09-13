# -*- coding: utf-8 -*-
"""初始化题库并构造演示数据。
时间线（UTC）:
  9/1-9/6   学员按章节练习
  9/7-9/9   部分错题重做（掌握）
  9/10      题库更新：q07「闯红灯记分」解析按2022新规修订 -> v2（李雷的旧错题仍是v1）
  9/10-12   每人3场全真模拟
"""
import json, os, random, sqlite3
from datetime import datetime, timedelta, timezone

import db
from seed_data import CHAPTERS, QUESTIONS

USERS = [
    {"name": "李雷", "role": "student",
     "base_p": 0.80, "weak_p": 0.30,
     "weak_tags": ["记分", "罚款", "标志"],
     "exam_scores": [78, 84, 81]},
    {"name": "韩梅梅", "role": "student",
     "base_p": 0.90, "weak_p": 0.55,
     "weak_tags": ["标志", "标线", "信号灯"],
     "exam_scores": [88, 92, 86]},
    {"name": "张教练", "role": "coach",
     "base_p": 0.97, "weak_p": 0.9,
     "weak_tags": [],
     "exam_scores": [96, 98, 95]},
]


def qrow_to_dict(r):
    return {"id": r["question_id"] if "question_id" in r.keys() else r["id"],
            "chapter_id": r["chapter_id"], "type": r["type"], "stem": r["stem"],
            "options": json.loads(r["options"]), "answer": r["answer"],
            "explanation": r["explanation"], "tags": json.loads(r["tags"]),
            "version": r["version"], "updated_at": r["updated_at"]}


def all_questions(conn):
    rows = conn.execute("SELECT * FROM questions ORDER BY id").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["options"] = json.loads(d["options"])
        d["tags"] = json.loads(d["tags"])
        out.append(d)
    return out


def insert_answer(conn, uid, q, source, selected, ts, context_id=None):
    """q: 当前题（含快照字段）；selected=None 表示未答。"""
    correct = 0 if selected is None or selected != q["answer"] else 1
    conn.execute("""INSERT INTO answer_records
      (user_id,question_id,question_version,chapter_id,source,context_id,selected,is_correct,
       snap_type,snap_stem,snap_options,snap_answer,snap_explanation,snap_tags,created_at)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (uid, q["id"], q["version"], q["chapter_id"], source, context_id, selected, correct,
       q["type"], q["stem"], json.dumps(q["options"], ensure_ascii=False), q["answer"],
       q["explanation"], json.dumps(q["tags"], ensure_ascii=False), ts))
    if not correct:
        conn.execute("""INSERT INTO wrong_questions
            (user_id,question_id,question_version_at_wrong,last_wrong_at,wrong_count)
            VALUES(?,?,?,?,1)
            ON CONFLICT(user_id,question_id) DO UPDATE SET
              question_version_at_wrong=excluded.question_version_at_wrong,
              last_wrong_at=excluded.last_wrong_at,
              resolved_at=NULL, wrong_count=wrong_count+1""",
            (uid, q["id"], q["version"], ts))
    elif source == "wrongbook":
        # 错题本里重做答对 = 掌握，移出错题本
        conn.execute("""UPDATE wrong_questions SET resolved_at=?
            WHERE user_id=? AND question_id=? AND resolved_at IS NULL""",
            (ts, uid, q["id"]))
    return correct


def seed_chapters_questions(conn):
    for i, c in enumerate(CHAPTERS):
        conn.execute("INSERT OR REPLACE INTO chapters(id,name,sort_order,description) VALUES(?,?,?,?)",
                     (c["id"], c["name"], i, c["desc"]))
    ts = datetime(2026, 8, 25, tzinfo=timezone.utc).isoformat(timespec="seconds")
    for q in QUESTIONS:
        conn.execute("""INSERT OR REPLACE INTO questions
            (id,chapter_id,type,stem,options,answer,explanation,tags,version,updated_at)
            VALUES(?,?,?,?,?,?,?,?,1,?)""",
            (q["id"], q["chapter_id"], q["type"], q["stem"],
             json.dumps(q["options"], ensure_ascii=False), q["answer"], q["explanation"],
             json.dumps(q["tags"], ensure_ascii=False), ts))


def update_q07_v2(conn):
    """题库迭代演示：闯红灯记分题的解析按现行规定修订（选项分值不变，仍记6分）。"""
    ts = datetime(2026, 9, 10, 9, 0, tzinfo=timezone.utc).isoformat(timespec="seconds")
    r = conn.execute("SELECT * FROM questions WHERE id='q07'").fetchone()
    old = dict(r)
    conn.execute("""INSERT OR REPLACE INTO questions_history
        (question_id,version,chapter_id,type,stem,options,answer,explanation,tags,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (old["id"], 1, old["chapter_id"], old["type"], old["stem"], old["options"],
         old["answer"], old["explanation"], old["tags"], old["updated_at"]))
    new_exp = ("记6分、罚200元。闯一次红灯小半个月油钱没了，还危险。"
               "注意：2022年4月新版记分规定沿用了6分标准（曾有征求意见稿拟调整为记1分，最终未采纳），"
               "考试以现行6分为准。黄灯亮了稳稳刹住。")
    conn.execute("UPDATE questions SET explanation=?, version=2, updated_at=? WHERE id='q07'",
                 (new_exp, ts))
    conn.execute("""INSERT OR REPLACE INTO questions_history
        (question_id,version,chapter_id,type,stem,options,answer,explanation,tags,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (old["id"], 2, old["chapter_id"], old["type"], old["stem"], old["options"],
         old["answer"], new_exp, old["tags"], ts))


def gen_practice(conn, user, uid, questions, clock):
    rng = random.Random({"李雷": 42, "韩梅梅": 7, "张教练": 99}[user["name"]])
    weak = set(user["weak_tags"])
    wronged = []
    for q in questions:
        if rng.random() > 0.92:
            continue  # 少量题还没练到
        p = user["base_p"]
        if weak & set(q["tags"]):
            p = user["weak_p"]
        if user["name"] == "李雷" and q["id"] == "q07":
            p = 0.0  # 强制答错，用于演示旧版本错题
        ok = rng.random() < p
        selected = q["answer"] if ok else (q["answer"] + 1) % len(q["options"])
        ts = clock().isoformat(timespec="seconds")
        insert_answer(conn, uid, q, "chapter", selected, ts)
        if not ok:
            wronged.append(q["id"])
    return wronged


def gen_redos(conn, user, uid, questions, clock, wronged):
    rng = random.Random({"李雷": 5, "韩梅梅": 8, "张教练": 100}[user["name"]])
    qmap = {q["id"]: q for q in questions}
    # 大约一半错题重做并答对（已掌握）；李雷的 q07 不重做，保留为"题库已更新"的旧错题
    for qid in wronged:
        if user["name"] == "李雷" and qid == "q07":
            continue
        if rng.random() < 0.55:
            ts = clock().isoformat(timespec="seconds")
            insert_answer(conn, uid, qmap[qid], "wrongbook", qmap[qid]["answer"], ts)


def gen_mock_exams(conn, user, uid, questions, dates):
    rng = random.Random({"李雷": 11, "韩梅梅": 22, "张教练": 33}[user["name"]])
    for idx, (score, day) in enumerate(zip(user["exam_scores"], dates)):
        paper = questions[:]
        rng.shuffle(paper)
        total = len(paper)
        target_correct = round(score * total / 100)
        wrong_idx = set(rng.sample(range(total), total - target_correct))
        # 李雷在模拟中 q07 答对，保留其 v1 旧错题状态用于演示
        if user["name"] == "李雷":
            pos = next(i for i, q in enumerate(paper) if q["id"] == "q07")
            if pos in wrong_idx:
                wrong_idx.discard(pos)
                cand = next(i for i in range(total)
                            if i not in wrong_idx and paper[i]["id"] != "q07")
                wrong_idx.add(cand)
        started = datetime(2026, 9, day, 10, 0, tzinfo=timezone.utc)
        finished = started + timedelta(minutes=rng.randint(18, 38))
        paper_json = []
        for i, q in enumerate(paper):
            selected = q["answer"] if i not in wrong_idx else (q["answer"] + 1) % len(q["options"])
            paper_json.append({"question_id": q["id"], "version": q["version"],
                               "chapter_id": q["chapter_id"], "type": q["type"],
                               "stem": q["stem"], "options": q["options"],
                               "answer": q["answer"], "explanation": q["explanation"],
                               "tags": q["tags"], "selected": selected})
        cur = conn.execute("""INSERT INTO mock_exams
            (user_id,total,correct_count,score,status,started_at,finished_at,duration_seconds,questions_json)
            VALUES(?,?,?,?,'finished',?,?,?,?)""",
            (uid, total, total - len(wrong_idx), score,
             started.isoformat(timespec="seconds"), finished.isoformat(timespec="seconds"),
             int((finished - started).total_seconds()),
             json.dumps(paper_json, ensure_ascii=False)))
        exam_id = cur.lastrowid
        for item in paper_json:
            q = {"id": item["question_id"], "version": item["version"],
                 "chapter_id": item["chapter_id"], "type": item["type"],
                 "stem": item["stem"], "options": item["options"],
                 "answer": item["answer"], "explanation": item["explanation"],
                 "tags": item["tags"]}
            insert_answer(conn, uid, q, "mock", item["selected"],
                          finished.isoformat(timespec="seconds"), context_id=exam_id)


def run(reset=False):
    if reset and os.path.exists(db.DB_PATH):
        os.remove(db.DB_PATH)
    db.init_db()
    with db.get_conn() as conn:
        seed_chapters_questions(conn)
        conn.execute("DELETE FROM answer_records")
        conn.execute("DELETE FROM wrong_questions")
        conn.execute("DELETE FROM mock_exams")
        for u in USERS:
            conn.execute(
                "INSERT OR IGNORE INTO users(name,role,created_at) VALUES(?,?,?)",
                (u["name"], u["role"],
                 datetime(2026, 8, 20, tzinfo=timezone.utc).isoformat(timespec="seconds")))
        users = {r["name"]: r["id"]
                 for r in conn.execute("SELECT id,name FROM users").fetchall()}

        clock = [datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)]

        def advance():
            clock[0] += timedelta(hours=5)
            return clock[0]

        v1_questions = all_questions(conn)
        wronged_map = {}
        for u in USERS:
            uid = users[u["name"]]
            wronged = gen_practice(conn, u, uid, v1_questions, advance)
            wronged_map[u["name"]] = wronged
        for u in USERS:
            uid = users[u["name"]]
            gen_redos(conn, u, uid, v1_questions, advance, wronged_map[u["name"]])

        conn.commit()
        update_q07_v2(conn)   # 9/10 题库迭代
        conn.commit()

        cur_questions = all_questions(conn)
        for u in USERS:
            uid = users[u["name"]]
            gen_mock_exams(conn, u, uid, cur_questions, [10, 11, 12])
        conn.commit()

    print("seed done. db =", db.DB_PATH)


if __name__ == "__main__":
    import sys
    run(reset="--reset" in sys.argv)
