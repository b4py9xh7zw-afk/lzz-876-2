# -*- coding: utf-8 -*-
"""科目一模拟考试系统 HTTP 服务（仅标准库）。
学生端: /        教练端: /coach.html
"""
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db
import store
from seed import run as seed_run

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static")

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "KM1/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.address_string(), fmt % args))

    # ---------- 响应工具 ----------
    def _send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _err(self, msg, status=400):
        self._send_json({"error": msg}, status)

    def _read_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        raw = self.rfile.read(n)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            raise ValueError("请求体不是合法 JSON")

    def _uid(self):
        v = self.path.split("?", 1)[1] if "?" in self.path else ""
        for kv in v.split("&"):
            if kv.startswith("user_id="):
                try:
                    return int(kv.split("=", 1)[1])
                except ValueError:
                    return None
        return None

    # ---------- 静态文件 ----------
    def _serve_static(self, rel):
        if rel in ("", "/"):
            rel = "index.html"
        rel = rel.lstrip("/")
        # 防目录穿越
        target = os.path.normpath(os.path.join(STATIC_DIR, rel))
        if not target.startswith(os.path.abspath(STATIC_DIR)):
            return self._err("forbidden", 403)
        if not os.path.isfile(target):
            return self._err("not found", 404)
        ext = os.path.splitext(target)[1]
        with open(target, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPES.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ---------- 路由 ----------
    def do_GET(self):
        p = self.path.split("?", 1)[0]
        api = {
            r"^/api/chapters$": self.h_chapters,
            r"^/api/practice/([a-z0-9]+)$": self.h_practice,
            r"^/api/wrong$": self.h_wrong_list,
            r"^/api/wrong/practice$": self.h_wrong_practice,
            r"^/api/mock$": self.h_mock_list,
            r"^/api/mock/(\d+)$": self.h_mock_detail,
            r"^/api/overview$": self.h_overview,
            r"^/api/coach/students$": lambda: self._send_json(store.coach_students()),
            r"^/api/coach/students/(\d+)$": self.h_coach_detail,
            r"^/api/admin/questions$": lambda: self._send_json(store.admin_list_questions()),
            r"^/api/admin/questions/([a-z0-9]+)/versions$": self.h_admin_versions,
        }.items()
        for pat, fn in api:
            m = re.match(pat, p)
            if m:
                try:
                    fn(*m.groups())
                except LookupError as e:
                    self._err(str(e), 404)
                except (ValueError, RuntimeError, TimeoutError) as e:
                    self._err(str(e), 400)
                except Exception as e:
                    import traceback; traceback.print_exc()
                    self._err("服务器内部错误: %s" % e, 500)
                return
        if p.startswith("/api/"):
            return self._err("接口不存在", 404)
        self._serve_static(p)

    def do_POST(self):
        p = self.path.split("?", 1)[0]
        try:
            data = self._read_json()
        except ValueError as e:
            return self._err(str(e))
        try:
            if p == "/api/users":
                role = data.get("role", "student")
                if role not in ("student", "coach"):
                    return self._err("角色非法")
                u = store.get_or_create_user(data.get("name", ""), role)
                return self._send_json(u)
            if p == "/api/users/by-name":
                from db import get_conn
                with get_conn() as conn:
                    r = conn.execute("SELECT * FROM users WHERE name=?",
                                     ((data.get("name") or "").strip(),)).fetchone()
                return self._send_json(dict(r) if r else None, 200)
            # 教练端题库维护接口不需要学员 user_id
            m = re.match(r"^/api/admin/questions/([a-z0-9]+)$", p)
            if m:
                return self._send_json(store.admin_update_question(m.group(1), data))
            uid = self._uid_from_body(data)
            if p == "/api/answers/chapter":
                return self._send_json(store.submit_chapter_answer(
                    uid, data["question_id"], data.get("selected")))
            if p == "/api/answers/wrongbook":
                return self._send_json(store.submit_wrongbook_answer(
                    uid, data["question_id"], data.get("selected")))
            if p == "/api/mock/start":
                return self._send_json(store.mock_start(uid))
            m = re.match(r"^/api/mock/(\d+)/submit$", p)
            if m:
                return self._send_json(store.mock_submit(
                    uid, int(m.group(1)), data.get("answers", {}),
                    data.get("duration_seconds")))
            return self._err("接口不存在", 404)
        except LookupError as e:
            self._err(str(e), 404)
        except (ValueError, RuntimeError, TimeoutError) as e:
            self._err(str(e), 400)
        except KeyError as e:
            self._err("缺少参数: %s" % e, 400)
        except Exception as e:
            import traceback; traceback.print_exc()
            self._err("服务器内部错误: %s" % e, 500)

    def _uid_from_body(self, data):
        uid = data.get("user_id") or self._uid()
        if uid is None:
            raise ValueError("缺少 user_id")
        if not store.get_user(int(uid)):
            raise LookupError("用户不存在")
        return int(uid)

    # GET handlers
    def h_chapters(self):
        uid = self._uid()
        if uid is None:
            raise ValueError("缺少 user_id")
        self._send_json(store.list_chapters(uid))

    def h_practice(self, ch):
        uid = self._uid()
        if uid is None:
            raise ValueError("缺少 user_id")
        self._send_json(store.get_practice(uid, ch))

    def h_wrong_list(self):
        uid = self._uid()
        if uid is None:
            raise ValueError("缺少 user_id")
        query = self.path.split("?", 1)[1] if "?" in self.path else ""
        scope = "resolved" if "scope=resolved" in query else "active"
        self._send_json(store.list_wrong(uid, scope))

    def h_wrong_practice(self):
        uid = self._uid()
        if uid is None:
            raise ValueError("缺少 user_id")
        self._send_json(store.wrong_practice_set(uid))

    def h_mock_list(self):
        uid = self._uid()
        if uid is None:
            raise ValueError("缺少 user_id")
        self._send_json(store.mock_list(uid))

    def h_mock_detail(self, exam_id):
        uid = self._uid()
        if uid is None:
            raise ValueError("缺少 user_id")
        self._send_json(store.mock_detail(uid, int(exam_id)))

    def h_overview(self):
        uid = self._uid()
        if uid is None:
            raise ValueError("缺少 user_id")
        self._send_json(store.overview(uid))

    def h_coach_detail(self, uid_str):
        self._send_json(store.coach_student_detail(int(uid_str)))

    def h_admin_versions(self, qid):
        self._send_json(store.admin_get_versions(qid))


def main():
    db.init_db()
    # 空库自动播种（首启）
    from db import get_conn
    need_seed = False
    with get_conn() as conn:
        if conn.execute("SELECT COUNT(*) n FROM questions").fetchone()["n"] == 0:
            need_seed = True
    if need_seed:
        seed_run(reset=False)
    port = int(os.environ.get("PORT", "8000"))
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print("科目一模拟考试系统已启动: http://localhost:%d" % port)
    print("  学生端 /  |  教练端 /coach.html")
    srv.serve_forever()


if __name__ == "__main__":
    main()
