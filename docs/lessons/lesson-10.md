# Lesson 10 · LangGraph 入门（State / Node / Edge）

> 目标：把 L9 的**手工 if/elif 路由**升级成"**图**"编排，理解 LangGraph 三大核心概念。
> 前置：L9 完成（可用的飞书版）。
> 阶段 3 开始：AI 编排（LangGraph 是后面所有复杂流程的地基）。

---

## 0. 为什么要学"图"（从 L9 的痛点出发）

L9 的 `handle_command` 是一串 if/elif。命令少还好，但流程一复杂就崩：

- 命令越来越多（7 个 → 20 个），if/elif 变成一堵墙；
- 流程出现**分支**（"投递"直接执行 vs "改简历"要**先分析 → 等用户确认 → 再改写**）；
- 流程出现**等待**（人工确认按钮点了才继续）。

**图（Graph）** 就是解决这个的：把流程"画"出来——**节点**（做一件事）+ **边**（下一步去哪）。

> 类比：地铁图。站点 = 节点，线路 = 边；你在哪站上车（入口）、坐几站、在哪换乘（条件边），都由图决定。
> LangGraph = 用代码描述这张图、并自动执行的框架。

---

## Part A · 三大核心概念（先记死这三个词）

| 概念 | 是什么 | 类比 |
|---|---|---|
| **State（状态）** | 节点之间传递的**数据包**（一个 dict），一路累积 | 乘客的行李 |
| **Node（节点）** | 一个**函数**：读 state → 干活 → 返回 state 的更新 | 一个站点 |
| **Edge（边）** | 连接节点，决定"做完这个下一步去哪" | 地铁线路 |
| 条件边 | 根据 state 内容**动态决定**去哪条边 | 换乘指示 |

---

## Part B · 装 LangGraph + 最小图

### B1. 安装（你终端，一次）

```cmd
cd /d D:\job_hunter\cli
..\.venv\Scripts\python.exe -m pip install langgraph
```

### B2. 最小图（新建 `cli/graph_demo.py`）

```python
# cli/graph_demo.py —— LangGraph 最小示例
from typing import TypedDict
from langgraph.graph import StateGraph, START, END

class State(TypedDict):                 # ① 定义 State：节点间传递的数据
    messages: list[str]

def node_a(state: State) -> State:      # ② 节点 = 普通函数
    return {"messages": state["messages"] + ["A 处理了"]}

def node_b(state: State) -> State:
    return {"messages": state["messages"] + ["B 处理了"]}

builder = StateGraph(State)             # ③ 建图
builder.add_node("a", node_a)           #    注册节点
builder.add_node("b", node_b)
builder.add_edge(START, "a")            # ④ 连线：入口 → a
builder.add_edge("a", "b")              #    a → b
builder.add_edge("b", END)              #    b → 出口
graph = builder.compile()               # ⑤ 编译成可执行图

result = graph.invoke({"messages": []}) # ⑥ 从入口跑，沿着边走
print(result)                           # {'messages': ['A 处理了', 'B 处理了']}
```

**运行**：`..\.venv\Scripts\python.exe cli\graph_demo.py`

**三个直觉**：
1. `START` 是入口、`END` 是出口（`from langgraph.graph` 导入）；
2. `invoke({"messages": []})` 从 START 出发，沿边依次执行节点，state 一路累积；
3. 每个节点**返回的是"对 state 的更新"**（只写自己改的字段），框架负责合并。

---

## Part C · 条件边（这才是路由！）

把 L9 的命令路由"画成图"——**路由逻辑从"代码里的 if/elif"变成"图里的条件边"**。

新建 `cli/graph_router.py`：

```python
# cli/graph_router.py —— 用 LangGraph 重写 L9 的命令路由（先跑通，不接飞书）
from typing import TypedDict
from langgraph.graph import StateGraph, START, END

class State(TypedDict):
    cmd: str        # 命令词
    text: str       # 原始文本
    reply: str      # 生成的回复（图只管生成，发送留给外面）

def router(state: State) -> str:
    """条件边的'指路函数'：看一眼 state，返回'下一个节点名'。"""
    if state["cmd"] == "投递":
        return "do_add"
    if state["cmd"] == "我的进度":
        return "do_progress"
    return "do_help"            # 其余都走帮助

def do_add(state: State) -> State:
    return {"reply": f"✅ 执行添加：{state['text']}"}

def do_progress(state: State) -> State:
    return {"reply": "📋 执行查看进度"}

def do_help(state: State) -> State:
    return {"reply": "🦐 帮助菜单"}

builder = StateGraph(State)
builder.add_node("router", lambda s: s)      # 入口中转节点
builder.add_node("do_add", do_add)
builder.add_node("do_progress", do_progress)
builder.add_node("do_help", do_help)

builder.add_edge(START, "router")
builder.add_conditional_edges(                # 关键：条件边
    "router",                                 # 从哪个节点出发
    router,                                   # 指路函数（返回 key）
    {"do_add": "do_add",                      # key → 去哪个节点
     "do_progress": "do_progress",
     "do_help": "do_help"},
)
for n in ("do_add", "do_progress", "do_help"):
    builder.add_edge(n, END)

graph = builder.compile()

print(graph.invoke({"cmd": "投递", "text": "投递 字节 后端", "reply": ""}))
print(graph.invoke({"cmd": "我的进度", "text": "我的进度", "reply": ""}))
print(graph.invoke({"cmd": "你好", "text": "你好", "reply": ""}))
```

**`add_conditional_edges(节点, 指路函数, 映射表)` 三件套**：

| 参数 | 作用 |
|---|---|
| 节点 | 从哪个节点开始判断（这里是 router）|
| 指路函数 | 读 state，返回一个 key（字符串）|
| 映射表 | `{key: 节点名}`——返回的 key 对应去哪个节点 |

**运行**：`..\.venv\Scripts\python.exe cli\graph_router.py`，看到三个不同 reply。

---

## Part D · 架构原则：图管决策，IO 留在外面 ★

**图里不要直接调 `send_text` / 读写文件**（IO 操作）。图只负责"决定做什么 + 生成结果"，真正发送由**外面**做：

```
do_message（飞书事件）→ 填 state → graph.invoke(state) → 拿 reply → send_text(reply)
                                     ↑ 图在这里只管逻辑，不管发消息
```

好处：
1. **图可以脱离飞书单独测试**（像 graph_router.py 一样直接 invoke，不碰网络/飞书）；
2. 同一个图将来可以接**不同的入口**（飞书、HTTP、CLI）——IO 换，图不换；
3. L11 的"简历优化图"（分析→确认→改写）依赖这个原则——它要暂停等用户确认，IO 更不能焊死在图里。

---

## 任务清单

1. 装 langgraph（B1）。
2. 跑通最小图 `graph_demo.py`，理解 invoke 输出。
3. 跑通条件路由图 `graph_router.py`，然后**把 L9 的全部 7 个命令加进去**：
   - do_add / do_progress / do_update / do_delete / do_jobs / do_advice / do_help
   - 每个节点先只生成 reply 字符串（不调真实业务也行，先看路由对不对）。
4. 思考题（口头回答）：为什么"图管决策、IO 留外面"？

## 验证清单（做完逐条打勾）

- [ ] `graph_demo.py` 输出 `{'messages': ['A 处理了', 'B 处理了']}`
- [ ] `graph_router.py` 三个 invoke 分别到 do_add / do_progress / do_help
- [ ] 7 个命令都能被路由到正确节点
- [ ] 未识别命令 → do_help

## 弄坏再修（必做）

1. 把 `add_conditional_edges` 的映射表**删掉一个 key**（比如 `do_progress`）→ 运行看报错，理解"映射表必须覆盖指路函数的所有返回值"。
2. 让指路函数返回一个**映射表里没有的值** → 看报错。
3. 忘加 `builder.add_edge("b", END)` → 看报错，理解"每条路径都要到 END"。

## 自测题（能口头回答才算过关）

- State / Node / Edge 分别是什么？State 是怎么在节点间传递的？
- 普通边和条件边的区别？
- `add_conditional_edges` 的三个参数分别是什么？
- 为什么图里不放 `send_text`？"图管决策，IO 留外面"有什么好处？
- L9 的 if/elif 和 L10 的条件边，本质区别是什么？（提示：逻辑从"代码里的分支"变成"数据驱动的边"——加新命令时改哪里？）

---

*做完把 graph_router.py 贴回来，我 review。下一课 L11：简历优化图——用 LangGraph 编排"分析 JD → 给意见 → 等用户确认 → 改写简历"，正式引入 `interrupt`（人工确认中断），这是校招虾最核心的 AI 功能。*
