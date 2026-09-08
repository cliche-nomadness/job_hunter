# Lesson 6 · FastAPI 入门（HTTP 服务）

> 目标：让校招虾第一次以"**服务**"形态运行——通过 HTTP 就能访问它。
> 前置：L1–L5 全部过关（尤其 L5 的 `ApplicationBook` 类）。
> 阶段 2 开始：从命令行世界，进入"后端服务"世界。

---

## 0. 思维转变：从"命令行"到"服务"

| | 之前（L1–L5） | 现在（L6 起） |
|---|---|---|
| 形态 | 程序跑完就退出 | **服务器永远在跑**，等别人来"请求" |
| 交互 | 你输入 → 程序打印 | 别的程序/浏览器发 HTTP 请求 → 服务器回 JSON |
| 类比 | 你问柜台职员 | **你开了一家餐厅**，客人随时来点菜 |

回忆 L3 的"点外卖"：那时你的程序是**客人**，DeepSeek 是**餐厅**（你发 `requests.post` 点菜）。现在**轮到你开餐厅了**——FastAPI 就是你的餐厅执照 + 厨房，`uvicorn` 是帮你把餐厅开起来的伙计。

---

## 1. HTTP 四板斧（记死这 4 个动词）

| 方法 | 含义 | 校招虾对应 |
|---|---|---|
| **GET** | 取数据 | 查看投递列表 |
| **POST** | 创建数据 | 添加一条投递 |
| **PUT / PATCH** | 更新数据 | 更新状态 |
| **DELETE** | 删除数据 | 删除投递 |

URL（路由）是"菜名"，方法（动词）是"做法"。同一个 URL 用不同动词 = 不同的菜。

---

## 2. 装 FastAPI + uvicorn（你终端，一次性）

```powershell
.venv\Scripts\python.exe -m pip install fastapi "uvicorn[standard]"
```

> 我的沙箱没外网，这步必须你自己来（和装 requests 一样）。装完验证：
> `.venv\Scripts\python.exe -c "import fastapi, uvicorn; print('OK', fastapi.__version__)"`

---

## 3. 任务 A：第一个 FastAPI 应用（最小版）

新建 `cli/server.py`：

```python
# cli/server.py
from fastapi import FastAPI

app = FastAPI(title="校招虾 API")   # 创建应用对象

@app.get("/")                        # 装饰器：把下面这个函数注册成 GET 路由
def root():
    return {"message": "校招虾服务已启动"}
```

**运行**（先 `cd cli`，再启动）：

```powershell
cd D:\job_hunter\cli
..\.venv\Scripts\python.exe -m uvicorn server:app --reload
```

浏览器打开两个地址（终端会显示它监听在 8000 端口）：

- `http://127.0.0.1:8000/` → 看到 `{"message": "校招虾服务已启动"}`
- `http://127.0.0.1:8000/docs` → **FastAPI 白送的自动接口文档**（这是它最爽的功能，后面全靠它调试）

**三个新概念**：

| 概念 | 说明 |
|---|---|
| `app = FastAPI(...)` | 创建应用对象，整个服务的"本体" |
| `@app.get("/")` | **装饰器**：把函数"注册"成 URL 路由。`/` 是路径 |
| 函数返回值 | 返回 dict → FastAPI 自动转成 JSON 响应 |

---

## 4. 任务 B：用 ApplicationBook 做真实接口（核心）

**关键洞察**：`server.py` 和 `main.py` 是**同一个 ApplicationBook 的两个前台**——CLI 是命令行前台，HTTP 是网络前台，数据都落在 `applications.json`。

改 `cli/server.py`：

```python
# cli/server.py
from fastapi import FastAPI
from pydantic import BaseModel
from application_book import ApplicationBook

app = FastAPI(title="校招虾 API")
book = ApplicationBook("applications.json")   # 复用 L5 的类！

@app.get("/applications")
def get_all():
    return book.applications          # 返回整个列表

class NewApplication(BaseModel):      # Pydantic：声明"请求体长什么样"
    company: str
    position: str

@app.post("/applications")
def add_one(item: NewApplication):
    book.add(item.company, item.position)   # 调类的方法，自动存盘
    return {"ok": True, "data": item.model_dump()}
```

**新概念**：

| 概念 | 说明 |
|---|---|
| `class NewApplication(BaseModel)` | **Pydantic 模型**：声明 POST 请求的 JSON 必须有哪些字段、什么类型 |
| `item: NewApplication` | **类型注解**：FastAPI 自动把请求 JSON 解析成这个对象 |
| 校验失败 | 少传字段/类型错 → 自动返回 **422**，而不是程序崩溃 |

**测试**（浏览器打开 `http://127.0.0.1:8000/docs`，点开接口 → **Try it out** → 直接发请求）：

```powershell
# 或者命令行（另开一个终端）：
curl http://127.0.0.1:8000/applications
curl -X POST http://127.0.0.1:8000/applications -H "Content-Type: application/json" -d "{\"company\":\"字节\",\"position\":\"后端\"}"
```

---

## 5. 任务清单

- [ ] **A1**：装 fastapi + uvicorn，写最小 `server.py`，跑起来，浏览器打开 `/` 和 `/docs`
- [ ] **A2**：理解 `--reload` 的作用（改代码自动重启，不用手动重启）
- [ ] **B1**：加 GET + POST `/applications`，用 docs 页面发请求
- [ ] **B2**：POST 一条 → GET 看到它 → 检查 `applications.json` 确实持久化了
- [ ] **C（选做）**：加 `PUT /applications/{index}`（更新状态）和 `DELETE /applications/{index}`（删除）。提示：`@app.put("/applications/{index}")`，`index` 是**路径参数**，函数签名写 `def update(index: int, ...)`；更新状态要接 JSON（Pydantic 模型：`new_status: str`），然后调 `book.update_status(index, new_status)`

---

## 验证清单（做完逐条打勾）

- [ ] `http://127.0.0.1:8000/docs` 能打开，能看到自动生成的接口文档
- [ ] GET `/applications` 返回列表（JSON）
- [ ] POST 一条投递后，GET 能看到它，且 `applications.json` 里多了这条
- [ ] POST 时故意少传 `position` 字段 → 返回 422 而不是崩溃（Pydantic 的功劳）
- [ ] （选做）PUT 更新状态：非法迁移被拒绝；DELETE 后 GET 里少一条

## 弄坏再修（必做）

1. POST 时少传一个字段 → 亲眼看看 422 错误长什么样（这是"服务器不背锅"的体现）。
2. 把 `/applications` 错写成 `/applicationss` → 404（路径不对服务器直接拒绝）。
3. **关掉 `--reload`** 再改代码 → 发现改动不生效 → 重启生效。理解 reload 存在的意义。
4. 停掉服务器（Ctrl+C）后再访问 `http://127.0.0.1:8000` → 打不开。理解"服务是常驻进程"。

## 自测题（能口头回答才算过关）

- GET / POST / PUT / DELETE 分别是什么语义？
- `@app.get("/applications")` 里的 `"/applications"` 是什么？函数名和它有关系吗？
- `item: NewApplication` 这一行在做什么？FastAPI 怎么知道请求体长什么样？
- 422 和 404 分别代表什么？为什么会返回它们而不是崩溃？
- `--reload` 是干嘛的？为什么开发时开、部署时关？
- 为什么说 `server.py` 和 `main.py` 是"同一个 ApplicationBook 的两个前台"？

---

*做完把 `server.py` 贴回来，我 review。下一课 L7：飞书应用创建 + 事件订阅/验签——让校招虾真正"接入飞书"，从浏览器可见升级为飞书可聊。*
