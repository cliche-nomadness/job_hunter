# Lesson 7 · 飞书应用创建 + 事件订阅/验签

> 目标：让校招虾在飞书里"有了身份"，能收到飞书发来的事件。
> 前置：L6 完成（FastAPI 服务跑通）。
> 核心洞察：**L6 的模型原封不动复用——飞书当"客人"，你的服务器当"餐厅"。**

---

## 0. 大图：飞书事件 = 飞书来点菜

你在飞书开放平台创建一个"**应用**"（给校招虾在飞书里注册一个机器人身份），然后做一件事：

```
有人 @机器人 / 给机器人发消息
        ↓（飞书服务器自动发起）
飞书服务器 POST → 你在后台配置的回调 URL（https://你的穿透域名/feishu/event）
        ↓（你的 FastAPI 收到请求）
你的函数"醒"了，处理这件事
```

**和 L6 一模一样**：飞书是客户端（它发 POST），你的 server.py 是服务器（你写函数等它来）。区别只有一点——**飞书的请求不是你手动发的，是飞书服务器自动发的**。

---

## 1. 现实障碍预警（先看这个，别卡住）

| 障碍 | 怎么办 |
|---|---|
| **需要企业版飞书** | 飞书开放平台只对企业（租户）开放。没有企业账号？去飞书官网**免费创建一个"只有你自己"的企业**（个人也能创建企业版）。 |
| **需要公网地址** | 飞书服务器要能访问到你的本地服务。开发期用**内网穿透**（§7）。 |
| **我的沙箱没外网** | 所有"飞书后台操作 + 内网穿透"必须由你在自己电脑上完成，我只能帮你写代码、解释。 |

---

## 2. 创建应用 + 拿凭证

1. 打开 <https://open.feishu.cn>，用你的**企业飞书**登录。
2. 开发者后台 → **创建企业自建应用** → 起个名字（"校招虾"），上传个图标。
3. 进入应用 → 左侧「凭证与基础信息」，拿到两个关键值：

| 凭证 | 是什么 | 类比 |
|---|---|---|
| **App ID** | 应用公开身份标识 | 用户名 |
| **App Secret** | 机密密钥（只能看一次，妥善保存） | 密码（绝不能进 git/代码） |

**App Secret 的地位 = L3 的 DEEPSEEK_API_KEY**：放环境变量，不进代码。

---

## 3. 开通权限（⚠️ 这是 L7/L8 最大的坑，务必理解"权限 → 事件"的对应关系）

左侧「权限管理」→ 搜索并开通（开通后需**发布版本**才生效）。

**核心认知：不是"开了 im:message 就能收到消息"！** 飞书是"**事件 → 前置权限**"的对应关系——每个事件要能推送，必须同时满足"订阅了该事件" **且** "开通了该事件要求的前置权限"。

| 事件 | 要产生这个事件，需要开通 | 场景 |
|---|---|---|
| **接收消息** `im.message.receive_v1` | `im:message.p2p_msg:readonly` | 用户**单聊**机器人时 |
| **接收消息** `im.message.receive_v1` | `im:message.group_at_msg.include_bot:readonly` | 群聊里 **@ 机器人** 时 |
| 撤回消息 `im.message.recalled_v1` | `im:message` | 消息被撤回 |
| 消息已读 `im.message.message_read_v1` | `im:message` | 消息被已读 |

**注意**：`im:message` 本身只产生"撤回消息/消息已读"事件，**不产生"接收消息"**。所以校招虾要收到用户消息，必须开通：

- `im:message.p2p_msg:readonly`（单聊）
- `im:message.group_at_msg.include_bot:readonly`（群聊 @）
- `im:message`（后续"撤回/已读"可选）
- `im:resource`（后续发 PDF 用，可选）

> 规则：**用哪个事件开哪个权限**，别一次性开一大堆（最小权限原则）。开了之后记得**重新发布版本**。

> 血的教训（我们实测踩的）：只开了 `im:message` → 群聊 @ 没反应、私聊没反应，查了三天 URL/隧道/验签……最后发现是**事件的前置权限没开**。任何"订阅了事件但收不到"的问题，先查这张表。

---

## 4. 配置事件订阅 + URL 验证（challenge）

左侧「事件与回调」→ 事件订阅 → 添加**请求地址**（先随便填，比如 `https://你的穿透域名/feishu/event`）。

**关键：URL 验证机制（challenge）**

你提交回调地址的那一刻，飞书会立刻往这个地址发一个 POST，body 长这样：

```json
{
  "challenge": "ajls384kdjx98XX",
  "token": "xxxx",
  "type": "url_verification"
}
```

**你必须原样返回 `{"challenge": "ajls384kdjx98XX"}`**，飞书收到后才会认为"这地址是我的服务器"，配置才算通过。这就是飞书和你的第一次"握手"——它先试探你是不是活的、听不听话。

> 直觉理解：飞书像个谨慎的房东，租房前先敲敲门问暗号（challenge），你答对暗号它才把钥匙（事件）给你。

---

## 5. 写 FastAPI 接收回调（先跑通验证，再谈验签）

在 `server.py` 加一段（先不验签，让握手跑通）：

```python
import json
from fastapi import FastAPI, Request

@app.post("/feishu/event")
async def feishu_event(request: Request):
    raw = (await request.body()).decode("utf-8")   # 原始字符串（后面验签要用它）
    body = json.loads(raw)                          # 再解析成字典（取字段用）

    print(">>> 收到飞书请求，body =", body)          # 先"解剖"：看看飞书发来什么

    challenge = body.get("challenge")               # 握手验证
    if challenge:
        return {"challenge": challenge}             # 原样回显 → 验证通过

    # （L8 在这里处理真实事件）
    return {"code": 0}
```

两个新东西：

| 概念 | 说明 |
|---|---|
| `async def` | 异步函数（FastAPI 支持）。先按"模板记住"即可，L10 之后会真正理解 |
| `await request.body()` | 拿到请求的**原始字节**（字符串）。注意：验签必须用原始 body，不能用 `request.json()`——因为 JSON 再序列化可能和原文差一个空格，签名就对不上了 |

**跑通步骤**：起服务 → 穿透 → 在后台点「验证」→ 看你的终端打印出的 body 里有 `challenge` 字段 → 后台显示"验证通过"。

---

## 6. 验签（安全必学，防止伪造请求）

### 为什么需要

你的回调 URL 是**公网公开**的，任何人都能往它发 POST（伪造"我是飞书"）。验签 = 让服务器确认"这请求真是飞书发的，不是骗子"。

### 飞书每次回调都会带 3 个请求头

| 请求头 | 内容 |
|---|---|
| `X-Lark-Request-Timestamp` | 时间戳 |
| `X-Lark-Request-Nonce` | 随机串 |
| `X-Lark-Signature` | `base64( HMAC-SHA256( timestamp + nonce + body, app_secret ) )` |

### 验签四步（服务器要算一遍同样的签名再比对）

```python
import hashlib, hmac, base64, os

FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")

def verify_feishu_signature(timestamp, nonce, raw_body, signature):
    string_to_sign = f"{timestamp}{nonce}{raw_body}"     # 1. 拼字符串
    h = hmac.new(FEISHU_APP_SECRET.encode(), string_to_sign.encode(), hashlib.sha256)
    expected = base64.b64encode(h.digest()).decode()      # 2. HMAC + base64
    return hmac.compare_digest(expected, signature)       # 3. 比对（防时序攻击的写法）
```

然后在回调函数开头加一道"门卫"：

```python
@app.post("/feishu/event")
async def feishu_event(request: Request):
    timestamp = request.headers.get("X-Lark-Request-Timestamp", "")
    nonce = request.headers.get("X-Lark-Request-Nonce", "")
    signature = request.headers.get("X-Lark-Signature", "")
    raw = (await request.body()).decode("utf-8")

    if not verify_feishu_signature(timestamp, nonce, raw, signature):
        return {"code": 403, "msg": "验签失败"}           # 门卫拦下伪造请求

    body = json.loads(raw)
    # ... 后面的处理照旧
```

> 用 `hmac.compare_digest` 而不是 `==`：前者即使两串不同也耗时相同，防止黑客用"时间差"猜签名（防时序攻击）。先记住"用这个函数"即可。

### 运行方式补充

把 App Secret 放进环境变量再起服务：

```powershell
$env:FEISHU_APP_SECRET = "你的App Secret"
cd D:\job_hunter\cli
..\.venv\Scripts\python.exe -m uvicorn server:app --reload
```

---

## 7. 内网穿透（让飞书能访问你的本地服务）

飞书服务器在公网上，你的服务在本地 `127.0.0.1:8000`——中间需要一座桥。推荐顺序：

**方案一：cloudflared（推荐，无需注册账号）**
```powershell
winget install cloudflared        # 或去官网下载 exe
cloudflared tunnel --url http://localhost:8000
```
终端会显示一个 `https://xxx.trycloudflare.com` 地址，这就是你的临时公网地址。

**方案二：ngrok（需要免费注册）**
```powershell
# 注册 https://ngrok.com → 下载 → 配置 auth token
ngrok http 8000
```

⚠️ **免费版穿透地址会变**：每次重启穿透，URL 都不同，而回调地址每次改都要重新验证。所以习惯是：**先开穿透，把当前 URL 填进飞书后台，别中途重启穿透**。

---

## 8. 完整流程清单（照这个顺序走）

1. 创建企业飞书（如果没有）
2. 创建应用 → 拿 App ID / App Secret
3. 开通权限 `im:message` → 发布版本
4. 装 cloudflared → 起 server.py（先不加验签）→ 穿透跑通，拿到 https URL
5. 后台填回调地址 `https://xxx.trycloudflare.com/feishu/event` → 点验证
6. 看终端打印的 challenge body → 验证通过 ✅
7. 加验签代码 → 重启 → 再点一次验证（确认验签没把真请求拦掉）

## 验证清单（做完逐条打勾）

- [ ] 后台「事件订阅」显示回调地址验证成功，不再报错
- [ ] 你的终端打印出带 `challenge` 字段的 body
- [ ] 加验签后，点「验证」依然通过（说明验签放行了真飞书）
- [ ] （进阶）用 curl 伪造一个不带签名的 POST → 你的服务器返回 403

## 弄坏再修（必做）

1. 故意不返回 challenge（返回空 dict）→ 后台验证失败，看飞书报什么错。
2. 验签里故意把 `FEISHU_APP_SECRET` 写错 → 真请求也被拒。体会"密钥一致性"。
3. 关掉穿透 → 后台再点验证 → 失败。理解"公网可达"是硬前提。

## 自测题（能口头回答才算过关）

- 飞书事件订阅里，"谁"是客户端，"谁"是服务器？
- URL 验证（challenge）是干嘛的？为什么要"原样回显"？
- App ID 和 App Secret 分别像什么？
- 验签的 `string_to_sign` 是怎么拼的？为什么必须用**原始 body** 而不是 `request.json()`？
- `hmac.compare_digest` 比 `==` 好在哪？
- 为什么要内网穿透？免费版穿透 URL 为什么会变？
- 回调地址验证通过 = 什么成立？（"飞书确认这地址是我的服务器"）

---

*做完把 `server.py` 更新后的代码贴回来，我 review。下一课 L8：飞书消息 + 交互卡片——用户发「投了字节后端」→ 机器人自动记录并回复卡片，校招虾第一次"在飞书里活起来"。*
