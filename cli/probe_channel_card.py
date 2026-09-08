"""
诊断探针 v2：FeishuChannel 长连接 + 卡片发送 + 卡片回调
========================================================
v1 只打印不回复，导致测不了卡片按钮。v2 收到"优化简历"就
自动回发一张确认卡片（结构和 server.py 的 send_confirm_card 一致），
点按钮后打印 cardAction 事件 —— 一次测通「发卡片 + 卡片回调」两条链路。

跑法（和 run_bot.cmd 同一个 cmd 窗口，先停掉正在跑的 bot）：
    set FEISHU_APP_ID=你的AppID
    set FEISHU_APP_SECRET=你的AppSecret
    .venv\Scripts\python.exe cli\probe_channel_card.py

然后：
1. 发 "优化简历"        -> 应收到一张带按钮的确认卡片
2. 点「确认改写」按钮     -> 控制台出现 ">>> 收到卡片回调"
把控制台输出整段贴回来。
"""
import json
import os

from lark_oapi.channel import Events, FeishuChannel

APP_ID = os.environ["FEISHU_APP_ID"]
APP_SECRET = os.environ["FEISHU_APP_SECRET"]

channel = FeishuChannel(app_id=APP_ID, app_secret=APP_SECRET)


def build_confirm_card(report):
    """与 server.py send_confirm_card 相同的卡片结构（value 只带 cmd）。"""
    return {
        "config": {"wide_screen_mode": True},
        "header": {"title": {"tag": "plain_text", "content": "📋 简历优化确认（探针）"}},
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


async def on_message(msg):
    print("\n>>> 收到消息", flush=True)
    print("  message_id :", msg.message_id)
    print("  chat_id    :", msg.chat_id, "| chat_type:", msg.chat_type)
    print("  sender     :", msg.sender_id)
    print("  content    :", repr(msg.content_text))
    if "优化简历" in msg.content_text:
        card = build_confirm_card("**探针测试报告**\n确认后模拟恢复图（resume=confirm）。")
        result = await channel.send(msg.chat_id, {"card": card})
        ok = "成功" if getattr(result, "success", False) else repr(result)
        print("  已回发确认卡片 ->", ok, flush=True)


async def on_card(event):
    print("\n>>> 收到卡片回调", flush=True)
    print("  message_id :", event.message_id)
    print("  chat_id    :", event.chat_id)
    print("  operator   :", event.operator.open_id)
    print("  action.tag :", event.action.tag)
    print("  action.val :", json.dumps(event.action.value, ensure_ascii=False))
    print("  raw(截断)  :", json.dumps(event.raw, ensure_ascii=False)[:800])


async def on_error(err):
    print("\n!!! 错误:", repr(err), flush=True)


channel.on(Events.MESSAGE, on_message)
channel.on(Events.CARD_ACTION, on_card)
channel.on(Events.ERROR, on_error)

print("长连接已启动（探针 v2）。", flush=True)
print("请测试：发「优化简历」→ 点「确认改写」按钮。", flush=True)
channel.start()
