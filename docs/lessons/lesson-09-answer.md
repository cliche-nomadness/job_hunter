# Lesson 9 · 参考答案（里程碑版 server.py）

> 用途：对照你自己的实现查漏补缺。**先自己写完再来看答案**，效果最好。
> 注意：这是"完整可运行"的参考版；你不需要改得和它一模一样，功能和行为一致即可。

---

## 0. 两个前置小修（答案里已含，你也要修）

1. **`resume.py` 的相对路径坑**：`resume.py` 用 `RESUME_FILE = "resume.md"`，bot.py 从 `cli/` 运行时可能找不到根目录的 resume.md。和 server.py 修 `applications.json` 时一样，用 `__file__` 定位：

```python
# resume.py 顶部（替换原来的 RESUME_FILE 定义）
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
RESUME_FILE = str(BASE_DIR / "resume.md")
```

2. **`run_bot.cmd` 要补 DEEPSEEK_API_KEY**：`简历意见`命令要调 DeepSeek，但 run_bot.cmd 只设了 FEISHU 三个变量。加上：

```cmd
set DEEPSEEK_API_KEY=你的DeepSeekKey
```

3. 顺手删掉残留的 `cli\applications.json`（server.py 现在用根目录的）。

---

## 1. 参考版 server.py（完整）

```python
# cli/server.py —— 校招虾后端（L9 里程碑版）
from fastapi import FastAPI, Request, Response
from pydantic import BaseModel
from pathlib import Path
from application_book import ApplicationBook, TRANSITIONS
from resume import read_resume, get_resume_advice
import json
import os
import time
import csv
import requests
import lark_oapi as lark
from lark_oapi.core.model.raw_request import RawRequest

# ---- 飞书凭证（环境变量）----
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
FEISHU_VERIFICATION_TOKEN = os.environ.get("FEISHU_VERIFICATION_TOKEN", "")

BASE_DIR = Path(__file__).resolve().parent.parent
app = FastAPI(title="校招虾 API")
book = ApplicationBook(str(BASE_DIR / "applications.json"))

# ---- 岗位数据（CLI 与飞书各自加载，共用 jobs.csv）----
JOBS_FILE = str(BASE_DIR / "jobs.csv")

def load_jobs():
    global jobs
    if os.path.exists(JOBS_FILE):
        with open(JOBS_FILE, "r", encoding="utf-8-sig") as f:
            jobs = list(csv.DictReader(f))
    else:
        jobs = []

jobs = []
load_jobs()

# ---- 发消息工具（会员卡：2 小时有效，缓存）----
_token_cache = {"token": "", "expire_at": 0}

def get_tenant_access_token():
    if _token_cache["token"] and _token_cache["expire_at"] > time.time():
        return _token_cache["token"]
    resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}, timeout=10)
    data = resp.json()
    _token_cache["token"] = data["tenant_access_token"]
    _token_cache["expire_at"] = time.time() + data["expire"] - 60
    return _token_cache["token"]

def send_text(open_id, text):
    token = get_tenant_access_token()
    resp = requests.post(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
        headers={"Authorization": f"Bearer {token}"},
        json={"receive_id": open_id, "msg_type": "text",
              "content": json.dumps({"text": text})}, timeout=10)
    print("发送结果:", resp.status_code)

# ---- 去重（message_id，官方推荐；event_id 兜底）----
_processed_messages = {}

def _is_dup(key):
    now = time.time()
    stale = [k for k, t in _processed_messages.items() if now - t > 600]
    for k in stale:
        _processed_messages.pop(k, None)
    if key in _processed_messages:
        return True
    _processed_messages[key] = now
    return False

# ---- 命令路由（L9 核心）----
def handle_command(open_id, text):
    parts = text.split()
    if not parts:
        return
    cmd = parts[0]

    if cmd == "投递":
        cmd_add(open_id, parts)
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


def cmd_add(open_id, parts):
    if len(parts) != 3:
        send_text(open_id, "格式：投递 公司 岗位\n例：投递 字节 后端")
        return
    _, company, position = parts
    book.add(company, position)
    send_text(open_id, f"✅ 已记录 {company} - {position}")


def cmd_progress(open_id):
    if len(book.applications) == 0:
        send_text(open_id, "还没有投递记录")
        return
    lines = [f"{i+1}. {a['company']} - {a['position']} [{a['status']}]"
             for i, a in enumerate(book.applications)]
    send_text(open_id, "你的投递进度：\n" + "\n".join(lines))


def cmd_update(open_id, parts):
    if len(parts) < 2:
        send_text(open_id, "格式：更新 序号 [状态]\n· 更新 1 面试（直接改）\n· 更新 1（列出允许的状态）")
        return
    try:
        idx = int(parts[1]) - 1
    except ValueError:
        send_text(open_id, "序号要是数字，例：更新 1 面试")
        return
    if idx < 0 or idx >= len(book.applications):
        send_text(open_id, "序号超出范围")
        return

    current = book.applications[idx]["status"]
    allowed = TRANSITIONS.get(current, [])

    if len(parts) == 2:                       # 「更新 1」→ 列出能改的状态
        if not allowed:
            send_text(open_id, f"「{current}」已是终态，不能变更")
            return
        lines = "\n".join(f"{i+1}. {s}" for i, s in enumerate(allowed))
        send_text(open_id, f"当前「{current}」，可以变为：\n{lines}")
        return

    new_status = parts[2]
    if not allowed:
        send_text(open_id, f"「{current}」已是终态，不能变更")
        return
    if new_status not in allowed:
        send_text(open_id, f"不能从「{current}」变成「{new_status}」\n允许：{' / '.join(allowed)}")
        return
    book.update_status(idx, new_status)
    send_text(open_id, f"✅ 已更新为「{new_status}」")


def cmd_delete(open_id, parts):
    if len(parts) != 2:
        send_text(open_id, "格式：删除 序号\n例：删除 1")
        return
    try:
        idx = int(parts[1]) - 1
    except ValueError:
        send_text(open_id, "序号要是数字")
        return
    if idx < 0 or idx >= len(book.applications):
        send_text(open_id, "序号超出范围")
        return
    removed = book.applications[idx]
    book.delete(idx)
    send_text(open_id, f"🗑️ 已删除 {removed['company']} - {removed['position']}")


def cmd_jobs(open_id, parts):
    if len(jobs) == 0:
        send_text(open_id, "没有岗位数据，请先准备 jobs.csv")
        return
    city = parts[1] if len(parts) > 1 else ""
    keyword = parts[2] if len(parts) > 2 else ""
    result = [j for j in jobs
              if (not city or j["城市"] == city)
              and (not keyword or keyword in j["岗位"])]
    if len(result) == 0:
        send_text(open_id, "没有符合条件的岗位")
        return
    lines = [f"{i+1}. [{j['城市']}] {j['公司']} - {j['岗位']}" for i, j in enumerate(result)]
    send_text(open_id, "匹配岗位：\n" + "\n".join(lines))


def cmd_advice(open_id, parts):
    if len(parts) != 2:
        send_text(open_id, "格式：简历意见 序号（序号看「岗位」的列表）")
        return
    if len(jobs) == 0:
        send_text(open_id, "没有岗位数据")
        return
    try:
        idx = int(parts[1]) - 1
    except ValueError:
        send_text(open_id, "序号要是数字")
        return
    if idx < 0 or idx >= len(jobs):
        send_text(open_id, "序号超出范围")
        return

    job = jobs[idx]
    resume_text = read_resume()
    if not resume_text:
        send_text(open_id, "没有简历文件 resume.md")
        return

    send_text(open_id, "AI 正在分析，请稍候...")     # 先安抚用户
    advice = get_resume_advice(job["岗位"], job["JD"], resume_text)
    send_text(open_id, advice if advice else "分析失败，请检查 DEEPSEEK_API_KEY")


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


# ---- 事件处理（长连接/回调通用）----
def do_message(data: lark.im.v1.P2ImMessageReceiveV1) -> None:
    # 去重：message_id 优先（官方推荐），event_id 兜底
    msg_id = data.event.message.message_id
    event_id = getattr(data.header, "event_id", None) if data.header else None
    dedup_key = msg_id or event_id
    if dedup_key and _is_dup(dedup_key):
        print(">>> 重复消息，跳过:", dedup_key)
        return

    event = data.event
    open_id = event.sender.sender_id.open_id
    content = json.loads(event.message.content)
    text = content.get("text", "").strip()
    print(f">>> 收到消息 from {open_id}: {text}")
    handle_command(open_id, text)


event_handler = (
    lark.EventDispatcherHandler.builder("", FEISHU_VERIFICATION_TOKEN)
    .register_p2_im_message_receive_v1(do_message)
    .build()
)


@app.post("/feishu/event")
async def feishu_event(request: Request):
    req = RawRequest()
    req.uri = str(request.url.path)
    req.headers = dict(request.headers)
    req.body = await request.body()
    resp = event_handler.do(req)
    return Response(content=resp.content, status_code=resp.status_code, headers=resp.headers)


# ---- HTTP API（L6，保留）----
@app.get("/applications")
def get_all():
    return book.applications


class NewApplication(BaseModel):
    company: str
    position: str


@app.post("/applications")
def add_one(item: NewApplication):
    book.add(item.company, item.position)
    return {"ok": True, "data": item.model_dump()}


@app.get("/")
def root():
    return {"message": "校招虾服务已启动!"}
```

---

## 2. 和你自己版本对照的重点

| 检查点 | 参考做法 | 你自己的 |
|---|---|---|
| `handle_command` 只做分发 | 7 个 `cmd_*` 各管一摊 | ？ |
| `cmd_update` 的「更新 1」/「更新 1 状态」双路径 | 列允许状态 vs 直接改 | ？ |
| 边界：非数字/越界/终态/空数据 | 全部 try/except + 友好提示 | ？ |
| `jobs` 加载 | `load_jobs()` + 启动时调用 | ？ |
| 去重键 | `message_id` 优先 | ？ |

## 3. 验收标准

- 7 个命令 + 帮助全部可跑；
- 所有边界情况**不崩溃**，只回友好提示；
- 私聊/群聊行为稳定（去重生效）；
- `简历意见` 能出结果（注意 run_bot.cmd 要设 DEEPSEEK_API_KEY）。

---

## 4. 自测题答案

1. **handle_command 和 do_message 的关系？** do_message 是 SDK 调用的事件入口（去重/解析/取 open_id 和文本），handle_command 是分发器（按第一个词调对应 cmd_*）。拆开是为了单一职责：接收、分发、执行各管一摊，加新命令只动一行路由。
2. **「更新 1」vs「更新 1 面试」？** 「更新 1」查允许的状态列出来让用户选（引导式）；「更新 1 面试」直接校验并更新。两条路降低用户记忆负担。
3. **为什么用 `TRANSITIONS.get(current, [])`？** 旧数据可能含不在状态机里的状态（L1 时代自由输入过），`TRANSITIONS[current]` 会 KeyError 崩溃，`.get(..., [])` 返回空列表走"终态"提示——防御性编程。
4. **筛选可选参数？** `(not city or j["城市"] == city)`：空字符串是 falsy，`not city` 为 True 时 or 短路不过滤；非空才比较。用 or 短路实现"可选过滤"。
5. **长连接不怕 AI 慢调用？** 回调模式要求 3 秒内回 HTTP 响应（飞书等着）；长连接没有响应死线（飞书递完话就走），所以能"先回分析中，再发结果"。
6. **为什么 server.py 也要 load_jobs()？** CLI 和飞书是两个进程（两个前台），内存互不相通；共享的是文件（jobs.csv/applications.json）而不是内存，所以各自要加载数据。
