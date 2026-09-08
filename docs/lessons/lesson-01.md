# Lesson 1 · 命令行投递记录本

> 配套代码：`cli/main.py`
> 学习目标：掌握 Python 最核心的 6 个概念，跑通第一个程序。

---

## 1. 怎么运行

在项目根目录 `D:\job_hunter` 打开终端（PowerShell），执行：

```powershell
# 方式一：直接指定虚拟环境里的 python
.venv\Scripts\python.exe cli\main.py

# 方式二：先激活虚拟环境，再用 python
.venv\Scripts\activate
python cli\main.py
```

你会看到一个菜单，选 `1` 输入公司和岗位，选 `2` 查看，选 `3` 改状态，选 `4` 退出。

> **什么是虚拟环境（.venv）？**
> 它给每个项目一个"独立的 Python + 依赖盒子"，避免项目 A 装的库污染项目 B。
> 一句话：**每个项目都有自己的 .venv，装包都装在里面**。以后我们装 FastAPI、LangGraph 都会装进这个 .venv。

---

## 2. 今天要搞懂的 6 个概念

对照 `cli/main.py` 看：

| 概念 | 一句话解释 | 在代码里的位置 |
|---|---|---|
| **变量** | 给一个值起名字 | `applications = []` |
| **列表 list** | 用 `[]` 装一串东西，可增删 | `applications` 就是列表 |
| **字典 dict** | 用 `{}` 装"键: 值"，按名字取 | `record = {"company": ...}` |
| **函数 function** | `def` 定义的一段可复用代码 | `add_application()` 等 |
| **循环 while/for** | 反复执行一段代码 | `while True:` 和 `for i, item in ...` |
| **分支 if/elif/else** | 按条件走不同路 | `if choice == "1":` 等 |

三个你可能第一次见的"魔法"，先记结论：

- `item["company"]` —— 字典取值，等价于"从这个盒子拿出 company 标签对应的东西"。
- `f"{i + 1}. ..."` —— f-string，花括号里写变量，会被替换成实际值。
- `if __name__ == "__main__":` —— "直接运行本文件才执行"，是 Python 的入口惯例。

---

## 3. 动手任务（必做，这是"学会"的关键）

按顺序做，每做一个就运行验证：

1. **加一个"删除投递"功能**：仿照 `update_status()` 写一个 `delete_application()`，菜单里加第 5 项。提示：用 `applications.pop(index)` 或 `del applications[index]`。
2. **把状态变成固定选项**：不要用户随便输状态，改成让用户在 `["已投递", "笔试", "面试", "Offer", "凉凉"]` 里选一个。
3. **故意弄坏再修**：把 `applications.append(record)` 这一行**删掉**，运行、看报错长什么样，再把它加回来。目标：以后见到报错不慌，会读最后一行错误信息。

---

## 4. 自测（能口头回答才算过关）

- 列表和字典的区别是什么？什么时候用哪个？
- `return` 在函数里起什么作用？
- 为什么 `update_status` 里要用 `try/except`？
- `break` 和 `return` 有什么不同？

---

*做完第 3 节的动手任务后，把你写的代码贴回来（或告诉我卡在哪），我来 review 并出 Lesson 2（把数据存进文件，让投递记录不丢失）。*
