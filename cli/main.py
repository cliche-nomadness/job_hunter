# -*- coding: utf-8 -*-
"""
校招虾 · Lesson 1：命令行投递记录本（阶段 0 里程碑）

功能只有三件事：
  1. 记录一条投递
  2. 查看所有投递
  3. 更新某条投递的状态

它刻意"很简陋"：数据存在内存里（程序一退出就没了），
目的是让你先熟悉 Python 最核心的 6 个概念：
  - 变量 variable
  - 列表 list        （用方括号 [] 表示的一串东西）
  - 字典 dict        （用花括号 {} 表示的一堆"键: 值"）
  - 函数 function    （用 def 定义的一段可复用代码）
  - 循环 while / for
  - 分支 if / elif / else

运行方式（在项目根目录 D:\\job_hunter 下）：
  .venv\\Scripts\\python.exe cli\\main.py
（或者先 .venv\\Scripts\\activate 再 python cli\\main.py）
"""
import os
import csv
from resume import read_resume, parse_resume_sections, get_resume_advice
from application_book import ApplicationBook, TRANSITIONS

JOBS_FILE = "jobs.csv"
jobs = []  # 全局列表，装岗位



def filter_jobs():
    """按城市和关键词筛选岗位并打印。"""
    city = input("按城市筛选（回车跳过）：").strip()
    keyword = input("按岗位关键词筛选（回车跳过）：").strip()

    result = jobs
    if city:
        result = [j for j in result if j["城市"] == city]
    if keyword:
        result = [j for j in result if keyword in j["岗位"]]

    if len(result) == 0:
        print("（没有符合条件的岗位）")
        return
    for i, job in enumerate(result):
        print(f"{i + 1}. [{job['城市']}] {job['公司']} - {job['岗位']}")

def ai_advice_flow():
    """菜单入口：选一个岗位 → 读简历 → 调 AI → 打印意见。"""
    if len(jobs) == 0:
        print("[!] 没有岗位，先导入 jobs.csv")
        return
    list_jobs()
    try:
        idx = int(input("输入要分析的岗位序号：")) - 1
        if idx < 0 or idx >= len(jobs):
            print("[!] 序号超出范围")
            return
    except ValueError:
        print("[!] 请输入数字")
        return
    job = jobs[idx]
    resume_text = read_resume()
    if not resume_text:
        return
    resume_contents = parse_resume_sections(resume_text)  # 把简历文本解析成字典
    print("===== 读取简历 =====")
    print(resume_contents)
    print("\nAI 正在分析，请稍候...\n")
    advice = get_resume_advice(job["岗位"], job["JD"], resume_text)
    if advice:
        print("===== AI 修改意见 =====")
        print(advice)

def load_jobs():
    """程序启动时，把jobs.csv 文件里的数据读回 jobs 列表。"""
    global jobs  #因为是重新赋值jobs，所以要加global关键字
    if not os.path.exists(JOBS_FILE):
        jobs = []
        return
    with open(JOBS_FILE, "r",encoding="utf-8-sig") as f:
        reader = csv.DictReader(f) # csv库的DictReader函数，读取csv文件，返回一个迭代器，每个迭代器元素是一个字典，字典的键是csv文件的第一行的列名，值是csv文件对应行的列值
        jobs = list(reader) #把reader 一次性转成列表

def list_jobs():
    """打印所有岗位."""
    if len(jobs) == 0:
        print("没有岗位，请先准备 jobs.csv")
        return
    for i,job in enumerate(jobs):
        print(f"{i+1}. [{job['城市']}] {job['公司']} - {job['岗位']}")


# ── 5. 主循环 ──────────────────────────────────────────────────────
def menu():
    """反复显示菜单，直到用户选 5 退出。"""
    book = ApplicationBook("applications.json")
    while True:                          # while True 表示"永远循环"
        print("\n===== 校招虾 · 投递记录本 =====")
        print("1. 添加投递")
        print("2. 查看投递")
        print("3. 更新状态")
        print("4. 删除投递")
        print("5. 筛选岗位")
        print("6. AI修改意见")
        print("0. 退出")
        choice = input("请选择（0-6）：").strip()

        if choice == "1":
            company = input("公司名称：").strip()
            position = input("岗位名称：").strip()
            book.add(company, position)
        elif choice == "2":
            book.list_all()
        elif choice == "3":
            book.list_all()
            try:
                idx = int(input("输入要更新的投递序号：")) - 1
                if idx < 0 or idx >= len(book.applications):
                    print("[!] 序号超出范围")
                    continue
            except ValueError:
                print("[!] 请输入数字")
                continue
            now_status = book.applications[idx]["status"]
            next_status_list = TRANSITIONS.get(now_status,[])
            if len(next_status_list) == 0:
                print(f"[!] {now_status} 已经是终态，无法更新")
                continue
        
            for i, item in enumerate(next_status_list):
                print(f"{i+1}. {item}")
            try:
                new_status_idx = int(input("输入要更新的状态序号：")) - 1
                if new_status_idx < 0 or new_status_idx >= len(next_status_list):
                    print("[!] 序号超出范围")
                    continue
            except ValueError:
                print("[!] 请输入数字")
                continue
            new_status = next_status_list[new_status_idx]
            book.update_status(idx,new_status)
        elif choice == "4":
            if len(book.applications) == 0:
                print("[!] 没有投递记录")
                continue
            book.list_all()
            try:
                idx = int(input("输入要删除的投递序号：")) - 1
                if idx < 0 or idx >= len(book.applications):
                    print("[!] 序号超出范围")
                    continue
            except ValueError:
                print("[!] 请输入数字")
                continue
            book.delete(idx)
        elif choice == "5":
            filter_jobs()
        elif choice == "6":
            ai_advice_flow()
        elif choice == "0":
            print("再见！")
            break                       # break 跳出 while 循环
        else:
            print("[!] 请输入 0-6 之间的数字")

# ── 6. 程序入口 ────────────────────────────────────────────────────
# 这是 Python 的常见写法：只有当"直接运行本文件"时才执行下面的代码。
# （如果别人 import 这个文件，则不会自动弹出菜单。）
if __name__ == "__main__":
    load_jobs()
    menu()
