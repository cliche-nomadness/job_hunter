# Lesson 3 · 从 CSV 导入岗位 + 调 DeepSeek 给简历意见

> 目标：让校招虾第一次"有数据来源"和"有脑子"。
> 前置：已完成 Lesson 2（JSON 持久化）。
> 本课新增两个能力：
>   A. 从 `jobs.csv` 导入可投递岗位（对应未来"在线表格"）
>   B. 调 DeepSeek，针对某个岗位给你的简历提修改意见（对应未来"改简历"）

---

## Part A · 从 CSV 导入岗位

### 1. CSV 是什么

CSV（Comma-Separated Values）就是**用逗号分隔的纯文本表格**。我们项目根目录的 `jobs.csv` 长这样：

```
公司,岗位,城市,JD,链接
字节跳动,后端开发工程师,北京,负责后端服务开发...,https://...
```

第一行是**表头**（列名），后面每行是一条岗位。Python 标准库的 `csv` 模块能直接读它。

### 2. `csv.DictReader`：每行自动变成字典

```python
import csv

with open("jobs.csv", "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)   # 用第一行当"键"
    for row in reader:
        print(row)               # row 是 {"公司": "字节跳动", "岗位": "后端开发工程师", ...}
```

- `DictReader` 用表头当 key，每行变成一个 `dict`，你就能 `row["岗位"]` 这样取值——**和你之前用的 `record["company"]` 一模一样**。
- `encoding="utf-8-sig"`：多了一个 `-sig`，作用是**自动剥掉 Excel 导出 CSV 时偷偷加的 BOM 头**（否则第一列会变成 `\ufeff公司`）。我们文件虽是我用 UTF-8 写的，但加 `-sig` 更稳，兼容 Excel。

### 3. 参考代码（贴到 main.py）

```python
JOBS_FILE = "jobs.csv"
jobs = []          # 全局列表，装岗位，和 applications 并列

def load_jobs():
    """程序启动时，把 jobs.csv 读进 jobs 列表。"""
    global jobs     # 又是"重新赋值"，所以需要 global（回忆 Lesson 2！）
    if not os.path.exists(JOBS_FILE):
        jobs = []
        return
    with open(JOBS_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        jobs = list(reader)      # 把 reader 一次性转成列表

def list_jobs():
    """打印所有岗位。"""
    if len(jobs) == 0:
        print("（没有岗位，请先准备 jobs.csv）")
        return
    for i, job in enumerate(jobs):
        print(f"{i + 1}. [{job['城市']}] {job['公司']} - {job['岗位']}")
```

### 4. 任务步骤（Part A）

1. 顶部加 `import csv`（和已有的 `import json`/`import os` 放一起）。
2. 加 `JOBS_FILE`、`jobs = []`、`load_jobs()`、`list_jobs()`。
3. `if __name__ == "__main__":` 里，`load_data()` 旁边加一行 `load_jobs()`。
4. 菜单加第 5 项「查看岗位」，`choice == "5"` 时调 `list_jobs()`。
5. 运行，选 5，应该能看到 `jobs.csv` 里那 3 条岗位。

---

## Part B · 调 DeepSeek 给简历意见

### 0. 先装 requests（一次性，在你自己的终端执行）

```powershell
.venv\Scripts\python.exe -m pip install requests
# 如果上面很慢或失败，换清华镜像：
.venv\Scripts\python.exe -m pip install requests -i https://pypi.tuna.tsinghua.edu.cn/simple
```

装完验证（能打印版本号即成功）：

```powershell
.venv\Scripts\python.exe -c "import requests; print(requests.__version__)"
```

### 1. 什么是"调 API"（用点外卖类比）

你的程序想要 DeepSeek 帮它"想"，就得**发一个 HTTP 请求**给 DeepSeek 的服务器，就像点外卖：

| 外卖 | HTTP 请求 |
|---|---|
| 餐厅地址 | `url`（`https://api.deepseek.com/chat/completions`） |
| 你的会员卡/凭证 | `headers` 里的 `Authorization: Bearer <你的key>` |
| 你点的菜 | `body`（JSON：用哪个模型、发什么消息） |
| 送来的餐 | 响应（JSON：AI 的回答） |

`requests` 库就是帮你"下单"的工具：`requests.post(url, headers=..., json=...)`。

### 2. API key 是什么、怎么拿

- `API key` 是 DeepSeek 发给你的**一串密钥**，证明"这个请求是你发的"，按用量收费。
- 获取：去 <https://platform.deepseek.com> 注册 → 充值一点点（几块钱够用很久）→ 创建 API key → 复制。
- **千万别把 key 写进代码或提交到 git**。我们存进环境变量：

```powershell
# 只在当前终端窗口生效（关闭窗口就失效，适合测试）
$env:DEEPSEEK_API_KEY = "sk-你的key"
```

（以后我们会学用 `.env` 文件更优雅地管理，现在先用环境变量。）

### 3. 参考代码（贴到 main.py）

```python
import requests

RESUME_FILE = "resume.md"

def read_resume():
    """读简历文件，返回文本。"""
    if not os.path.exists(RESUME_FILE):
        print("[!] 没有 resume.md")
        return ""
    with open(RESUME_FILE, "r", encoding="utf-8") as f:
        return f.read()

def get_resume_advice(job_title, jd, resume_text):
    """调 DeepSeek，针对岗位给简历修改意见，返回 AI 的回复文本。"""
    api_key = os.environ.get("DEEPSEEK_API_KEY")   # 从环境变量取 key
    if not api_key:
        print("[!] 未设置 DEEPSEEK_API_KEY，先在终端执行 $env:DEEPSEEK_API_KEY=...")
        return ""

    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    prompt = (
        f"岗位：{job_title}\n"
        f"岗位要求(JD)：{jd}\n\n"
        f"我的简历：\n{resume_text}\n\n"
        "请针对这个岗位，指出我简历的差距，并分点给出具体修改建议。"
    )
    body = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是专业的校招简历顾问。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.5,
    }

    resp = requests.post(url, headers=headers, json=body, timeout=60)
    resp.raise_for_status()                     # 状态码不是 2xx 就抛异常
    data = resp.json()                          # 把返回的 JSON 转成 dict
    return data["choices"][0]["message"]["content"]   # 取出 AI 的回复文字

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
    print("\nAI 正在分析，请稍候...\n")
    advice = get_resume_advice(job["岗位"], job["JD"], resume_text)
    if advice:
        print("===== AI 修改意见 =====")
        print(advice)
```

### 4. 任务步骤（Part B）

1. 顶部加 `import requests`。
2. 贴 `RESUME_FILE`、`read_resume()`、`get_resume_advice()`、`ai_advice_flow()`。
3. 菜单加第 6 项「AI 简历意见」，`choice == "6"` 时调 `ai_advice_flow()`。
4. 把「退出」改成第 7 项，`choice == "7"` 时 `break`，提示语改成「请选择（1-7）」。
5. 终端里先设置 key，再运行：
   ```powershell
   $env:DEEPSEEK_API_KEY = "sk-你的key"
   .venv\Scripts\python.exe cli\main.py
   ```
   选 6 → 选岗位 1（字节后端）→ 看 AI 的回复。

---

## 验证清单（做完逐条打勾）

- [ ] 选 5「查看岗位」能列出 3 条岗位
- [ ] 选 6「AI 简历意见」→ 选岗位 → 打印出一段 AI 意见
- [ ] 不设 key 时，选 6 会友好提示"未设置 DEEPSEEK_API_KEY"而不是崩溃
- [ ] 退出选项序号已改成 7，且菜单里各项序号正确

---

## 自测（能口头回答才算过关）

- `csv.DictReader` 帮我们做了什么？和手动 `split(",")` 比好在哪？
- `encoding="utf-8-sig"` 的 `-sig` 是干嘛的？
- 一次 API 调用 = 哪几部分？（URL / headers / body 分别是什么角色）
- `Authorization: Bearer <key>` 是什么意思？
- 为什么 key 不能写进代码？
- `resp.json()` 和 Lesson 2 里的 `json.load(f)` 有什么异同？

---

*做完把 `main.py` 贴回来，我 review。下一课 Lesson 4：把状态机做完整（投递→笔试→面试→Offer 的合法迁移）+ 用 Markdown 结构化管理简历——离真正的校招虾越来越近。*
