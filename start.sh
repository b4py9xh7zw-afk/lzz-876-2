#!/usr/bin/env bash
# 一键启动科目一模拟考试系统（仅依赖 Python 3.8+，无需安装任何包）
set -e
cd "$(dirname "$0")"
PORT="${PORT:-8000}"
if [ ! -f data/km1.db ]; then
  echo "首次启动：初始化题库与演示数据…"
  python3 server/seed.py --reset
fi
echo "学生端:  http://localhost:${PORT}/"
echo "教练端:  http://localhost:${PORT}/coach.html"
exec env PORT="$PORT" python3 server/server.py
