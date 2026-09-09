from fastapi import FastAPI, Request, Response
from pydantic import BaseModel
from pathlib import Path
from application_book import ApplicationBook, TRANSITIONS
from resume import read_resume, get_resume_advice  # 顶部加（复用 L3 的函数）
import json
import os
import time
import csv 
import requests
import lark_oapi as lark
from lark_oapi.core.model.raw_request import RawRequest
from graph_resume import start_optimize, finish_optimize
# ---- 飞书凭证（从环境变量读，不写死在代码里）----
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
FEISHU_VERIFICATION_TOKEN = os.environ.get("FEISHU_VERIFICATION_TOKEN", "")

BASE_DIR = Path(__file__).resolve().parent.parent
app = FastAPI(title="校招虾 API")
book = ApplicationBook(str(BASE_DIR / "applications.json"))
JOBS_FILE = str(BASE_DIR / "jobs.csv")
_token_cache = {"token": "", "expire_at": 0}
# ---- 事件处理：SDK 自动完成 令牌校验 + 挑战处理 + 分发 ----
_processed_messages = {}   # {消息ID: 处理时间戳} —— 用 message_id 去重（官方推荐，event_id 可能被重新生成）

def handle_command(open_id, text):
    load_jobs()   # 每条命令重读 jobs.csv——sync_jobs 定时写完，bot 不重启也能看到新数据
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
    elif cmd == "优化简历":
        cmd_optimize(open_id, parts)
    elif cmd == "确认":
        cmd_confirm(open_id, True)          # ← 恢复
    elif cmd == "取消":
        cmd_confirm(open_id, False)         # ← 恢复
    elif cmd in ("帮助", "help", "?"):
        cmd_help(open_id)
    else:
        send_text(open_id, "发送「帮助」看看我会什么")
def _is_dup(key):
    """判断这个 key 是否已处理过；同时清理超过 10 分钟的旧记录。"""
    now = time.time()
    # 清理过期记录（去重只需覆盖"重复推送窗口"，防止内存无限增长）
    stale = [k for k, t in _processed_messages.items() if now - t > 600]
    for k in stale:
        _processed_messages.pop(k, None)
    if key in _processed_messages:
        return True                      # 见过 → 重复
    _processed_messages[key] = now       # 没见过 → 记下再放行
    return False

def do_message(data: lark.im.v1.P2ImMessageReceiveV1) -> None:
    """收到 im.message.receive_v1 事件时，SDK 调用这个函数（HTTP webhook 模式入口）。"""
    # 去重：优先用 message_id（官方推荐，同一条消息恒定不变），取不到再兜底 event_id
    msg_id = data.event.message.message_id
    event_id = getattr(data.header, "event_id", None) if data.header else None
    dedup_key = msg_id or event_id
    if dedup_key and _is_dup(dedup_key):
        print(">>> 重复消息，跳过:", dedup_key)
        return

    event = data.event
    open_id = event.sender.sender_id.open_id
    content = json.loads(event.message.content)   # content 是"字符串里的 JSON"
    text = content.get("text", "").strip()
    print(f">>> 收到消息 from {open_id}: {text}")
    handle_command(open_id, text)

def handle_message_from_channel(msg):
    """FeishuChannel 长连接消息入口（msg: lark_oapi.channel.InboundMessage）。

    与 do_message（HTTP webhook 入口）共用 handle_command；
    去重逻辑一致（message_id + 10 分钟窗口）。
    """
    msg_id = msg.message_id
    if msg_id and _is_dup(msg_id):
        print(">>> 重复消息，跳过:", msg_id)
        return

    # 单聊直接处理；群聊只有 @ 了机器人才回
    if msg.chat_type != "p2p" and not msg.mentioned_bot:
        print(">>> 群聊未@机器人，忽略")
        return

    open_id = msg.sender_id
    text = (msg.content_text or "").strip()
    # 群聊 @ 场景：content_text 形如 "@校招虾 优化简历 1"，切掉第一段
    if text.startswith("@"):
        parts = text.split(" ", 1)
        text = parts[1].strip() if len(parts) > 1 else ""
    if not text:
        return
    print(f">>> 收到消息 from {open_id}: {text}")
    handle_command(open_id, text)


event_handler = (
    lark.EventDispatcherHandler.builder("", FEISHU_VERIFICATION_TOKEN)  # (加密密钥, 验证令牌)
    .register_p2_im_message_receive_v1(do_message)
    .build()
)


def get_tenant_access_token():
    if _token_cache["token"] and _token_cache["expire_at"] > time.time(): # 有token且未过期
        return _token_cache["token"]
    resp = requests.post( # 没有或者已过期，从飞书获取 token
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
              "content": json.dumps({"text": text}, ensure_ascii=False)},  # 不转义中文——\uXXXX 会把体积撑大 3 倍多
        timeout=10)
    print("发送结果:", resp.status_code, resp.text)

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

def load_jobs():
    global jobs
    if os.path.exists(JOBS_FILE):
        with open(JOBS_FILE, "r", encoding="utf-8-sig") as f:
            jobs = list(csv.DictReader(f))
    else:
        jobs = []

jobs = []
load_jobs()   # 启动时加载一次

JOB_LIST_LIMIT = 20         # "岗位"命令最多列 20 条——防止超飞书消息长度 + 保证可读

def cmd_jobs(open_id, parts):
    if len(jobs) == 0:
        send_text(open_id, "没有岗位数据，请先准备 jobs.csv"); return
    city = parts[1] if len(parts) > 1 else ""
    keyword = parts[2] if len(parts) > 2 else ""
    result = [j for j in jobs
              if (not city or city in j["城市"])
              and (not keyword or keyword in j["岗位"])]
    if len(result) == 0:
        send_text(open_id, "没有符合条件的岗位"); return
    shown = result[:JOB_LIST_LIMIT]
    lines = [f"{i+1}. [{j['城市']}] {j['公司']} - {j['岗位']}" for i, j in enumerate(shown)]
    head = "匹配岗位：" if len(result) <= JOB_LIST_LIMIT else \
        f"匹配岗位 {len(result)} 个（显示前 {JOB_LIST_LIMIT}，发「岗位 {city} 更具体关键词」缩小范围）："
    send_text(open_id, head + "\n" + "\n".join(lines))

# ---- 简历优化确认状态（防"幽灵确认" + 超时清理）----
_pending_optimize = {}      # {open_id: 发起时间戳} —— 谁在等确认
_PENDING_TIMEOUT = 600      # 10 分钟未确认自动作废

def _is_pending(open_id):
    """检查某用户是否有待确认的优化；超时自动作废。"""
    if open_id in _pending_optimize and time.time() - _pending_optimize[open_id] > _PENDING_TIMEOUT:
        del _pending_optimize[open_id]     # 超时作废
    return open_id in _pending_optimize


def send_confirm_card(open_id, report):
    """发一张带「确认改写」「放弃」按钮的卡片。"""
    card = {
        "config": {"wide_screen_mode": True},
        "header": {"title": {"tag": "plain_text", "content": "📋 简历优化确认"}},
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": report}},
            {"tag": "action", "actions": [
                {"tag": "button", "text": {"tag": "plain_text", "content": "✅ 确认改写"},
                 "value": {"cmd": "optimize_confirm"}},
                {"tag": "button", "text": {"tag": "plain_text", "content": "❌ 放弃"},
                 "value": {"cmd": "optimize_cancel"}},
            ]},
        ],
    }
    token = get_tenant_access_token()
    resp = requests.post(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
        headers={"Authorization": f"Bearer {token}"},
        json={"receive_id": open_id, "msg_type": "interactive",
              "content": json.dumps(card, ensure_ascii=False)}, timeout=10)
    print("发送确认卡片结果:", resp.status_code)


def cmd_optimize(open_id, parts):
    """第 1 步：发起 → 图暂停在确认处 → 发报告卡片（带确认/放弃按钮）。"""
    if len(parts) != 2:
        send_text(open_id, "格式：优化简历 序号（序号看「岗位」的列表）")
        return
    try:
        n = int(parts[1]) - 1
    except ValueError:
        send_text(open_id, "序号要是数字")
        return
    if n < 0 or n >= len(jobs):
        send_text(open_id, "序号超出范围")
        return
    job = jobs[n]                       # server 解析岗位
    out = start_optimize(job, open_id)  # 把岗位字典传入图（不再依赖 jobs，避免循环 import）
    _pending_optimize[open_id] = time.time()   # 记录"在等确认"
    send_confirm_card(open_id, out["report"])  # 用卡片+按钮，不用纯文本


def cmd_confirm(open_id, confirmed):
    """第 2 步：确认/取消 → 恢复图（同 thread_id）→ 发结果。带状态守卫。"""
    if not _is_pending(open_id):
        send_text(open_id, "当前没有待确认的简历优化（先发「优化简历 序号」）")
        return
    del _pending_optimize[open_id]
    out2 = finish_optimize(confirmed, open_id)   # Command(resume=...), thread_id=open_id
    send_text(open_id, out2["result"])
    if confirmed:
        send_text(open_id, "优化完成！新简历已保存（原稿未动）。")


def handle_card_action(event):
    """FeishuChannel 长连接卡片回调入口（event: CardActionEvent）。

    新版 SDK 已把 action.value 解析成 dict（{"cmd": "optimize_confirm"} 等），
    这里防御性兼容字符串形式。替代旧的 /feishu/event HTTP 拦截。
    """
    value = event.action.value
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            pass
    cmd = value.get("cmd") if isinstance(value, dict) else None
    open_id = event.operator.open_id
    print(f">>> 卡片回调 from {open_id}: {value}")
    if cmd == "optimize_confirm":
        cmd_confirm(open_id, True)
    elif cmd == "optimize_cancel":
        cmd_confirm(open_id, False)
    else:
        print(">>> 未知卡片指令:", cmd)

def cmd_help(open_id):
    send_text(open_id,
        "我是校招虾 🦐，支持：\n"
        "· 投递 公司 岗位 —— 记录投递\n"
        "· 我的进度 —— 查看投递列表\n"
        "· 更新 序号 状态 —— 更新状态（更新 序号 看可选）\n"
        "· 删除 序号 —— 删除投递\n"
        "· 岗位 城市 关键词 —— 筛选岗位（都可省略）\n"
        "· 优化简历 序号 —— AI 优化简历（同岗位）\n"
        "· 简历意见 序号 —— AI 按岗位给简历意见\n"
        "· 帮助 —— 本菜单")

def send_card(open_id,title,lines):
    token = get_tenant_access_token()
    card = {
        "config": {"wide_screen_mode":True},
        "header": {"title": {"tag": "plain_text", "content": title}},
        "elements": [{"tag": "div", "text":{"tag": "lark_md", "content": line}} for line in lines],
    }
    resp = requests.post(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
        headers={"Authorization": f"Bearer {token}"},
        json={"receive_id": open_id, "msg_type": "interactive",
              "content": json.dumps(card, ensure_ascii=False)}, timeout=10)
    print("发送卡片结果:", resp.status_code)

@app.post("/feishu/event")
async def feishu_event(request: Request):
    """HTTP webhook 入口（保留备用：后台若切成 URL 模式仍可用）。

    注意：当前后台事件订阅是「长连接」模式，消息和卡片回调都走
    FeishuChannel（见 bot.py），此端点平时不会被调用。
    """
    req = RawRequest()
    req.uri = str(request.url.path)
    req.headers = dict(request.headers)
    req.body = await request.body()  # SDK 要原始字节

    resp = event_handler.do(req)     # SDK：token 校验 + 挑战处理 + 分发到 do_message
    return Response(content=resp.content, status_code=resp.status_code, headers=resp.headers)



# ---- 原有 HTTP API（L6，保留不动）----
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
