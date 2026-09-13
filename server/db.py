# -*- coding: utf-8 -*-
"""SQLite 数据访问层。
设计要点：questions 表保存题库的"当前版本"，questions_history 保存每个历史版本；
answer_records 保存答题当时的题目快照(stem/options/answer/explanation 全量冗余)，
所以题库无论怎么更新，旧错题永远能按当时的样子回看。
wrong_questions 是错题本（最新一次答错=active；重做答对=resolved）。
"""
import sqlite3, json, os, threading
from datetime import datetime, timezone

DB_PATH = os.environ.get("KM_DB", os.path.join(os.path.dirname(__file__), "..", "data", "km1.db"))
_lock = threading.Lock()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  role TEXT NOT NULL DEFAULT 'student',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chapters(
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0,
  description TEXT
);
CREATE TABLE IF NOT EXISTS questions(
  id TEXT PRIMARY KEY,
  chapter_id TEXT NOT NULL,
  type TEXT NOT NULL,
  stem TEXT NOT NULL,
  options TEXT NOT NULL,          -- JSON array
  answer INTEGER NOT NULL,
  explanation TEXT NOT NULL,
  tags TEXT NOT NULL DEFAULT '[]',
  version INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS questions_history(
  question_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  chapter_id TEXT NOT NULL,
  type TEXT NOT NULL,
  stem TEXT NOT NULL,
  options TEXT NOT NULL,
  answer INTEGER NOT NULL,
  explanation TEXT NOT NULL,
  tags TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(question_id, version)
);
CREATE TABLE IF NOT EXISTS answer_records(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  question_id TEXT NOT NULL,
  question_version INTEGER NOT NULL,
  chapter_id TEXT NOT NULL,
  source TEXT NOT NULL,            -- chapter | wrongbook | mock
  context_id INTEGER,              -- mock_exam id (if mock)
  selected INTEGER,                -- null = 未作答
  is_correct INTEGER NOT NULL,
  -- 答题时刻题目快照（题库更新不影响回看）
  snap_type TEXT, snap_stem TEXT, snap_options TEXT, snap_answer INTEGER,
  snap_explanation TEXT, snap_tags TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ar_user ON answer_records(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ar_uq ON answer_records(user_id, question_id);
CREATE TABLE IF NOT EXISTS wrong_questions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  question_id TEXT NOT NULL,
  question_version_at_wrong INTEGER NOT NULL,  -- 答错时题库版本
  last_wrong_at TEXT NOT NULL,
  resolved_at TEXT,                            -- 非空=已掌握
  wrong_count INTEGER NOT NULL DEFAULT 1,
  UNIQUE(user_id, question_id)
);
CREATE INDEX IF NOT EXISTS idx_wq_user ON wrong_questions(user_id, resolved_at);
CREATE TABLE IF NOT EXISTS mock_exams(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  total INTEGER NOT NULL,
  correct_count INTEGER,
  score INTEGER,                  -- 百分制
  status TEXT NOT NULL DEFAULT 'ongoing',  -- ongoing | finished
  started_at TEXT NOT NULL,
  finished_at TEXT,
  duration_seconds INTEGER,
  questions_json TEXT NOT NULL    -- 冻结的试卷 [{question_id, version, options...snapshot}]
);
CREATE INDEX IF NOT EXISTS idx_me_user ON mock_exams(user_id, status);
"""


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)


if __name__ == "__main__":
    init_db()
    print("db initialized:", DB_PATH)
