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
    return{"report": report}

def confirm(state):
    answer = interrupt("确认改写吗？ 回复 确认/取消") #关键点：图在这里暂停
    print(">>> [节点2 confirm] 收到:", answer)
    return {"result": "已改写" if answer else "已取消"}

builder = StateGraph(State)
builder.add_node("analyze", analyze)
builder.add_node("confirm", confirm)
builder.add_edge(START, "analyze")
builder.add_edge("analyze", "confirm")
builder.add_edge("confirm", END)
graph = builder.compile(checkpointer=MemorySaver()) #← 必须：装“暂停记忆”

# ① 第一次 invoke：跑到 interrupt 暂停
out = graph.invoke({"job": "字节-后端"},
                   config={"configurable": {"thread_id": "会话1"}})
print("第一次返回:", out)      # 里有 report 和 __interrupt__（"确认改写吗？"）

# ② 恢复：同一个 thread_id，告诉它"确认"
out2 = graph.invoke(Command(resume=True),
                    config={"configurable": {"thread_id": "会话1"}})
print("恢复后:", out2)         # {'result': '已改写'}