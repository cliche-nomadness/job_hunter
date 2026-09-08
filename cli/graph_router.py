# cli/graph_router.py —— L10：用 LangGraph 重写命令路由（真实业务版）
#
# 架构：图管决策（节点只生成 replies），IO 留外面（process_message 负责发送）。
# 复用 server.py 里的 book / jobs / send_text / TRANSITIONS / resume 函数，
# 避免重复实现——graph_router 是 server.py 的"图版命令层"。

from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from server import book, jobs, send_text, TRANSITIONS, read_resume, get_resume_advice


class State(TypedDict):
    cmd: str          # 命令词（router 用它路由）
    text: str         # 原始消息文本（节点从它解析参数）
    replies: list[str]  # 要回复的内容列表（多条 = 顺序发送）


# ==================== 图节点：真实业务（L9 逻辑，send_text → return replies）====================

def do_add(state: State) -> State:
    parts = state["text"].split()
    if len(parts) != 3:
        return {"replies": ["格式：投递 公司 岗位\n例：投递 字节 后端"]}
    _, company, position = parts
    book.add(company, position)
    return {"replies": [f"✅ 已记录 {company} - {position}"]}


def do_progress(state: State) -> State:
    if len(book.applications) == 0:
        return {"replies": ["还没有投递记录"]}
    lines = [f"{i+1}. {a['company']} - {a['position']} [{a['status']}]"
             for i, a in enumerate(book.applications)]
    return {"replies": ["你的投递进度：\n" + "\n".join(lines)]}


def do_update(state: State) -> State:
    parts = state["text"].split()
    if len(parts) < 2:
        return {"replies": ["格式：更新 序号 [状态]\n· 更新 1 面试（直接改）\n· 更新 1（列出允许的状态）"]}
    try:
        idx = int(parts[1]) - 1
    except ValueError:
        return {"replies": ["序号要是数字，例：更新 1 面试"]}
    if idx < 0 or idx >= len(book.applications):
        return {"replies": ["序号超出范围"]}

    current = book.applications[idx]["status"]
    allowed = TRANSITIONS.get(current, [])

    if len(parts) == 2:                       # 「更新 1」→ 列出允许的状态
        if not allowed:
            return {"replies": [f"「{current}」已是终态，不能变更"]}
        lines = "\n".join(f"{i+1}. {s}" for i, s in enumerate(allowed))
        return {"replies": [f"当前「{current}」，可以变为：\n{lines}"]}

    new_status = parts[2]
    if not allowed:
        return {"replies": [f"「{current}」已是终态，不能变更"]}
    if new_status not in allowed:
        return {"replies": [f"不能从「{current}」变成「{new_status}」\n允许：{' / '.join(allowed)}"]}
    book.update_status(idx, new_status)
    return {"replies": [f"✅ 已更新为「{new_status}」"]}
    

def do_delete(state: State) -> State:
    parts = state["text"].split()
    if len(parts) != 2:
        return {"replies": ["格式：删除 序号\n例：删除 1"]}
    try:
        idx = int(parts[1]) - 1
    except ValueError:
        return {"replies": ["序号要是数字"]}
    if idx < 0 or idx >= len(book.applications):
        return {"replies": ["序号超出范围"]}
    removed = book.applications[idx]
    book.delete(idx)
    return {"replies": [f"🗑️ 已删除 {removed['company']} - {removed['position']}"]}


def do_jobs(state: State) -> State:
    if len(jobs) == 0:
        return {"replies": ["没有岗位数据，请先准备 jobs.csv"]}
    parts = state["text"].split()
    city = parts[1] if len(parts) > 1 else ""
    keyword = parts[2] if len(parts) > 2 else ""
    result = [j for j in jobs
              if (not city or j["城市"] == city)
              and (not keyword or keyword in j["岗位"])]
    if len(result) == 0:
        return {"replies": ["没有符合条件的岗位"]}
    lines = [f"{i+1}. [{j['城市']}] {j['公司']} - {j['岗位']}" for i, j in enumerate(result)]
    return {"replies": ["匹配岗位：\n" + "\n".join(lines)]}


def do_advice(state: State) -> State:
    parts = state["text"].split()
    if len(parts) != 2:
        return {"replies": ["格式：简历意见 序号（序号看「岗位」的列表）"]}
    if len(jobs) == 0:
        return {"replies": ["没有岗位数据"]}
    try:
        idx = int(parts[1]) - 1
    except ValueError:
        return {"replies": ["序号要是数字"]}
    if idx < 0 or idx >= len(jobs):
        return {"replies": ["序号超出范围"]}

    job = jobs[idx]
    resume_text = read_resume()
    if not resume_text:
        return {"replies": ["没有简历文件 resume.md"]}

    # 注意：AI 调用是同步的，"分析中"要等 AI 返回后才发出。
    # 真正的"先发分析中再出结果"需要 interrupt/流式，L11 再解决。
    advice = get_resume_advice(job["岗位"], job["JD"], resume_text)
    return {"replies": ["AI 正在分析，请稍候...",
                        advice if advice else "分析失败，请检查 DEEPSEEK_API_KEY"]}


def do_help(state: State) -> State:
    return {"replies": [
        "我是校招虾 🦐，支持：\n"
        "· 投递 公司 岗位 —— 记录投递\n"
        "· 我的进度 —— 查看投递列表\n"
        "· 更新 序号 状态 —— 更新状态（更新 序号 看可选）\n"
        "· 删除 序号 —— 删除投递\n"
        "· 岗位 城市 关键词 —— 筛选岗位（都可省略）\n"
        "· 简历意见 序号 —— AI 按岗位给简历意见\n"
        "· 帮助 —— 本菜单"
    ]}


# ==================== 路由节点 ====================

def router(state: State) -> str:
    """条件边的指路函数：返回下一个节点的名字。"""
    if state["cmd"] == "投递":
        return "do_add"
    if state["cmd"] == "我的进度":
        return "do_progress"
    if state["cmd"] == "更新":
        return "do_update"
    if state["cmd"] == "删除":
        return "do_delete"
    if state["cmd"] == "岗位":
        return "do_jobs"
    if state["cmd"] == "简历意见":
        return "do_advice"
    return "do_help"


# ==================== 建图 ====================

NODES = ["do_add", "do_progress", "do_update", "do_delete", "do_jobs", "do_advice", "do_help"]

builder = StateGraph(State)
builder.add_node("router", lambda s: s)          # 入口中转节点
for n in NODES:
    builder.add_node(n, globals()[n])            # 通过字符串变量名动态获取全局变量 把 do_* 函数注册成节点 

builder.add_edge(START, "router")
builder.add_conditional_edges(
    "router",
    router,                                      # 指路函数（返回 key）
    {n: n for n in NODES},                       # key → 节点 映射
)
for n in NODES:
    builder.add_edge(n, END)

graph = builder.compile()


# ==================== 图外面：process_message（真实发送）====================

def process_message(open_id, text, sender=send_text):
    """组 state → 跑图 → 逐条发送。open_id 只在这一层用。"""
    parts = text.split()
    cmd = parts[0] if parts else ""
    result = graph.invoke({"cmd": cmd, "text": text, "replies": []})
    for r in result.get("replies", []):
        sender(open_id, r)


# ==================== 测试入口（用假发送，不真发飞书）====================
if __name__ == "__main__":
    def fake_sender(open_id, text):
        print(f"📨 [{open_id}]\n{text}\n")

    print("========== 图路由测试 ==========")
    process_message("ou_test", "投递 字节 后端", sender=fake_sender)
    process_message("ou_test", "我的进度", sender=fake_sender)
    process_message("ou_test", "更新 1 面试", sender=fake_sender)
    process_message("ou_test", "你好呀", sender=fake_sender)
    print("========== 测试结束 ==========")
