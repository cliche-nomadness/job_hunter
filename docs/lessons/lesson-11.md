# Lesson 11 · 简历优化图（分析 → 人工确认 → 改写）★ AI 改简历

> 目标：用 LangGraph 的 **interrupt** 实现校招虾最核心的 AI 功能——针对岗位改简历，且**必须先经过你确认**才动手改写。
> 前置：L10 完成（理解 State/Node/Edge）。
> 路线调整：**PDF 渲染延后到 L14**（Windows 装 weasyprint/playwright 是安装地狱），L11 产出是**版本化 Markdown** 新简历。

---

## 0. 本课要解决的问题（为什么 L9/L10 做不到）

L9/L10 的图是**一口气跑完**的。但"AI 改简历"不能这样：

```
❌ 一口气跑：AI 直接改写并覆盖你的简历 → 改坏了连后悔药都没有
✅ 必须：先分析给意见 → 等你拍板 → 才动手改写
```

**"等用户拍板"在流程图里是一个特殊的东西**——图走到这里要**暂停**，把控制权交回外面，等用户回复后再**从暂停处继续**。LangGraph 管这个叫 **interrupt（中断）**。

---

## Part A · interrupt：让图停下来等用户

### A1. 机制三件套（先记这三个词）

| 概念 | 作用 | 类比 |
|---|---|---|
| **`interrupt(问题)`** | 在节点里调用 → 图暂停并把这个"问题"交回外面 | 剧里喊"卡！"，全场停住 |
| **checkpointer**（MemorySaver）| 把"暂停到哪了、当前 state 是啥"**存起来** | 暂停键 + 记忆 |
| **`thread_id`** | 每次"恢复"都要靠它找到**暂停的那条会话** | 摄影棚编号（多场戏互不串）|

**缺一不可**：不装 checkpointer，interrupt 直接报错；恢复时不带同一个 thread_id，找不到暂停点。

### A2. 最小 demo（已验证可跑，新建 `cli/interrupt_demo.py`）

```python
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver

class State(TypedDict):
    job: str
    report: str
    result: str

def analyze(state):
    report = f"针对「{state['job']}」的匹配分析报告（模拟）"
    print(">>> [节点1 analyze] 完成")
    return {"report": report}

def confirm(state):
    answer = interrupt("确认改写吗？回复 确认/取消")   # ← 关键：图在这里暂停
    print(">>> [节点2 confirm] 收到:", answer)
    return {"result": "已改写" if answer else "已取消"}

builder = StateGraph(State)
builder.add_node("analyze", analyze)
builder.add_node("confirm", confirm)
builder.add_edge(START, "analyze")
builder.add_edge("analyze", "confirm")
builder.add_edge("confirm", END)
graph = builder.compile(checkpointer=MemorySaver())   # ← 必须：装"暂停记忆"

# ① 第一次 invoke：跑到 interrupt 暂停
out = graph.invoke({"job": "字节-后端"},
                   config={"configurable": {"thread_id": "会话1"}})
print("第一次返回:", out)      # 里有 report 和 __interrupt__（"确认改写吗？"）

# ② 恢复：同一个 thread_id，告诉它"确认"
out2 = graph.invoke(Command(resume=True),
                    config={"configurable": {"thread_id": "会话1"}})
print("恢复后:", out2)         # {'result': '已改写'}
```

**运行**：`..\.venv\Scripts\python.exe interrupt_demo.py`

**三个观察**：
1. 第一次 invoke **不会**走到 confirm 的函数体后半段——它在 `interrupt()` 那行停住，返回的 state 里有 `__interrupt__`；
2. 恢复用 `Command(resume=True)` **必须带同一个 thread_id**，图才能找回暂停点继续；
3. `interrupt()` 的返回值 = 你恢复时传的 `resume` 值（True/False/任意东西）——这是"外面把用户的选择传回图里"的通道。

### A3. 弄坏再修

1. 恢复时**换 thread_id** → KeyError，理解"thread_id 是会话钥匙"；
2. **删掉 checkpointer** 再跑 → interrupt 报错，理解"必须持久化才能暂停"。

---

## Part B · 简历优化图（真实业务）

### B1. 流程图（本课核心）

```
「优化简历 1」
   ↓
[analyze]  调 DeepSeek 分析岗位JD vs 简历 → 生成匹配报告
   ↓
[confirm]  interrupt("确认改写吗？")  ← 图暂停！
   ↓（外面拿到报告 + 提示，等用户回复）
[rewrite]  用户确认 → 调 DeepSeek 按报告改写简历 → 存新版本（resume_时间戳.md）
            用户取消 → 不改写，回复"已取消"
```

**checkpointer 的妙用**：暂停后 state（包括选中的岗位 job）**都被记住了**——恢复时不用再告诉它"哪个岗位"，它还记得。

### B2. 需要的零件（复用 + 新增）

| 零件 | 来源 |
|---|---|
| `read_resume` | resume.py（已有）|
| `get_resume_advice` | resume.py（已有，分析步骤可复用它）|
| 调 DeepSeek 的通用函数 | 新建 `call_deepseek`（本课）|
| 版本化保存 | 新建（时间戳文件名）|

### B3. 完整代码（新建 `cli/graph_resume.py`）

```python
# cli/graph_resume.py —— 简历优化图（分析 → 确认 → 改写）
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver
from pathlib import Path
import os
import time
import requests
from server import jobs, read_resume, get_resume_advice

BASE_DIR = Path(__file__).resolve().parent.parent
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")


class State(TypedDict):
    job: dict          # 选中的岗位（暂停时会被记住）
    report: str        # 分析报告
    confirmed: bool    # 用户是否确认
    result: str        # 最终结果（新版本文件名 / 取消说明）


def call_deepseek(system, user):
    """调 DeepSeek 返回文本；失败或没 key 返回空串。"""
    if not DEEPSEEK_API_KEY:
        print("[!] 未设置 DEEPSEEK_API_KEY")
        return ""
    resp = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                 "Content-Type": "application/json"},
        json={"model": "deepseek-chat",
              "messages": [{"role": "system", "content": system},
                           {"role": "user", "content": user}],
              "temperature": 0.5},
        timeout=120)
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def analyze(state: State) -> State:
    """节点1：分析岗位JD vs 简历，生成匹配报告。"""
    job = state["job"]
    resume_text = read_resume()
    report = call_deepseek(
        "你是专业的校招简历顾问。",
        f"岗位：{job['岗位']}\n岗位要求(JD)：{job['JD']}\n\n我的简历：\n{resume_text}\n\n"
        "请分析简历与岗位的匹配情况，指出差距，并给出具体修改建议（分点）。")
    return {"report": report or "（分析失败，请检查 DEEPSEEK_API_KEY）"}


def confirm(state: State) -> State:
    """节点2：暂停，等用户确认。interrupt 的返回值就是恢复时传的 resume 值。"""
    answer = interrupt("确认按报告改写简历吗？回复「确认」或「取消」")
    return {"confirmed": bool(answer)}


def rewrite(state: State) -> State:
    """节点3：确认则改写并存新版本；取消则不动。"""
    if not state.get("confirmed"):
        return {"result": "已取消，简历未改动"}

    job = state["job"]
    resume_text = read_resume()
    new_text = call_deepseek(
        "你是简历改写专家。保留原简历中的事实（学校/公司/时间），只优化表达与针对性。",
        f"岗位：{job['岗位']}\n\n根据以下分析意见改写我的简历：\n{state['report']}\n\n"
        f"原简历：\n{resume_text}\n\n输出改写后的完整简历（Markdown 格式）。")

    if not new_text:
        return {"result": "改写失败，请检查 DEEPSEEK_API_KEY"}

    filename = f"resume_{time.strftime('%Y%m%d_%H%M%S')}.md"   # 版本化：时间戳文件名
    with open(BASE_DIR / filename, "w", encoding="utf-8") as f:
        f.write(new_text)
    return {"result": f"✅ 已生成新版本：{filename}"}


builder = StateGraph(State)
builder.add_node("analyze", analyze)
builder.add_node("confirm", confirm)
builder.add_node("rewrite", rewrite)
builder.add_edge(START, "analyze")
builder.add_edge("analyze", "confirm")
builder.add_edge("confirm", "rewrite")
builder.add_edge("rewrite", END)
graph = builder.compile(checkpointer=MemorySaver())


# ==================== 外面两步操作（组 state / 恢复）====================

def start_optimize(job_index, thread_id):
    """第一步：选岗位 → 跑图 → 返回（含报告，图停在确认处）。"""
    job = jobs[job_index]
    out = graph.invoke({"job": job, "report": "", "confirmed": None, "result": ""},
                       config={"configurable": {"thread_id": thread_id}})
    return out


def finish_optimize(answer, thread_id):
    """第二步：用户确认/取消 → 恢复图 → 返回最终结果。"""
    out = graph.invoke(Command(resume=answer),
                       config={"configurable": {"thread_id": thread_id}})
    return out


# ==================== CLI 测试（先不接飞书）====================
if __name__ == "__main__":
    print("可用岗位：")
    for i, j in enumerate(jobs):
        print(f"{i+1}. {j['公司']} - {j['岗位']}")
    n = int(input("输入要优化的岗位序号：")) - 1
    thread = "cli-test"

    out = start_optimize(n, thread)
    print("\n===== 匹配报告 =====")
    print(out["report"])
    print("\n===== 图已暂停，等待确认 =====")

    ans = input("确认改写？(y/n)：").strip().lower() == "y"
    out2 = finish_optimize(ans, thread)
    print("\n===== 结果 =====")
    print(out2["result"])
```

**运行**：设好 `DEEPSEEK_API_KEY` 后 `..\.venv\Scripts\python.exe graph_resume.py` → 选岗位 → 看报告 → 确认/取消。

### B4. 简化策略（YAGNI 声明）

- **整篇改写**起步（让 AI 输出完整新简历），**区块级改写**（只改"项目经历"等 section）作为进阶练习——还记得 L4 的 `parse_resume_sections` 吗？那就是以后按区块改写的原料。
- **PDF 延后 L14**（Windows 装渲染库是坑，L14 工程化时一并处理）。
- 版本化用"时间戳文件名"，不做复杂版本管理（够用）。

---

## Part C · 接入飞书：thread_id = open_id + 状态守卫 + 卡片按钮

> 把 graph_resume.py 接进飞书。**重点：interrupt 让"跨消息等待"技术上可行，但"待确认状态"是隐式、无引导的——技术可行 ≠ 体验清晰，要主动设计。** 这是本课最值得讲的"设计权衡"。

### C1. 核心思路（两步 + thread_id = open_id）

- **`thread_id = open_id`**：把每个用户当成"一条独立会话线"，谁暂停的谁恢复，天然多用户隔离。
- **两步流程**：
  ```
  ① 「优化简历 序号」 → start_optimize(n, open_id) → 图暂停在 confirm → 发报告 + 提示
  ② 「确认 / 取消」      → finish_optimize(确认?, open_id) → 恢复图 → 发结果
  ```
- **岗位序号 n 不用记**：它存在图的 state 里（checkpointer 记住了），恢复时 rewrite 节点自动知道改哪个岗位。

### C2. 你一定会撞上的 UX 问题（别等踩坑再后悔）

| 问题 | 表现 |
|---|---|
| **幽灵确认** | 发了「优化简历」后，中间发了 N 条别的命令，最后突然「确认」——技术上还能恢复图，但体验很怪，用户自己可能都忘了在确认什么 |
| **悬挂无期** | 一直不确认，图的暂停状态一直占着内存 |
| **无 pending 却确认** | 没发优化却发「确认」，会误触/报错 |

**根因**：interrupt 把"等待"做成了技术可行的，但用户感知不到"有一个流程在等我"，所以混乱。

### C3. 解法一：状态守卫 + 明确提示（改动小，先做）

```python
import time
_pending_optimize = {}   # {open_id: 发起时间} —— 谁在等确认

def cmd_optimize(open_id, parts):
    if len(parts) != 2:
        send_text(open_id, "格式：优化简历 序号（序号看「岗位」的列表）")
        return
    try:
        n = int(parts[1]) - 1
    except ValueError:
        send_text(open_id, "序号要是数字")
        return
    _pending_optimize[open_id] = time.time()
    out = start_optimize(n, open_id)
    send_text(open_id, out["report"])
    send_text(open_id, "这是一个待确认的简历优化，请回复「确认」或「取消」。可以先做别的，但要记得回来确认。")

def cmd_confirm(open_id, confirmed):
    if open_id not in _pending_optimize:
        send_text(open_id, "当前没有待确认的简历优化（先发「优化简历 序号」）")
        return
    del _pending_optimize[open_id]
    out2 = finish_optimize(confirmed, open_id)
    send_text(open_id, out2["result"])

# （可选）超时清理：定时任务里删除超过 10 分钟的 pending，解决"悬挂无期"
```

**效果**：没 pending 时「确认」会提示"没有待确认的"；明确提示让用户知道流程在等；超时清理防悬挂。

### C4. 解法二：卡片按钮（最佳体验，推荐，与架构 §9"确认改写按钮"一致）

把"**打字确认**"升级成"**点卡片按钮**"——意图明确、不会误触「确认」这个词、无歧义、随时点。

```python
def send_confirm_card(open_id, report):
    """发一张带「确认改写」「放弃」按钮的卡片。复用 L8 的 send_card（msg_type=interactive）。"""
    card = {
        "config": {"wide_screen_mode": True},
        "header": {"title": {"tag": "plain_text", "content": "简历优化确认"}},
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": report}},
            {"tag": "action", "actions": [
                {"tag": "button", "text": {"tag": "plain_text", "content": "确认改写"},
                 "value": {"cmd": "optimize_confirm"}},
                {"tag": "button", "text": {"tag": "plain_text", "content": "放弃"},
                 "value": {"cmd": "optimize_cancel"}},
            ]},
        ],
    }
    send_card(open_id, "📋 简历优化", card)   # send_card 签名按 L8 的实现调整

def cmd_optimize(open_id, parts):
    ...   # 同 C3，只是最后改成：
    send_confirm_card(open_id, out["report"])   # 用卡片+按钮，不用纯文本提示
```

**处理按钮回调**（在 `server.py` 的 `/feishu/event`，L8 讲过 `card.action.trigger`）：

```python
# 在进 SDK 前拦截卡片回调：
if body.get("type") == "card.action.trigger":
    value = body["action"]["value"]           # {"cmd": "optimize_confirm"} 或 "optimize_cancel"
    open_id = body["operator"]["open_id"]
    if value.get("cmd") == "optimize_confirm":
        cmd_confirm(open_id, True)
    elif value.get("cmd") == "optimize_cancel":
        cmd_confirm(open_id, False)
    return {"code": 0}
```

### C5. 最佳实践总结

| 问题 | 解法 |
|---|---|
| 幽灵确认（穿插命令后突然确认）| **状态守卫**（确认只在有 pending 时生效）+ 明确提示 |
| 悬挂无期 | **超时清理**（N 分钟作废）|
| 打字确认易误触/歧义 | **卡片按钮**（点选替代打字）|
| 多用户并发 | `thread_id = open_id` 天然隔离 |

> **面试点**：技术上 interrupt 支持跨消息等待确认，但**纯技术可行 ≠ 体验清晰**——我用"状态守卫 + 明确提示 + 超时清理"消除了悬挂和歧义，并用**卡片按钮**把打字确认升级成点选确认。**技术可行性和用户体验要一起设计。**

---

---

## 验证清单（做完逐条打勾）

- [ ] `interrupt_demo.py`：第一次返回含 `__interrupt__`，恢复后 `result: 已改写`
- [ ] `graph_resume.py`：选岗位 → 出报告 → 图暂停
- [ ] 回「y」→ 生成 `resume_时间戳.md`（打开看是不是改写后的完整简历）
- [ ] 再跑一次回「n」→ 显示"已取消，简历未改动"，且**没有**生成新文件
- [ ] （选做）接入飞书：发「优化简历 1」→ 收到报告+提示 → 回「确认」→ 收到新版本文件名

## 弄坏再修（必做）

1. 恢复时**换 thread_id** → KeyError，理解"会话钥匙"。
2. **删掉 checkpointer** 跑 interrupt → 报错，理解"暂停必须持久化"。
3. 第一次跑**不设 DEEPSEEK_API_KEY** → 报告显示"分析失败"，理解 key 的重要性。

## 自测题（能口头回答才算过关）

- `interrupt()` 做了什么？图暂停后，控制权在哪？
- 为什么 interrupt 必须配 checkpointer？thread_id 是干嘛的？
- 恢复时传的 `resume` 值和 `interrupt()` 的返回值是什么关系？
- 为什么"人工确认"对改简历是**必须**的，而不是可选项？
- `thread_id = open_id` 意味着什么？为什么岗位序号不用额外记录？
- 版本化为什么要用时间戳文件名？

---

*做完把 graph_resume.py 贴回来，我 review。下一课 L12：工程化——PostgreSQL/Redis/对象存储/Docker，把"文件即数据"升级成"数据库即数据"，并顺带把 PDF 渲染补上（L11 延后的账）。*
