# Lesson 5 · 拆模块 + 用类(class)重构

> 目标：把 330 行的 `main.py` 拆开，用**类**封装数据，**告别 `global`**。
> 前置：L1–L4 全部过关。
> 铁律：**重构 = 行为不变，结构变**。改完所有菜单功能必须和之前一模一样。

---

## 0. 为什么要做这件事

1. `main.py` 已经 330 行了：一个文件装下所有东西 → 找东西难、改一处担心影响别处。
2. 存在**技术债**：`global applications` 这种全局变量很危险——任何函数都能改它，出了 bug 很难定位"是谁改的"。
3. 程序员的组织方式：**一个文件只负责一类事情**（这就是"单一职责"在文件级别的体现）。

---

## Part A · 拆模块（纯搬家，不动逻辑）

### 1. 什么是"模块"

一个 `.py` 文件就是一个模块。别的文件用 `import` 来使用它里面的函数。好处：职责清晰、能单独测试、`main.py` 变薄。

### 2. 第一个模块：`resume.py`

你的 `read_resume()` / `parse_resume_sections()` / `get_resume_advice()` 这三个函数**不碰任何全局变量**（全靠参数传值），是纯函数——**搬家零风险**，最适合先拆。

**任务 A1**：新建 `cli/resume.py`，把这三个函数**原样搬进去**，并在文件顶部带上它们需要的 import：

```python
# cli/resume.py
import os
import requests

RESUME_FILE = "resume.md"

def read_resume():
    """读简历文件，返回文本。"""
    if not os.path.exists(RESUME_FILE):
        print("[!] 没有 resume.md")
        return ""
    with open(RESUME_FILE, "r", encoding="utf-8") as f:
        return f.read()

# ... parse_resume_sections() 和 get_resume_advice() 也原样搬进来
```

**任务 A2**：`main.py` 顶部**删掉这三个函数的定义**，换成一行 import：

```python
from resume import read_resume, parse_resume_sections, get_resume_advice
```

**运行验证**：所有功能必须和之前一模一样。

> import 两种写法：
> - `import resume` → 使用时写 `resume.read_resume()`
> - `from resume import read_resume` → 直接写 `read_resume()`
>
> 自己写的模块常用 **from 形式**（写起来短）。注意：main.py 和 resume.py 在同一个 `cli/` 目录下才能这样 import。

---

## Part B · 用类封装 ApplicationBook（核心，新概念）

### 3. 什么是"类"（class）

类 = **数据 + 操作这些数据的方法，打包成一个模板**。

| | 以前的写法 | 类的写法 |
|---|---|---|
| 数据 | 全局变量 `applications` | 实例属性 `self.applications` |
| 操作 | 散落的函数 + `global` | 类里的方法（add/update/delete…） |
| 访问 | 谁都碰得到全局 | 只能通过实例去操作 |

**三个新关键词**：

| 关键词 | 作用 | 类比 |
|---|---|---|
| `class 名字:` | 定义类（模板） | 一张"账本"的设计图纸 |
| `__init__` | 构造函数：创建实例时自动执行 | 按图纸"造出"一本具体的账本 |
| `self` | 代表"这个实例自己" | 账本自己身上写着的"这是我的数据" |

### 4. ApplicationBook 类参考代码

新建 `cli/application_book.py`：

```python
# cli/application_book.py
import json
import os

# 状态机迁移表（从 main.py 搬过来，作为模块级常量）
TRANSITIONS = {
    "已投递": ["笔试", "面试", "凉凉"],
    "笔试":   ["面试", "凉凉"],
    "面试":   ["Offer", "凉凉"],
    "Offer":  ["已接受", "已拒绝"],
    "已接受": [],
    "已拒绝": [],
    "凉凉":   [],
}

class ApplicationBook:
    """投递记录本：数据（applications）+ 操作，全部打包在一起。"""

    def __init__(self, data_file):
        self.data_file = data_file     # 属性：这个账本对应的文件
        self.applications = []         # 属性：记录列表（不再是全局变量！）
        self.load()                    # 创建时自动读文件

    def load(self):
        """从文件读记录。"""
        if os.path.exists(self.data_file):
            with open(self.data_file, "r", encoding="utf-8") as f:
                self.applications = json.load(f)

    def save(self):
        """把记录写回文件。"""
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.applications, f, ensure_ascii=False, indent=2)

    def add(self, company, position):
        """新增一条投递，状态固定"已投递"。"""
        record = {"company": company, "position": position, "status": "已投递"}
        self.applications.append(record)
        self.save()
        print(f"[OK] 已记录 {company} - {position}")

    def list_all(self):
        """打印所有记录。"""
        if len(self.applications) == 0:
            print("（还没有任何投递记录）")
            return
        for i, item in enumerate(self.applications):
            print(f"{i + 1}. {item['company']} - {item['position']} [{item['status']}]")

    def update_status(self, index, new_status):
        """更新第 index 条记录的状态（带状态机校验）。"""
        current = self.applications[index]["status"]
        allowed = TRANSITIONS.get(current, [])
        if len(allowed) == 0:
            print(f"[!] 当前状态是「{current}」，这是终态，不能变更")
            return
        if new_status not in allowed:
            print(f"[!] 不能从「{current}」变成「{new_status}」（允许：{allowed}）")
            return
        self.applications[index]["status"] = new_status
        self.save()
        print("[OK] 已更新")

    def delete(self, index):
        """删除第 index 条记录。"""
        self.applications.pop(index)
        self.save()
        print("[OK] 已删除")
```

### 5. 类为什么能消灭 `global`

- 以前：函数要改 `applications`，必须 `global applications`（因为函数里 `applications = ...` 会被当成局部变量）。
- 现在：数据住在 `self.applications` 里，方法是**通过 `self` 操作自己的数据**，根本不需要 global。

**额外大奖**：类可以创建**多个互不干扰的实例**：

```python
qiuzhao = ApplicationBook("qiuzhao.json")    # 秋招账本
chunzhao = ApplicationBook("chunzhao.json")  # 春招账本
```
全局变量做不到这一点（全世界只有一个 `applications`）。

### 6. 任务 B

1. 新建 `cli/application_book.py`，把上面的类写进去（可以边看边敲，别直接复制粘贴，敲一遍才有手感）。
2. 改造 `main.py`：
   - **删掉**：全局 `applications`、`DATA_FILE`、`load_data()`、`save_data()`、`add_application()`、`update_status()`、`delete_application()`、`list_applications()`。
   - 顶部加：`from application_book import ApplicationBook, TRANSITIONS`
   - 程序入口改：
     ```python
     book = ApplicationBook("applications.json")
     ```
   - 菜单里改调类方法：
     ```python
     # 原来的 add_application() → 输入 company/position 后：
     book.add(company, position)

     # 原来的 list_applications() → book.list_all()

     # 原来的 update_status() → 保留"选记录序号"的输入逻辑，然后：
     #   让用户从 TRANSITIONS.get(当前状态, []) 里选，再 book.update_status(index, 新状态)
     # 原来的 delete_application() → 保留"选序号"逻辑，然后 book.delete(index)
     ```
3. **运行验证（铁律）**：添加/查看/更新（含终态拦截）/删除/筛选/AI 意见，全部和之前一样。

### 7. 顺便清理

之前注释掉的 `status_list`（第 36 行）和 `add_application` 里的大注释块——现在函数都删了，这些注释**一并删除**，不留残余。

---

## Part C（选做）· 给 jobs 也做一个类

`jobs` 目前还是全局变量（它只是只读的参考数据，风险小，先留着没问题）。想挑战的话：

```python
class JobBoard:
    """岗位库：读 CSV、筛选、列出。"""

    def __init__(self, jobs_file):
        self.jobs_file = jobs_file
        self.jobs = []
        self.load()

    def load(self):
        # ... 用 csv.DictReader 读 jobs_file，存进 self.jobs
        pass

    def filter_by(self, city="", keyword=""):
        # ... 返回筛选后的列表（用列表推导式）
        pass
```

## 验证清单（做完逐条打勾）

- [ ] `main.py` 里**不再有任何 `global` 关键字**
- [ ] `main.py` 明显变薄（只剩菜单 + 输入输出 + imports）
- [ ] `resume.py` / `application_book.py` 职责清晰、能独立阅读
- [ ] 添加投递 → 已投递 ✅；更新（含终态拦截）✅；删除 ✅
- [ ] 筛选岗位 ✅；AI 简历意见（读简历 + 出意见）✅
- [ ] 数据仍持久化（重启后记录还在）

## 弄坏再修（必做）

1. 把 `book = ApplicationBook(...)` 注释掉再运行 → 看 `NameError`，理解"实例必须存在才能用"。
2. 故意删掉 `__init__` → 运行看 `TypeError`，理解构造函数的必要性。
3. 在方法里把 `self.applications` 写成 `applications` → 看 `NameError`，理解 `self` 的作用。

## 自测题（能口头回答才算过关）

- 模块是什么？为什么把 resume 三个函数搬出去是"零风险"的？
- `import resume` 和 `from resume import read_resume` 的区别？
- `self` 是什么？为什么方法里必须写 `self.applications`？
- `__init__` 什么时候执行？创建 2 个实例执行几次？
- 类为什么能消灭 `global`？多实例为什么是全局变量做不到的？
- 重构的铁律是什么？为什么"功能必须和之前一样"是底线？

---

*做完把新的 `main.py` + `resume.py` + `application_book.py` 都贴回来，我 review。下一课 L6 开始进阶段 2：FastAPI 入门——你的校招虾要长出"服务"形态，为接飞书做准备。*
