# cli/bot.py —— 飞书长连接入口（新版 lark_oapi.channel）
#
# 旧版 lark.ws.Client 会把长连接上的「卡片消息帧」直接丢弃（CARD 分支是空实现），
# 导致卡片按钮点击永远没反应。新版 lark_oapi.channel.FeishuChannel 原生支持：
#   · channel.on("message",    fn)   -> 消息事件（InboundMessage，已解析好字段）
#   · channel.on("cardAction", fn)   -> 卡片按钮回调（CardActionEvent，value 已解析成 dict）
#   · channel.send(chat_id, {"card": ...}) 发卡片（本 bot 发送仍走 server 的 requests，见下）
#   · 内置回调去重 + 按 chat 串行化（飞书 at-least-once 重投不会重复触发确认）
#
# 复用 server.py 的业务逻辑：
#   · 消息   -> server.handle_message_from_channel(msg)
#   · 卡片   -> server.handle_card_action(event)
#   · 发送   -> server 内部仍用 requests 走 im/v1/messages HTTP API（已验证稳定，不动）

import os
from dotenv import load_dotenv
load_dotenv() #必须先执行，把.env的内容装进环境变量
import server
from lark_oapi.channel import Events, FeishuChannel

FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")

channel = FeishuChannel(app_id=FEISHU_APP_ID, app_secret=FEISHU_APP_SECRET)


async def on_message(msg):
    server.handle_message_from_channel(msg)


async def on_card(event):
    server.handle_card_action(event)


async def on_error(err):
    print("!!! channel error:", repr(err))


channel.on(Events.MESSAGE, on_message)
channel.on(Events.CARD_ACTION, on_card)
channel.on(Events.ERROR, on_error)

if __name__ == "__main__":
    print(">>> 校招虾长连接启动（FeishuChannel）...（Ctrl+C 退出）")
    channel.start()   # 阻塞运行，保持连接（默认 transport=ws，断线自动重连）
