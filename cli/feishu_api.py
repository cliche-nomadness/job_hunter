# cli/feishu_api.py —— 飞书消息发送公共模块（供 sync_jobs 等非 bot 进程复用）
#
# 来源：server.py 的发送逻辑原样提取（token 缓存 + im/v1/messages）。
# 已知取舍：server.py 内部仍保留自己的一份（核心文件不动，下次重构时切换引用）——
# 短期内发送逻辑存在两份，属于风险控制下的技术债，不是设计。
#
# 推送目标自动发现：
#   .env 配了 FEISHU_CHAT_ID 或 FEISHU_OPEN_ID → 直接用；
#   没配 → 调 im/v1/chats 列出机器人所在的会话，取第一个（单用户场景=你和它的单聊），
#   并把选择打印在日志里，不对就手动把 chat_id 写进 .env。

import os
import json
import time

import requests
from dotenv import load_dotenv

load_dotenv()

FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")

_token_cache = {"token": "", "expire_at": 0}


def get_tenant_access_token():
    """获取（带缓存的）tenant_access_token，逻辑同 server.py。"""
    if _token_cache["token"] and _token_cache["expire_at"] > time.time():
        return _token_cache["token"]
    resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}, timeout=10)
    data = resp.json()
    if "tenant_access_token" not in data:
        raise RuntimeError(f"获取 token 失败: {data}")
    _token_cache["token"] = data["tenant_access_token"]
    _token_cache["expire_at"] = time.time() + data.get("expire", 3600) - 60
    return _token_cache["token"]


def send_text(receive_id, text, receive_id_type="open_id"):
    """发文本消息。receive_id_type: open_id | chat_id。"""
    token = get_tenant_access_token()
    resp = requests.post(
        f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={receive_id_type}",
        headers={"Authorization": f"Bearer {token}"},
        json={"receive_id": receive_id, "msg_type": "text",
              "content": json.dumps({"text": text}, ensure_ascii=False)},
        timeout=10)
    ok = resp.status_code == 200
    print(("✅" if ok else "❌") + f" 发送文本: HTTP {resp.status_code} {resp.text[:200]}", flush=True)
    return ok


def send_card(receive_id, title, lines, receive_id_type="open_id"):
    """发交互卡片（elements 为 lark_md 行）。"""
    token = get_tenant_access_token()
    card = {
        "config": {"wide_screen_mode": True},
        "header": {"title": {"tag": "plain_text", "content": title}},
        "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": ln}} for ln in lines],
    }
    resp = requests.post(
        f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={receive_id_type}",
        headers={"Authorization": f"Bearer {token}"},
        json={"receive_id": receive_id, "msg_type": "interactive",
              "content": json.dumps(card, ensure_ascii=False)}, timeout=10)
    ok = resp.status_code == 200
    print(("✅" if ok else "❌") + f" 发送卡片: HTTP {resp.status_code}", flush=True)
    return ok


def list_chats():
    """列出机器人所在的会话（im/v1/chats）。"""
    token = get_tenant_access_token()
    resp = requests.get(
        "https://open.feishu.cn/open-apis/im/v1/chats?page_size=20",
        headers={"Authorization": f"Bearer {token}"}, timeout=10)
    data = resp.json()
    return (data.get("data") or {}).get("items") or []


def resolve_push_target():
    """返回 (receive_id, receive_id_type)。.env 优先，否则自动发现第一个会话。"""
    chat_id = os.environ.get("FEISHU_CHAT_ID", "")
    open_id = os.environ.get("FEISHU_OPEN_ID", "")
    if chat_id:
        return chat_id, "chat_id"
    if open_id:
        return open_id, "open_id"
    chats = list_chats()
    if not chats:
        raise RuntimeError("机器人不在任何会话里——先在飞书里给它发条消息，再把 chat_id 写入 .env")
    first = chats[0]
    print(f"ℹ️ 自动选择推送会话: {first.get('name') or '(单聊)'} "
          f"chat_id={first.get('chat_id')}（如不对，请把它写入 .env 的 FEISHU_CHAT_ID）", flush=True)
    return first["chat_id"], "chat_id"
