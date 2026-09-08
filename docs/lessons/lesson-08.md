# Lesson 8 · 飞书消息 + 交互卡片

> 目标：用户给机器人发消息 → 事件到达你的服务器 → 你**记录投递并回复**——校招虾在飞书里"活"起来。
> 前置：L7 完成（webhook 验证通过）。
> 模式：**webhook（回调）**，沿用已跑通的 `/feishu/event` 端点。
> 本课含 **Part D 实战避坑手册**——L7→L8 反复踩坑的完整总结，照着能少走 3 天弯路。

---

## 0. 本课闭环（先看全景）

```
你在飞书里给机器人发：「投递 字节 后端」
        ↓ 飞书 POST 到你的回调地址（事件 im.message.receive_v1）
你的 /feishu/event 收到事件 → SDK 令牌校验 → 解析出 open_id + 消息文本
        ↓ 调 L5 的 ApplicationBook 记录一条投递（复用！）
你的服务器调用飞书 API 回复：「✅ 已记录 字节 - 后端」+ 卡片
        ↓
你在飞书里看到机器人的回复
```

**这堂课你会理解**：飞书事件 → 解析 → 业务逻辑（L5 的类）→ 调用飞书 API 回复。**前后端 + 数据 + 第三方平台全打通了。**

---

## Part A · 让消息事件真正到达

### A1. 飞书后台三步

1. 「应用能力」→ 确认**机器人**能力已开启。
2. 「事件与回调」→ 事件订阅 → **添加事件**：`im.message.receive_v1`。
   > ⚠️ 注意：这是**事件**，不是权限！权限在「权限管理」（`im:message`），事件在「事件与回调」——两个页面，别搜错地方。
3. 「版本管理与发布」→ **创建版本并发布**（改事件/权限后都要重新发布才生效）。

### A2. 装官方 SDK（事件接收的标准姿势）

```cmd
cd /d D:\job_hunter\cli
..\.venv\Scripts\python.exe -m pip install lark-oapi
```

> 为什么用 SDK 而不是手搓验签？见 Part D2——手搓的算法和飞书实际机制对不上，是 L7 血泪的核心。

---

## Part B · 用 SDK 接收事件 + 回复文本（核心闭环）

### B1. 两个概念

| 概念 | 说明 |
|---|---|
| **tenant_access_token** | 调用飞书 API 的"门票"。用 App ID + App Secret 换，有效期 2 小时，应缓存复用 |
| **open_id** | 用户在某个应用下的唯一 ID，用它给这个人发消息 |

### B2. 完整代码（替换 server.py 的事件部分）

```python
import json
import os
import time
import requests
import lark_oapi as lark
from lark_oapi.core.model.raw_request import RawRequest
from fastapi import FastAPI, Request, Response

# ---- 飞书凭证（环境变量，不写死在代码里）----
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
FEISHU_VERIFICATION_TOKEN = os.environ.get("FEISHU_VERIFICATION_TOKEN", "")  # 见 Part D1

# ---- 事件处理：SDK 自动完成 令牌校验 + 挑战处理 + 分发 ----
def do_message(data: lark.im.v1.P2ImMessageReceiveV1) -> None:
    """收到 im.message.receive_v1 事件时，SDK 调用这个函数。"""
    event = data.event
    open_id = event.sender.sender_id.open_id
    content = json.loads(event.message.content)   # content 是"字符串里的 JSON"
    text = content.get("text", "").strip()
    print(f">>> 收到消息 from {open_id}: {text}")

    if text.startswith("投递") and len(text.split()) == 3:
        _, company, position = text.split()
        book.add(company, position)               # 复用 L5 的类！
        send_text(open_id, f"✅ 已记录 {company} - {position}")
    elif text == "我的进度":
        lines = [f"{i+1}. {a['company']} - {a['position']} [{a['status']}]"
                 for i, a in enumerate(book.applications)]
        send_text(open_id, "你的投递进度：\n" + "\n".join(lines) if lines else "还没有投递记录")
    else:
        send_text(open_id, "支持：\n· 投递 公司 岗位\n· 我的进度")

event_handler = (
    lark.EventDispatcherHandler.builder("", FEISHU_VERIFICATION_TOKEN)  # (加密密钥, 验证令牌)
    .register_p2_im_message_receive_v1(do_message)
    .build()
)


@app.post("/feishu/event")
async def feishu_event(request: Request):
    req = RawRequest()                          # SDK 要"原始请求"对象
    req.uri = str(request.url.path)
    req.headers = dict(request.headers)
    req.body = await request.body()             # 必须是原始字节！

    resp = event_handler.do(req)                # SDK：令牌校验 + 挑战 + 分发
    return Response(content=resp.content, status_code=resp.status_code,
                    headers=resp.headers)       # 把 SDK 生成的响应原样回给飞书
```

**三个必须注意的坑**：
1. `event_handler.do(req)` 接收的是 **RawRequest 对象**（`uri`/`headers`/`body` 字节），不是字符串——这是你实测踩过的 API 差异（有的教程写 `.handle()`，你装的版本只有 `.do()`）。
2. **验证令牌必须设对**：SDK 源码逻辑是"body 里的 `header.token` ≠ 你配置的令牌 → 拒绝"。设错/不设 = 所有事件被 500 拒掉。
3. 业务逻辑在 `do_message` 里，SDK 按事件类型自动分发——你**不用**自己解析 `event_type`。

### B3. 发消息工具（仍用 requests，练 HTTP）

```python
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
              "content": json.dumps({"text": text})},   # content 是"字符串里的 JSON"！
        timeout=10)
    print("发送结果:", resp.status_code, resp.text)
```

### B4. 测试

1. 给机器人发「投递 字节 后端」→ 收到「✅ 已记录 字节 - 后端」。
2. 发「我的进度」→ 收到进度列表。
3. 打开 `applications.json` → 数据真的写进去了（CLI / HTTP / 飞书三个前台共享同一份数据）。

---

## Part C · 交互卡片（进阶）

### C1. 发卡片（msg_type = interactive）

```python
def send_card(open_id, title, lines):
    token = get_tenant_access_token()
    card = {
        "config": {"wide_screen_mode": True},
        "header": {"title": {"tag": "plain_text", "content": title}},
        "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": line}} for line in lines],
    }
    resp = requests.post(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
        headers={"Authorization": f"Bearer {token}"},
        json={"receive_id": open_id, "msg_type": "interactive",
              "content": json.dumps(card, ensure_ascii=False)}, timeout=10)
    print("发送卡片结果:", resp.status_code)
```

**卡片结构速记**：`header`（标题）+ `elements`（内容块列表）。`tag: "div"` 文字块、`tag: "action"` 按钮区。字段非常多，**先抄最小可用，需要再查官方文档**——学第三方 API 的正确姿势。

### C2. 处理按钮回调（card.action.trigger）

按钮回调也 POST 到同一个 `/feishu/event`（`type == "card.action.trigger"`），但 **SDK 的 event_handler 不管这种**，要在进 SDK 之前拦截：

```python
@app.post("/feishu/event")
async def feishu_event(request: Request):
    raw = await request.body()
    # ① 卡片按钮回调：SDK 不处理，先拦截
    try:
        d = json.loads(raw)
        if d.get("type") == "card.action.trigger":
            action = d["action"]["value"]          # 按钮上带的 value
            open_id = d["operator"]["open_id"]
            print(">>> 卡片按钮点击:", action)
            if action.get("cmd") == "show_progress":
                lines = [f"{i+1}. {a['company']} - {a['position']} [{a['status']}]"
                         for i, a in enumerate(book.applications)]
                send_card(open_id, "📋 我的投递进度", lines or ["还没有投递记录"])
            return {"code": 0}
    except Exception:
        pass
    # ② 其余事件交给 SDK
    req = RawRequest()
    req.uri = str(request.url.path)
    req.headers = dict(request.headers)
    req.body = raw
    resp = event_handler.do(req)
    return Response(content=resp.content, status_code=resp.status_code, headers=resp.headers)
```

发送带按钮的卡片（`value` 会原样出现在回调里——这是"按钮 → 你的代码"的传参通道）：

```python
card_with_button = {
    "config": {"wide_screen_mode": True},
    "elements": [
        {"tag": "div", "text": {"tag": "lark_md", "content": "点击查看你的投递进度"}},
        {"tag": "action", "actions": [
            {"tag": "button", "text": {"tag": "plain_text", "content": "查看进度"},
             "value": {"cmd": "show_progress"}},
        ]},
    ],
}
```

---

## Part D · 实战避坑手册（L7→L8 血泪总结）★

> 这一节是你前面几天踩坑的**结晶**。每条都是实测验证过的，照做能少走 3 天弯路。

### D1. 后台操作四坑

1. **权限 ≠ 事件**：`im.message.receive_v1` 是**事件**（「事件与回调 → 事件订阅」），不是权限（「权限管理」）。`im:message` 才是权限。搜错页面 = 白找半小时。
2. **⚠️ 事件有"前置权限"（本课程最大的坑）**：不是"订阅了事件就能收到"！每个事件还要求对应的**读权限**，没开 = 事件永远不会推送：
   | 事件 | 前置权限 |
   |---|---|
   | `im.message.receive_v1`（**单聊**） | `im:message.p2p_msg:readonly` |
   | `im.message.receive_v1`（**群聊@**） | `im:message.group_at_msg.include_bot:readonly` |
   | 撤回/已读 | `im:message` |
   
   **血的教训**：只开了 `im:message` → 私聊、群 @ 都收不到"接收消息"事件，我们查了三天 URL/隧道/验签/可用范围，最后发现是**事件前置权限没开**。判断方法：群聊 @ 通、私聊不通，或反之——**先查这张表**，再查别的。
3. **验证令牌不用在后台找**：它藏在**每个事件的 `body.header.token`** 里（同一应用值固定）。抓一次包就有了——比在后台翻设置快得多。
4. **回调地址 = 隧道 URL + `/feishu/event`**：验证通过后别乱改；改了事件/权限要**重新发布版本**才生效。

### D2. 验签的真相（全网最坑，务必记住）

- **民间流传的算法（HMAC-SHA256 + App Secret + base64/hex）是错的**，我们实测怎么算都对不上。
- 官方 SDK 源码（用 `inspect.getsource` 直接读）显示真实算法：
  ```python
  bs = (timestamp + nonce + encrypt_key).encode() + body
  signature = hashlib.sha256(bs).hexdigest()   # 普通 SHA-256！不是 HMAC！参与的是加密密钥！
  ```
- **没配置加密密钥时，签名校验直接跳过**——官方校验方式是**验证令牌**（body 里 `header.token` == 你配置的令牌）。
- **结论：别手搓验签**。遇到第三方平台鉴权，第一反应是"**用官方 SDK 或读官方源码**"，不是自己猜算法——这是比验签本身更值钱的认知。

### D3. SDK 用法三坑

1. 版本不同 API 不同：`EventDispatcherHandler` 没有 `.handle()`（你装的版本是 `.do(RawRequest)`）。**别猜，用 `dir(对象)` 和 `inspect.getsource(方法)` 解剖 SDK**——一条命令看到所有方法和源码。
2. 正确姿势：`builder("", 验证令牌).register_p2_im_message_receive_v1(函数).build()`；端点构造 `RawRequest(uri, headers, body字节)` → `do(req)` → 把 `RawResponse(content/status_code/headers)` 回给飞书。
3. **长连接模式和回调模式共用同一个 `event_handler`**——切换只是换"运输工具"（`ws.Client.start()` vs `do(req)`），`do_message` 一行不用改。

### D4. 环境变量三坑（cmd）

1. `set NAME=值` **不加引号**——加引号会把引号也存进变量，值就错了。
2. 必须**先 set、同一个窗口再启动**——环境变量只在当前窗口有效。
3. 改 env 要**完整重启**（Ctrl+C → set → 启动）；`--reload` 只重载代码、**不重读环境变量**。

### D5. 免费隧道三坑

1. 免费 cloudflared 走**洛杉矶节点**（日志 `location=lax01`），国内往返延迟可能超飞书 3 秒验证超时 → **多试几次**，或切长连接模式根治。
2. **重启隧道 URL 就变** → 回调地址要同步更新 + 重新验证。
3. 日志里 `UDP/QUIC FAIL` + "degraded transport" **无害**——自动降级 HTTP/2 正常工作，别管它。

### D6. 调试方法论（比任何代码都值钱）

1. **法医报告**：验签失败时打印「密钥长度 / 收到的签名 / 我方算的签名 / 是否一致 / 原始 body 前 120 字符」——一眼锁定病因，不用瞎猜。
2. **一次只动一个变量**，改完完整重启再测。这是排查问题的黄金法则。
3. **curl 自测隧道链路**：`curl -X POST 隧道URL/feishu/event -d '{"challenge":"test"}'` → 能回 `{"challenge":"test"}` 就证明"自己侧"全通，问题在飞书侧——**一刀切开两边**。
4. **群 @ 机器人**比单聊更容易触发事件，是标准测试姿势。
5. **看 body 用 `print` 解剖**：拿到新东西先打印出来看结构，再写解析代码。

### D7. 回调模式 vs 长连接：怎么选

| 情况 | 选择 |
|---|---|
| 隧道稳定、webhook 已通 | 回调模式继续（你现在就是） |
| 隧道频繁掉线 / URL 总变 / 事件老丢 | 切**长连接**（不用隧道、无 3 秒超时；同一套 `event_handler`，切换约 10 分钟） |

---

## 验证清单（做完逐条打勾）

- [ ] 给机器人发消息，终端打印 `>>> 收到消息事件`
- [ ] 发「投递 字节 后端」→ 收到「✅ 已记录」；`applications.json` 里真的有
- [ ] 发「我的进度」→ 收到进度列表
- [ ] （进阶）「我的进度」改成卡片 + 「查看进度」按钮，点按钮回调生效

## 弄坏再修（必做）

1. 故意不发 `content`（或 content 不是 JSON 字符串）→ 看发送报错，理解"字符串里的 JSON"。
2. 把 `receive_id_type=open_id` 换成 `chat_id` 还传 open_id → 报错，理解"ID 类型要对上"。
3. 把 `FEISHU_VERIFICATION_TOKEN` 设错 → 事件全被 500 拒掉 → 体会"令牌校验"的存在感。
4. 用 `dir()` 和 `inspect.getsource` 解剖一次 `EventDispatcherHandler`，自己找到 `do` 的源码。

## 自测题（能口头回答才算过关）

- `im.message.receive_v1` 是权限还是事件？在哪配置？
- 为什么我们手搓的验签（HMAC + App Secret）永远对不上？官方真实算法是什么？
- 没配加密密钥时，官方靠什么校验请求？
- 验证令牌怎么拿？它在事件的哪个字段里？
- `event_handler.do()` 接收什么类型的参数？为什么是字节不是字符串？
- 回调模式和长连接模式的区别？它们共用什么？
- 为什么说"飞书、HTTP、CLI 是同一个 ApplicationBook 的三个前台"？

---

*做完把更新后的 `server.py` 贴回来，我 review。下一课 L9：CLI → 飞书机器人端到端整合（★里程碑：可用的飞书版）——把"投递/更新/删除/筛选/AI意见"全部搬进飞书，并处理边界情况。*
