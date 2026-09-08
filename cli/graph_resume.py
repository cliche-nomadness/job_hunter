# cli/graph_resume.py —— 简历优化图（分析 → 确认 → 改写）
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver
from pathlib import Path
import os
import time
import requests
from application_book import ApplicationBook, TRANSITIONS
from resume import read_resume, get_resume_advice


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

def start_optimize(job, thread_id):
    """第一步：传入岗位(字典) → 跑图 → 返回（含报告，图停在确认处）。
    注意：不依赖全局 jobs，岗位由调用方（server 的 cmd_optimize）解析后传入。"""
    out = graph.invoke({"job": job, "report": "", "confirmed": None, "result": ""},
                       config={"configurable": {"thread_id": thread_id}})
    return out


def finish_optimize(answer, thread_id):
    """第二步：用户确认/取消 → 恢复图 → 返回最终结果。"""
    out = graph.invoke(Command(resume=answer),
                       config={"configurable": {"thread_id": thread_id}})
    return out


# ==================== CLI 测试（独立运行用，接入飞书后可不跑这块）====================
if __name__ == "__main__":
    import csv
    # 独立测试时自己加载岗位（接入 server 后由 server 传入岗位）
    jobs = []
    if os.path.exists("jobs.csv"):
        with open("jobs.csv", "r", encoding="utf-8-sig") as f:
            jobs = list(csv.DictReader(f))
    print("可用岗位：")
    for i, j in enumerate(jobs):
        print(f"{i+1}. {j['公司']} - {j['岗位']}")
    n = int(input("输入要优化的岗位序号：")) - 1
    thread = "cli-test"

    out = start_optimize(jobs[n], thread)
    print("\n===== 匹配报告 =====")
    print(out["report"])
    print("\n===== 图已暂停，等待确认 =====")

    ans = input("确认改写？(y/n)：").strip().lower() == "y"
    out2 = finish_optimize(ans, thread)
    print("\n===== 结果 =====")
    print(out2["result"])