# Lesson 4 · 完整状态机 + 岗位筛选（+ 简历结构化预习）

> 目标：让投递记录的状态变化**有规则可依**，给岗位列表加**筛选**能力。
> 前置：Lesson 3 完成（CSV + DeepSeek）。
> 本课三部分：
>   A. 状态机（核心，必做）—— 状态不能乱变
>   B. 岗位筛选（必做）—— 学**列表推导式**
>   C. 简历 Markdown 结构化（选做预习）—— 为未来"AI 改简历"打底

---

## Part A · 状态机（核心）

### 1. 为什么需要状态机？

现在你的 `update_status()` 允许**任意状态改成任意状态**。这会产生脏数据：

```
投递记录：字节 - 后端 [凉凉]   ← 已经凉了
然后用户把它的状态改成 [Offer]   ← ？？凉了还能拿 Offer？
```

现实中状态变化有逻辑约束："已投递"不能直接变"Offer"；"凉凉"是**终态**，不能再动。
**状态机**就是把这些规则写下来，让程序**拒绝**非法迁移。

### 2. 状态机三要素

| 要素 | 含义 | 在本项目里 |
|---|---|---|
| **起点** | 新记录从哪个状态开始 | 新投递 = `已投递` |
| **迁移规则** | 每个状态"能去"哪些状态 | 一张迁移表 |
| **终态** | 到了就不能再变的状态 | `凉凉`、`已接受` |

**推论 1**：既然有起点，`add_application()` 就不该让你随便选状态了——新投递一律是"已投递"。（这解释了为什么 Lesson 1 你加的状态选择要被删掉：状态机不允许"一出生就在终点"。）

**推论 2**：状态选择 UI 不再显示全部状态，只显示"当前状态**允许去**的那些"。

### 3. 迁移表怎么设计（参考代码）

```python
# 状态机迁移表：key = 当前状态，value = 允许迁移到的状态列表
# 值为 [] 表示"终态"，不能再变更
TRANSITIONS = {
    "已投递": ["笔试", "面试", "凉凉"],
    "笔试":   ["面试", "凉凉"],
    "面试":   ["Offer", "凉凉"],
    "Offer":  ["已接受", "凉凉"],
    "凉凉":   [],      # 终态
    "已接受": [],      # 终态
}
```

### 4. 动手任务 A

1. 在 `status_list` 那一行附近加 `TRANSITIONS` 字典。
2. **删掉 `status_list`**——改完你会发现它没人用了，这就是"死代码"，删掉它（学会清理无用代码）。
3. 改 `add_application()`：删掉"请选择状态"那一整段，直接写 `"status": "已投递"`。
4. 重写 `update_status()` 的核心部分（参考下面骨架，自己接线）：

```python
current = applications[index]["status"]        # 当前状态
allowed = TRANSITIONS[current]                 # 从迁移表查"允许去哪些"
if len(allowed) == 0:
    print(f"[!] 当前状态是「{current}」，这是终态，不能变更")
    return

print(f"当前状态：{current}，可以变更为：")
for i, s in enumerate(allowed):
    print(f"{i}. {s}")
# ……然后让用户选序号，把 applications[index]["status"] 改成 allowed[选中的序号]
# ……改完记得 save_data()（老规矩）
```

5. 测试：把"已投递"改成"Offer"应被拒绝（因为 `TRANSITIONS["已投递"]` 里没有 Offer）；改成"凉凉"后再试更新，应提示"终态"。

---

## Part B · 岗位筛选（列表推导式）

### 5. 列表推导式（List Comprehension）

这是 Python 最常用的"快捷写法"。它的作用是：**从现有列表挑出符合条件的，组成新列表**。

```python
# 普通写法
result = []
for j in jobs:
    if j["城市"] == "北京":
        result.append(j)

# 列表推导式（一行搞定，效果完全一样）
result = [j for j in jobs if j["城市"] == "北京"]
```

**读法口诀**：`[j for j in jobs if 条件]` = "**对于 jobs 里的每一个 j，如果条件成立，就把 j 放进新列表**"。
（前半截 `j for j in jobs` 是"取谁"，后半截 `if 条件` 是"什么时候取"。）

### 6. 参考代码

```python
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
```

注意 `keyword in j["岗位"]`：`in` 判断"某串文字**包含在**另一串里"（`"前端" in "前端开发工程师"` → `True`）。这是模糊匹配，和 `==`（完全相等）不同。

### 7. 动手任务 B

1. 加 `filter_jobs()` 函数。
2. 菜单第 5 项改成「筛选岗位」，`choice == "5"` 时调 `filter_jobs()`（替换原来的 `list_jobs()`）。`list_jobs()` 先留着，`ai_advice_flow` 还要用它。
3. 测试：城市输"北京"只剩字节；关键词输"前端"只剩腾讯；两个都回车显示全部。

---

## Part C · 简历 Markdown 结构化（选做，预习）

为未来"AI 改简历"打底：把 `resume.md` 按 `## 标题` 拆成 `{小节名: 内容}`。

```python
def parse_resume_sections(resume_text):
    """把 markdown 简历按 '## ' 标题拆成 小节名 → 内容 的字典。"""
    sections = {}
    current = None
    lines = []
    for line in resume_text.splitlines():     # splitlines：按行拆成列表
        if line.startswith("## "):            # 遇到新标题
            if current is not None:
                sections[current] = "\n".join(lines)   # 把攒的内容存进字典
            current = line[3:].strip()        # 标题名 = 去掉 "## " 和空格
            lines = []
        elif current is not None:
            lines.append(line)                # 普通行，先攒着
    if current is not None:
        sections[current] = "\n".join(lines)  # 最后一个小节别忘了存
    return sections
```

**选做任务 C**：把 `parse_resume_sections()` 作为**一个新的独立函数**，定义在 `read_resume()` 的正下方（它俩职责不同，别合并成一个：`read_resume` 只负责"读文件→返回文本"，`parse_resume_sections` 只负责"把文本→拆成字典"）。然后在 `ai_advice_flow()` 里先调 `read_resume()` 拿到文本，再把文本传给 `parse_resume_sections()`，把结果 `print` 出来看看结构对不对（比如 `{"教育背景": "...", "实习经历": "..."}`）。

---

## 验证清单（做完逐条打勾）

- [ ] 添加投递时不再让你选状态，新记录全是"已投递"
- [ ] 更新时只显示"允许的下一个状态"；终态（凉凉/已接受）提示无法变更
- [ ] "已投递 → Offer"被拒绝；"已投递 → 笔试 → 面试 → Offer → 已接受"能走通
- [ ] 筛选：北京只剩字节；"前端"只剩腾讯；空输入显示全部
- [ ] （选做）简历解析能打印出 `{教育背景: ...}` 这样的字典

## 弄坏再修（必做，感受规则的力量）

1. 把 `TRANSITIONS["面试"]` 改成 `["凉凉"]`（删掉 Offer）→ 运行更新：面试后永远到不了 Offer。体会"迁移表就是铁律"。
2. 把 `TRANSITIONS["凉凉"]` 改成 `["已投递"]` → 凉了的记录居然能"复活"。体会终态的意义。
3. 改完**改回来**，并跑通验证清单里的"能走通"那条。

## 自测题（能口头回答才算过关）

- 状态机解决了什么脏数据问题？举一个具体的坏例子。
- 为什么新投递必须固定"已投递"？
- 终态在迁移表里是怎么表示的？为什么终态不能迁移？
- 列表推导式 `[j for j in jobs if j["城市"] == "北京"]` 用大白话怎么读？
- `in` 和 `==` 在筛选里的区别是什么？
- 为什么改完状态机后，`status_list` 就成了"死代码"？

---

*做完把 `main.py` 贴回来，我 review。下一课 Lesson 5：拆模块 + 用类(class)重构——把越来越大的 main.py 拆开，同时告别 `global`。*
