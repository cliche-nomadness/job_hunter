# Lesson 9 · CLI → 飞书机器人端到端整合（★里程碑：可用的飞书版）

> 目标：把 CLI 的**全部能力**搬进飞书，处理边界情况，达到"日常能用"的完整度。
> 前置：L1–L8 全部完成（长连接模式跑通）。
> 完成后你将拥有：**在飞书里能完成求职全流程管理的校招虾**。

---

## 0. 本课全景：还差什么

| 功能 | CLI | 飞书（现在） | 飞书（本课做完后） |
|---|---|---|---|
| 添加投递 | ✅ | ✅ 投递 公司 岗位 | ✅ |
| 查看进度 | ✅ | ✅ 我的进度 | ✅ |
| **更新状态** | ✅ | ❌ | ✅ 更新 序号 状态 |
| **删除投递** | ✅ | ❌ | ✅ 删除 序号 |
| **筛选岗位** | ✅ | ❌ | ✅ 岗位 [城市] [关键词] |
| **AI 简历意见** | ✅ | ❌ | ✅ 简历意见 序号 |
| **边界/帮助** | 部分 | ❌ | ✅ 帮助 |

---

## Part A · 命令路由（新概念，本课核心）

### 1. 为什么需要"路由"

你的 `do_message` 现在是一长串 `if/elif`（投递、我的进度、支持…）。命令一多（本课要加到 6 个），堆在一起会很难读。**路由** = 把"这句话是什么命令"和"命令该干什么"分开：一个入口函数负责**分发**，具体逻辑各自成函数。

```python
def handle_command(open_id, text):
    """用户消息入口：解析命令 → 分发。"""
    parts = text.split()
    if not parts:
        return
    cmd = parts[0]                      # 第一个词 = 命令

    if cmd == "投递":
        cmd_add(open_id, parts)          # 各自函数，各管一摊
    elif cmd == "我的进度":
        cmd_progress(open_id)
    elif cmd == "更新":
        cmd_update(open_id, parts)
    elif cmd == "删除":
        cmd_delete(open_id, parts)
    elif cmd == "岗位":
        cmd_jobs(open_id, parts)
    elif cmd == "简历意见":
        cmd_advice(open_id, parts)
    elif cmd in ("帮助", "help", "?"):
        cmd_help(open_id)
    else:
        send_text(open_id, "没听懂，发「帮助」看看我会什么")
```

**这就是 L10 要学的 LangGraph 意图路由的"手工版"**：先判断用户想干嘛，再分发给对应处理。理解了它，L10 你会秒懂。

### 2. 改造 do_message

```python
def do_message(data: lark.im.v1.P2ImMessageReceiveV1) -> None:
    # （去重逻辑保持不变，见 L8）
    ...
    content = json.loads(event.message.content)
    text = content.get("text", "").strip()
    print(f">>> 收到消息 from {open_id}: {text}")
    handle_command(open_id, text)       # ← 原来一长串 if/elif 换成这一行
```

---

## Part B · 三个新功能 + 两个已有功能的升级

### B1. 添加投递（微调：格式校验更友好）

```python
def cmd_add(open_id, parts):
    if len(parts) != 3:
        send_text(open_id, "格式：投递 公司 岗位\n例：投递 字节 后端")
        return
    _, company, position = parts
    book.add(company, position)
    send_text(open_id, f"✅ 已记录 {company} - {position}")
```

### B2. 查看进度（复用已有逻辑）

```python
def cmd_progress(open_id):
    if len(book.applications) == 0:
        send_text(open_id, "还没有投递记录")
        return
    lines = [f"{i+1}. {a['company']} - {a['position']} [{a['status']}]"
             for i, a in enumerate(book.applications)]
    send_text(open_id, "你的投递进度：\n" + "\n".join(lines))
```

### B3. 更新状态（核心，复用 L4 的状态机）

```python
def cmd_update(open_id, parts):
    if len(parts) < 2:
        send_text(open_id, "格式：更新 序号 [状态]\n· 更新 1 面试（直接改）\n· 更新 1（列出允许的状态）")
        return
    try:
        idx = int(parts[1]) - 1
    except ValueError:
        send_text(open_id, "序号要是数字，例：更新 1 面试"); return
    if idx < 0 or idx >= len(book.applications):
        send_text(open_id, "序号超出范围"); return

    current = book.applications[idx]["status"]
    allowed = TRANSITIONS.get(current, [])

    if len(parts) == 2:                       # 「更新 1」→ 列出能改的状态
        if not allowed:
            send_text(open_id, f"「{current}」已是终态，不能变更"); return
        lines = "\n".join(f"{i+1}. {s}" for i, s in enumerate(allowed))
        send_text(open_id, f"当前「{current}」，可以变为：\n{lines}")
        return

    new_status = parts[2]
    if not allowed:                           # 终态
        send_text(open_id, f"「{current}」已是终态，不能变更"); return
    if new_status not in allowed:             # 非法迁移
        send_text(open_id, f"不能从「{current}」变成「{new_status}」\n允许：{' / '.join(allowed)}")
        return
    book.update_status(idx, new_status)
    send_text(open_id, f"✅ 已更新为「{new_status}」")
```

> 关键：**把 L4 状态机的校验逻辑（终态/非法迁移）从"打印"升级为"告诉用户为什么不行"**——同样的规则，现在以对话的形式反馈。

### B4. 删除投递

```python
def cmd_delete(open_id, parts):
    if len(parts) != 2:
        send_text(open_id, "格式：删除 序号\n例：删除 1"); return
    try:
        idx = int(parts[1]) - 1
    except ValueError:
        send_text(open_id, "序号要是数字"); return
    if idx < 0 or idx >= len(book.applications):
        send_text(open_id, "序号超出范围"); return
    removed = book.applications[idx]
    book.delete(idx)
    send_text(open_id, f"🗑️ 已删除 {removed['company']} - {removed['position']}")
```

### B5. 筛选岗位（⚠️ server.py 要先有 jobs 数据）

**重要**：CLI 的 `main.py` 里有 `load_jobs()`，但 `server.py` 里**没有**！飞书端要筛选岗位，得先让 server.py 也能读 jobs.csv：

```python
import csv   # 顶部加

JOBS_FILE = str(BASE_DIR / "jobs.csv")

def load_jobs():
    global jobs
    if os.path.exists(JOBS_FILE):
        with open(JOBS_FILE, "r", encoding="utf-8-sig") as f:
            jobs = list(csv.DictReader(f))
    else:
        jobs = []

jobs = []
load_jobs()   # 启动时加载一次

def cmd_jobs(open_id, parts):
    if len(jobs) == 0:
        send_text(open_id, "没有岗位数据，请先准备 jobs.csv"); return
    city = parts[1] if len(parts) > 1 else ""
    keyword = parts[2] if len(parts) > 2 else ""
    result = [j for j in jobs
              if (not city or j["城市"] == city)
              and (not keyword or keyword in j["岗位"])]
    if len(result) == 0:
        send_text(open_id, "没有符合条件的岗位"); return
    lines = [f"{i+1}. [{j['城市']}] {j['公司']} - {j['岗位']}" for i, j in enumerate(result)]
    send_text(open_id, "匹配岗位：\n" + "\n".join(lines))
```

### B6. AI 简历意见（长连接模式没 3 秒超时，放心调慢 API）

```python
from resume import read_resume, get_resume_advice   # 顶部加（复用 L3 的函数）

def cmd_advice(open_id, parts):
    if len(parts) != 2:
        send_text(open_id, "格式：简历意见 序号（序号看「岗位」的列表）"); return
    if len(jobs) == 0:
        send_text(open_id, "没有岗位数据"); return
    try:
        idx = int(parts[1]) - 1
    except ValueError:
        send_text(open_id, "序号要是数字"); return
    if idx < 0 or idx >= len(jobs):
        send_text(open_id, "序号超出范围"); return

    job = jobs[idx]
    resume_text = read_resume()
    if not resume_text:
        send_text(open_id, "没有简历文件 resume.md"); return

    send_text(open_id, "AI 正在分析，请稍候...")     # 先安抚用户
    advice = get_resume_advice(job["岗位"], job["JD"], resume_text)
    send_text(open_id, advice if advice else "分析失败，请检查 DEEPSEEK_API_KEY")
```

> **长连接的好处再次体现**：回调模式 3 秒必须响应，DeepSeek 动辄 10~30 秒肯定超时；长连接没有响应死线，**慢 API 随便调**，还可以"先回一句'分析中'，再回结果"。

### B7. 帮助

```python
def cmd_help(open_id):
    send_text(open_id,
        "我是校招虾 🦐，支持：\n"
        "· 投递 公司 岗位 —— 记录投递\n"
        "· 我的进度 —— 查看投递列表\n"
        "· 更新 序号 状态 —— 更新状态（更新 序号 看可选）\n"
        "· 删除 序号 —— 删除投递\n"
        "· 岗位 城市 关键词 —— 筛选岗位（都可省略）\n"
        "· 简历意见 序号 —— AI 按岗位给简历意见\n"
        "· 帮助 —— 本菜单")
```

---

## Part C · 边界情况（本课质量的体现）

| 情况 | 处理 |
|---|---|
| 命令格式不对 | 每个 cmd 都校验 `len(parts)`，不对就教用户格式 |
| 序号不是数字 | `int()` 包 `try/except`，提示"序号要是数字" |
| 序号越界 | 边界检查 + 友好提示 |
| 终态更新 | 提示"已是终态" |
| 非法迁移 | 列出允许的状态 |
| 数据为空（岗位/进度/简历） | 各自友好提示 |
| 未知命令 | 引导「帮助」 |
| DEEPSEEK_API_KEY 没设 | `get_resume_advice` 已内置提示（L3） |

---

## 验证清单（做完逐条打勾）

- [ ] 「投递 字节 后端」→ ✅ 已记录；`applications.json` 多了记录
- [ ] 「我的进度」→ 列表带序号
- [ ] 「更新 1」→ 列出允许的状态；「更新 1 面试」→ 更新成功
- [ ] 更新**终态**记录 → 拒绝；更新**非法迁移** → 拒绝并列出允许项
- [ ] 「删除 1」→ 删除成功
- [ ] 「岗位 北京」「岗位 北京 前端」→ 正确筛选
- [ ] 「简历意见 1」→ 先回"分析中"，再回 AI 意见
- [ ] 「随便说句话」→ 引导「帮助」
- [ ] 所有边界（越界/非数字/空数据）都不崩溃，只回友好提示

## 弄坏再修（必做）

1. 对**终态**记录执行「更新 1 面试」→ 看拒绝提示。
2. 输入「更新 abc 面试」→ 看"序号要是数字"（验证 try/except 生效）。
3. 把 `jobs.csv` 临时改名 → 「岗位」→ 看"没有岗位数据"→ 改回来。
4. 输入「今天天气怎么样」→ 看引导帮助。

## 自测题（能口头回答才算过关）

- `handle_command` 和 `do_message` 是什么关系？为什么要拆出路由？
- 「更新 1」和「更新 1 面试」两条路径分别做了什么？
- 为什么 `cmd_update` 里要用 `TRANSITIONS.get(current, [])` 而不是 `TRANSITIONS[current]`？
- 筛选岗位时 city/keyword 都是可选参数，列表推导式怎么写才不报错？
- 为什么长连接模式下 AI 慢调用不用担心超时？回调模式会怎样？
- 为什么 server.py 也要 `load_jobs()`？（提示：CLI 和飞书是两个"前台"，各自都要能拿到岗位数据）

---

*做完把更新后的 `server.py` 贴回来，我 review。下一课 L10 进入阶段 3：LangGraph 入门——把这段手工路由升级成真正的 AI 意图路由，并用图编排"简历优化"流程（分析→确认→改写→PDF）。*
