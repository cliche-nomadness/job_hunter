# Lesson 2 · JSON 文件持久化

> 目标：让投递记录在程序退出后不丢失。
> 前置：已完成 Lesson 1，能运行 `cli/main.py`。

---

## 1. 要解决的问题

现在的数据存在内存里的 `applications` 列表，**程序一退出就全没了**。这一课我们把它存到磁盘文件 `applications.json`，下次启动时读回来。

---

## 2. 核心概念（5 分钟读懂）

### 2.1 JSON 是什么

JSON 是一种**纯文本**格式，长得几乎和 Python 的 `list`/`dict` 一模一样。我们当前的数据：

```python
[{"company": "字节", "position": "后端", "status": "已投递"}]
```

直接就能写进一个 `.json` 文件。Python 用 `json` 模块在这两者之间"翻译"。

### 2.2 四个函数，两两一组

| 函数 | 作用 | 记忆 |
|---|---|---|
| `json.dump(obj, file)` | 把 Python 对象**写进文件** | dump = "倒进"文件 |
| `json.load(file)` | 从文件**读回** Python 对象 | load = "装回来" |
| `json.dumps(obj)` | 把对象转成**字符串**（不写文件） | 末尾的 s = string |
| `json.loads(str)` | 把字符串转回对象 | 同上 |

我们这次用**带文件的** `dump`/`load`。

### 2.3 `open()` 的三种模式

```python
open("a.json", "r")   # r = read   读（文件必须存在）
open("a.json", "w")   # w = write  写（文件不存在会创建；存在会清空重写）
open("a.json", "a")   # a = append 追加（在末尾接着写）
```

中文要加 `encoding="utf-8"`，否则 Windows 上可能乱码。

### 2.4 `with` 帮你自动关文件

```python
with open("a.json", "w", encoding="utf-8") as f:
    json.dump(applications, f)
# 出了 with 块，文件自动关闭，不用手动 f.close()
```

### 2.5 `global`：函数里改全局变量

我们的 `applications` 是全局变量。在函数里要**重新赋值**它，必须先用 `global` 声明，否则 Python 会以为你在函数里新建了一个同名局部变量。

```python
def load_data():
    global applications      # 声明：我要改的是外面那个 applications
    applications = ...       # 这样才是改全局的
```

---

## 3. 参考骨架（复制到 main.py 顶部附近，再按第 4 节接线）

```python
import json
import os

DATA_FILE = "applications.json"

def load_data():
    """程序启动时，把文件里的数据读回 applications 列表。"""
    global applications
    if not os.path.exists(DATA_FILE):   # 文件还不存在 → 当作空列表
        applications = []
        return
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        applications = json.load(f)

def save_data():
    """把 applications 列表写回文件。"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(applications, f, ensure_ascii=False, indent=2)
```

两个参数说明：
- `ensure_ascii=False`：中文直接存中文，否则会变成 `\u5b57\u8282` 这种鬼画符。
- `indent=2`：写文件时缩进 2 格，方便你用人眼打开看。

---

## 4. 你的动手任务（按顺序做，每步都运行验证）

1. **贴骨架**：把第 3 节的两段代码加到 `main.py` 里（`import` 放最上面，函数放 `applications = []` 之后）。
2. **启动时加载**：在文件最底部 `if __name__ == "__main__":` 里，`menu()` **之前**加一行 `load_data()`。
3. **改动后保存**：在 `add_application()`、`update_status()`、`delete_application()` 三个函数里，**成功改动的最后一句**（`print("[OK] ...")` 之后）各加一行 `save_data()`。
4. **验证（关键！）**：
   ```powershell
   .venv\Scripts\python.exe cli\main.py
   ```
   添加两条投递 → 退出 → **再运行一次** → 选 2 查看。如果记录还在，你就成功了。
5. **打开看看**：运行后项目根目录会出现 `applications.json`，用记事本打开，确认里面中文正常、有缩进。

---

## 5. 顺手清理 Lesson 1 的小尾巴

改 main.py 时顺便把这 3 处也改了：
- 第 114 行 docstring：「选一条**状态**」→「选一条**投递记录**」
- 第 139 行菜单：「删除**状态**」→「删除**投递**」
- `delete_application()` 的缩进：Tab → 4 个空格

---

## 6. 自测（能口头回答才算过关）

- `json.dump` 和 `json.dumps` 的区别？
- `open()` 的 `"w"` 和 `"a"` 分别什么行为？
- 为什么 `load_data()` 里需要 `global applications`，而 `save_data()` 里不需要？
- `ensure_ascii=False` 是干嘛的？去掉它会怎样？
- 如果我们不在 add/update/delete 里调用 `save_data()`，会发生什么？

---

*做完后把 `main.py` 贴回来（或告诉我卡在哪），我 review。下一课 Lesson 3：把岗位从 CSV 表格导入进来 + 调 DeepSeek 给简历意见——开始出现真正的"AI"能力。*
