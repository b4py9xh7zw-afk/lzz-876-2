# 驾校科目一模拟考试系统

按"**章节练题 → 错题重做 → 全真模拟**"主线设计的科目一刷题系统，含教练诊断后台。
纯 Python 标准库后端（零依赖）+ 原生 JS 移动端页面，移动端按碎片时间刷题优化，
错题解析全部用"讲人话"的口语风格。

## 快速启动

```bash
bash start.sh
# 或：python3 server/seed.py --reset && python3 server/server.py
```

- 学员端（移动优先，手机浏览器直接开）：<http://localhost:8000/>
- 教练后台（桌面宽屏自适应）：<http://localhost:8000/coach.html>

演示账号（登录页可一键填入）：

| 账号 | 状态 | 在教练看板上的样子 |
|---|---|---|
| **李雷** | 模拟均分 81、错题积压 34 道、法规题薄弱 | 🔴 暂不建议预约 |
| **韩梅梅** | 均分 88.7、标志标线类易错 | 🟠 再巩固一下 |
| 新姓名 | 自动注册新学员，数据不足 | ⚪ 数据不足 |

> 预置 3 场模拟、章节练习与错题历史，并内置一次**题库版本迭代演示**
> （q07"闯红灯记分"解析于 9/10 从 v1 更新到 v2，李雷的错题仍按 v1 回看）。

## 功能地图

### 学员端（底部 4 个 Tab）
- **首页**：正确率、待攻克错题数、最近模拟分；易错法规标签云；快捷入口。
- **章节练习**：4 大章节（法规 / 交通信号 / 安全文明 / 操作知识），进度条；
  逐题作答、即时反馈，**解析口语化**（"黄实线是一堵看不见的墙…"）。
- **错题本**：
  - 「待重做」：答错自动入本，重做答对即移出；
  - 「已掌握」：历史永久可回看；
  - **题库更新过的错题带橙色标记**，展开即按"当时的旧版本"回看，
    还可一键对比"最新版本题目"，明确改了什么；
  - 错题重做按答错时锁定的版本判分。
- **全真模拟**：45 分钟倒计时、答题卡、未答提醒、到时自动交卷；
  支持断网/误刷新后续考；百分制折算、90 分合格；交卷后整卷解析回看；
  错题自动同步进错题本。

### 教练后台
- **学员看板**：近 3 场均分、最高分、待清错题、易错法规标签，
  以及三档**预约考试建议**（可以预约 / 再巩固 / 暂不建议）+ 文字理由。
- **学员诊断**：易错法规 TOP 柱状图、各章节掌握度、当前错题明细
  （含旧版本题目标记与解析）。
- **题库维护**：编辑题干/选项/答案/解析/标签，保存即生成新版本；
  可查看每题的完整版本历史。

## 题库更新后旧错题为什么还能看？（核心设计）

```
questions            题库当前版本（version 递增）
questions_history    每个题目的全部历史版本
answer_records       每次答题都冗余保存"答题那一刻"的题目快照
                     （题干/选项/答案/解析/版本号）
wrong_questions      错题本，记录答错时锁定的版本
```

- 错题列表展示的是 **answer_records 里的快照**，题库怎么改都不受影响；
- 错题重做时按 `question_version_at_wrong` 找当时的快照判分；
- `outdated` 标记（快照版本 ≠ 题库当前版本）驱动前端的"题库已更新"提示和版本对比弹窗；
- 模拟考试开考时服务端冻结整卷快照，考中题库更新也不影响这一场。

## 目录结构

```
server/
  seed_data.py   60 道精选题库（4 章，标签，口语解析）
  db.py          SQLite 建表/连接
  seed.py        初始化 + 演示数据（用户/练习/错题/模拟/一次题库迭代）
  store.py       业务逻辑（练习、错题本、模拟、教练统计、题库版本）
  server.py      标准库 HTTP 服务 + REST 路由 + 静态托管
static/
  index.html/app.js/style.css   学员端 SPA
  coach.html/coach.js           教练后台
data/km1.db      SQLite 数据文件（自动生成）
```

## 主要 API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /api/users | 登录/自动注册 |
| GET | /api/chapters?user_id= | 章节及掌握进度 |
| GET | /api/practice/{ch}?user_id= | 取章节题目（不含答案） |
| POST | /api/answers/chapter | 提交章节作答，返回对错+解析 |
| GET | /api/wrong?user_id=&scope=active\|resolved | 错题本（含快照） |
| GET | /api/wrong/practice?user_id= | 错题重做题组 |
| POST | /api/answers/wrongbook | 重做作答，答对即掌握 |
| POST | /api/mock/start | 开考/续考（服务端冻结试卷） |
| POST | /api/mock/{id}/submit | 交卷判分 |
| GET | /api/mock/{id}?user_id= | 成绩与整卷解析 |
| GET | /api/coach/students | 学员看板（易错法规+预约建议） |
| GET | /api/coach/students/{id} | 学员详细诊断 |
| GET | /api/admin/questions | 题库列表 |
| POST | /api/admin/questions/{id} | 更新题目（生成新版本） |
| GET | /api/admin/questions/{id}/versions | 版本历史 |

## 重置演示数据

```bash
python3 server/seed.py --reset
```
