# Lesson 13 · 部署落地（7×24 常驻）+ 每日自动同步 ★ 功能级落地

> 目标：校招虾从"你电脑开着、手动跑 run_bot.cmd 才活"变成**永远在线**——开机自启、崩溃自启、断电恢复，并且**每天自动抓岗位/JD 更新 jobs.csv**。
> 前置：L12 完成（`job_provider_moka.py` + `update_jobs_csv.py` 跑通——本课直接复用它们）。
> 说明：本课分两阶段——**阶段 1 本地自动化（必做，零成本）**：`.env` 密钥 + 开机自启 + 定时同步；**阶段 2 上云（可选）**：Linux + systemd + cron。先跑通阶段 1 再考虑上云。
> ⚠️ 前置检查：L12 的"新 JD 喂给优化简历"验证如果还没做完，先补上再开始本课。

---

## 0. 本课要解决的问题

```
现在：你手动开窗口 → set 环境变量 → python bot.py → 窗口一关/电脑一关，机器人就死了
目标：开机自动起、崩溃自动重启、断电恢复后自动拉起、每天自动同步岗位，连续一周不用管
```

**为什么这课是"功能级落地"的分水岭**：机器人 24 小时活着，才算一个"服务"；每天自动同步岗位，才算一个"agent"（而不是一个"你手动喂数据的工具"）。

**好消息（长连接模式的红利）**：你的 bot 用的是**长连接**（主动连飞书 WebSocket），**不需要公网 URL**——所以部署**不需要域名、不需要反向代理、不需要 HTTPS**。大纲里"若回退 webhook 模式"那条对你**不适用**，跳过。

---

## Part A · 部署决策：你的选项

### A1. 为什么必须 7×24

"电脑关机 = 机器人下线"听起来像废话，但这是落地与否的分界线。面试官问"你的项目怎么保证可用性"，答案就是本课内容：**自启 + 守护 + 恢复**。

### A2. 三个选项对比

| 选项 | 成本 | 优点 | 缺点 |
|---|---|---|---|
| **常开电脑**（家里旧电脑/笔记本不关机）| 免费 | 环境现成（Windows 已全跑通）| 电费、Windows 自动更新会重启、断电 |
| **云服务器**（阿里云/腾讯云轻量服务器）| ~30–60 元/月 | 7×24 稳定、独立环境、简历加分 | 花钱、要接触 Linux 命令行 |
| 树莓派等小主机 | 硬件成本 | 低功耗 | 环境折腾，零基础不推荐 |

### A3. 推荐路径（本课就按这个顺序）

```
阶段 1（必做，Part B–D）：本地自动化——.env + 开机自启 + 每日定时同步
   ↓ 跑通一周再说
阶段 2（可选，Part E）：上云——买轻量服务器 → Linux 环境 → systemd + cron
```

**理由**：阶段 1 零成本、复用你已跑通的 Windows 环境，先解决"关机就死"和"手动喂数据"两个痛点；上云是锦上添花（且是 L14 工程化之前的事）。

### A4. 长连接为什么免公网（一句话）

你的 bot 是**主动拨号**（连飞书的 WebSocket 服务器），飞书有事**顺着这条连接推给你**——就像你主动给朋友打电话并保持通话，朋友找你不需要知道你家地址。Webhook 模式才需要公网地址（朋友要上门找你）。

---

## Part B · 密钥管理：.env 文件（脱离 run_bot.cmd）

### B1. 现在的问题

你的 `run_bot.cmd` 长这样（注意：**密钥明文躺在文件里**）：

```bat
set FEISHU_APP_ID=cli_xxx
set FEISHU_APP_SECRET=xxx
set DEEPSEEK_API_KEY=sk-xxx
..\.venv\Scripts\python.exe bot.py
```

问题：① 密钥明文（以后 git 提交就泄密）② 每次启动手动 set ③ 部署到服务器时这套 cmd 没用。

### B2. 标准做法：`.env` 文件

在项目根目录（`D:\job_hunter\`）新建 `.env`：

```
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_VERIFICATION_TOKEN=xxx
DEEPSEEK_API_KEY=sk-xxx
```

（内容照抄 run_bot.cmd 里的 set 值，去掉 `set ` 前缀）

### B3. 让代码读 .env（两行改动）

先装库（你终端）：`..\.venv\Scripts\python.exe -m pip install python-dotenv -i https://pypi.tuna.tsinghua.edu.cn/simple`

改 `cli/bot.py`——**注意位置，这是本课第一个"为什么"**：

```python
import os
from dotenv import load_dotenv

load_dotenv()          # ① 必须先执行：把 .env 的内容塞进环境变量

import server          # ② 之后才能 import：server.py 模块级代码要读环境变量
```

**为什么 `load_dotenv()` 必须在 `import server` 之前**：`server.py` 一被 import，它的**模块级代码立刻执行**（`FEISHU_APP_ID = os.environ.get(...)` 就在第 15 行）。如果那时环境变量还没从 .env 加载，拿到的就是空字符串。所以"先加载环境变量，再 import 依赖它的模块"——顺序就是生命线。

> 面试点：**环境变量的加载时机**——入口文件的顶部、任何读取它的模块被 import 之前。

### B4. 验证

删掉 `run_bot.cmd` 里的 set 行（或直接只留启动命令），跑 `..\.venv\Scripts\python.exe bot.py`，能正常连上飞书 = `.env` 生效。

> 安全提醒：`.env` 里有真实密钥，**永远不要把它发到网上/贴到 GitHub**。以后 git init 时第一件事就是建 `.gitignore` 写上 `.env`（L14 会做）。

---

## Part C · 开机自启 + 崩溃自启（Windows，阶段 1 核心）

### C1. 问题

现在 bot 靠"开窗口手动跑"，窗口一关就死。要让它**开机自己起来**、**死了自己重启**。

### C2. 最小方案：任务计划程序（Windows 自带，不用装东西）

**第一步**：建一个"无窗口"的启动脚本 `cli\start_bot.cmd`（没有 `pause`，跑完不占窗口焦点；用 `start /b` 让它后台跑也行，先用最简版）：

```bat
@echo off
cd /d D:\job_hunter\cli
..\.venv\Scripts\python.exe bot.py
```

**第二步**：Win+R 输入 `taskschd.msc` 打开"任务计划程序"→ 右侧"创建任务"：

| 选项卡 | 设置 |
|---|---|
| 常规 | 名称 `XiaZhaoXiaBot`；勾选"不管用户是否登录都要运行"（可选）|
| 触发器 | 新建 → "登录时"（或"启动时"）|
| 操作 | 新建 → 启动程序 → `D:\job_hunter\cli\start_bot.cmd` |
| 设置 | **勾选"如果任务失败，重新启动"**（间隔 1 分钟，最多 3 次）——这就是"崩溃自启" |

**第三步**：右键任务 → 运行，验证 bot 起来；然后**重启电脑**，登录后等几秒，看 bot 是否自动连上（发条消息测试）。

> 命令行版（等价操作，以后在服务器/脚本里会用）：
> ```
> schtasks /create /tn "XiaZhaoXiaBot" /tr "D:\job_hunter\cli\start_bot.cmd" /sc onlogon
> ```

### C3. 断电恢复

"启动时"触发器（上表可选）解决断电恢复：电脑来电开机后，任务自动拉起 bot。**"登录时"需要你登录 Windows 才触发**——家用电脑开机就自动登录的话两者都行，云服务器（Linux）用 systemd 就没有这个问题（Part E）。

---

## Part D · 每日自动同步岗位/JD（把 L12 变成定时任务）★

### D1. 目标

L12 是手动三步：抓列表 → 抓 JD → 合并 csv。本课把它变成**每天定时自动跑**：

```
每天 9:00（或你定的时间）
   ↓
sync_jobs.py：读站点清单 → 逐站抓列表 → 逐岗位抓 JD → 合并进 jobs.csv → 写日志
   ↓
你打开「岗位」/「优化简历」看到的就是最新 JD
```

### D2. 先自己想（拆需求模板，别急着看代码）

```
① 输入：站点清单文件（公司名 + 列表 URL）；输出：更新后的 jobs.csv + 日志文件
② 步骤：读清单 → 对每个站点：抓列表 → 对每个岗位抓 JD → 合并（更新/新增）→ 写日志
③ 边界：某岗位抓 JD 失败（不能中断整个同步）；没 JD 的岗位（跳过）；清单文件格式错（跳过该行）
④ 拆函数：读/写 csv（复用 L12 的）、抓列表+抓JD（复用 job_provider_moka 的）、写日志
```

**先自己写一遍，写不出来再看下面的参考答案**——这是 L13 最重要的练习（你在 L12 说过"自己写就浆糊"，现在正好治）。

### D3. 参考答案：`cli/sync_jobs.py`（完整代码在文末附录，先看设计）

```python
# cli/sync_jobs.py —— 每日自动同步岗位/JD → jobs.csv + 日志
# 站点清单 cli/sites.txt（每行：公司名,岗位列表URL，# 开头是注释）：
#   远景,https://app.mokahr.com/campus_apply/envisiongroup/43123#/jobs
# 用法：
#   ..\.venv\Scripts\python.exe sync_jobs.py            # 同步所有站点
#   ..\.venv\Scripts\python.exe sync_jobs.py --limit 3  # 调试：每站只抓前3个岗位的JD
```

核心逻辑就三个函数（其余是 IO）：

```python
def load_sites():      # 读 sites.txt → [(公司名, URL)]（空行/注释跳过）
def sync_site(company, url, limit):
    jobs = scrape_job_list(url)            # 复用 L12：抓列表
    for i, j in enumerate(jobs[:limit]):
        time.sleep(2)                       # 请求间停顿，防限流
        j["jd"] = scrape_job_detail(...)    # 复用 L12：抓 JD（失败 try/except 不中断）
        log(...)
    return jobs
def upsert(rows, company, title, jd, url): # 复用 L12 逻辑：匹配更新 / 新增
```

**注意两个设计点**：
1. **单个岗位失败不能中断整个同步**——`try/except` 包住抓 JD，失败就 log 一行继续（否则 35 个岗位有一个超时，全白跑）；
2. **`--limit` 参数**——调试时只抓前 3 个，验证流程通了再全量（先小后大）。

### D4. 定时触发（Windows 任务计划程序，和 Part C 同款操作）

| 项 | 设置 |
|---|---|
| 触发器 | 新建 → "按预定计划" → 每天 09:00 |
| 操作 | 启动程序 → `D:\job_hunter\cli\sync_jobs.cmd`（内容：`cd /d D:\job_hunter\cli` + `..\.venv\Scripts\python.exe sync_jobs.py >> D:\job_hunter\logs\sync.log 2>&1`）|

> `>> logs\sync.log 2>&1` = 把输出**追加**到日志文件（标准输出 + 错误都写进去），这样第二天能查"昨晚跑了吗、成功没"。

### D5. 验证

1. 先**手动**跑一次 `sync_jobs.py --limit 3` → 看 jobs.csv 新增/更新行、logs\sync.log 有记录；
2. 把定时任务设成"每 2 分钟"临时测试（触发器改为重复间隔）→ 看日志时间戳确认真的自动跑了 → 再改回每天 9:00。

**铁律：定时任务之前，先手动跑通 N 次。** 定时器只是"到点执行同一个命令"，命令本身必须先可靠。

---

## Part E · 上云（可选）：Linux + systemd + cron

> 做这一步你需要：一个云服务器（阿里云/腾讯云轻量，选 Ubuntu）、会 SSH 登录、把代码传上去（`git clone` 或 scp）。对零基础有门槛，**本课标为选做**，但代码示例先给你，将来照抄。

### E1. 环境差异（最容易踩的坑）

| | Windows（现在） | Linux 服务器 |
|---|---|---|
| Playwright 浏览器 | `channel="msedge"` 用系统 Edge | **没有系统 Edge** → `playwright install --with-deps chromium` 装 Chromium + 系统依赖 |
| 密钥 | `.env`（Part B 已做）| 同一个 `.env`，但用 `EnvironmentFile=` 喂给 systemd |
| 自启/守护 | 任务计划程序 | **systemd**（`Restart=always`）|
| 定时 | 任务计划程序 | **cron** |

**所以上云第一步不是部署，是"让 L12 的脚本在 Linux 上能跑"**：`pip install playwright` + `playwright install --with-deps chromium`，然后 `job_provider_moka.py` 里把 `channel="msedge"` 改成**不传 channel**（默认 Chromium）——一行代码的环境适配。

### E2. systemd 服务（开机自启 + 崩溃自启 + 断电恢复，一条龙）

`/etc/systemd/system/xiazhauxia.service`：

```ini
[Unit]
Description=XiaZhaoXia Bot
After=network.target

[Service]
WorkingDirectory=/opt/xiazhauxia
EnvironmentFile=/opt/xiazhauxia/.env
ExecStart=/opt/xiazhauxia/.venv/bin/python /opt/xiazhauxia/cli/bot.py
Restart=always          # ← 崩溃/断电后永远自动重启
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable xiazhauxia   # 开机自启
sudo systemctl start xiazhauxia
sudo systemctl status xiazhauxia   # 看运行状态
```

**一句话**：`Restart=always` = Windows"任务失败重新启动"的 Linux 版，而且是**主动的**——进程死了 5 秒内拉起来，不需要等"任务失败"判定。

### E3. cron 定时同步

```bash
crontab -e
# 每天 9:00 跑同步，输出追加到日志
0 9 * * * cd /opt/xiazhauxia/cli && /opt/xiazhauxia/.venv/bin/python sync_jobs.py >> /opt/xiazhauxia/logs/sync.log 2>&1
```

`0 9 * * *` = 分 时 日 月 周 = "每天 9 点"。**每个定时任务都要写日志**——服务器上看不到屏幕，日志就是你唯一的眼睛。

### E4. Docker（大纲列为内容，但对零基础排到"之后再说"）

原理一句话：Docker 把"Python 环境 + 代码 + 依赖"打包成镜像，任何机器一条命令跑起来。**但你要先会 systemd 那套再上 Docker**（Docker 内部还是靠 systemd 管），而且 Docker Desktop 在 Windows 上要先装 WSL2。**本课不做，L14 工程化时再评估。**

---

## Part F · 自动进度同步（展望，本课不做）

架构里的 `ProgressSyncGraph`（登录态抓"我的投递"→ LLM 整理 → 更新状态机 → 推送变更）**需要保持登录态**（cookie 会话），复杂度高、站点反爬风险大。本课只把它的**基础设施**（7×24 常驻 + 定时 + 日志）建好，登录态抓取留到后续课。**知道它存在即可。**

---

## 验证清单（做完逐条打勾）

- [ ] `.env` 生效：删掉 run_bot.cmd 的 set 行，bot.py 仍能连上飞书
- [ ] 任务计划程序：登录自动起 bot；重启电脑后发消息 bot 有响应
- [ ] 杀掉 bot 进程（任务管理器结束 python）→ 计划任务把它拉起来（若配置了失败重启）
- [ ] `sync_jobs.py --limit 3` 手动跑通：jobs.csv 更新 + logs\sync.log 有记录
- [ ] 定时任务临时设"每 2 分钟" → 日志出现多次时间戳 → 改回每天 9:00
- [ ] （选做）上云：systemd `Restart=always` + 服务器重启后 bot 自动回来

## 弄坏再修（必做）

1. `.env` 里把 `FEISHU_APP_SECRET` 故意写错 → bot 连不上/报错 → 改回来，理解"密钥从 .env 来，不在代码里"；
2. `sync_jobs.py` 里故意让一个岗位 URL 超时（如把 URL 改错）→ 观察"该岗位失败但同步继续"，理解 try/except 的价值；
3. 任务计划程序**不勾**"如果任务失败重新启动" → 杀掉 bot 看它不回来 → 勾上再看它回来，理解"守护"是配置出来的不是默认的；
4. （选做）systemd 里把 `Restart=always` 删掉 → 杀进程后不重启 → 加回来，同理。

## 自测题（能口头回答才算过关）

- 为什么 `load_dotenv()` 必须在 `import server` **之前**？
- 长连接模式为什么不需要域名/反代/HTTPS？（对比 webhook 模式）
- systemd 的 `Restart=always` 对应 Windows 任务计划程序的什么设置？
- 为什么同步脚本里"单个岗位失败"不能中断整个同步？
- 为什么"定时任务之前必须先手动跑通"？定时器只是什么？
- 为什么每个定时任务都要写日志？（服务器上"眼睛"是什么？）
- Linux 上 Playwright 的 `channel="msedge"` 为什么不行？要做什么？

---

*做完把 `.env`（值打码）、`start_bot.cmd`、`sync_jobs.py`、一段 `logs\sync.log` 贴回来，我 review。下一课 L14：工程化 + 求职补强——pytest 测试、git + GitHub、数据库（把 jobs.csv/JSON 换成 PostgreSQL），把简历的最后一格补上。*

---

## 附录：`cli/sync_jobs.py` 完整参考代码

```python
# cli/sync_jobs.py —— 每日自动同步：抓列表 → 抓全部JD → 合并进 jobs.csv → 写日志
#
# 站点清单 cli/sites.txt（每行：公司名,岗位列表URL；# 开头是注释）：
#   远景,https://app.mokahr.com/campus_apply/envisiongroup/43123#/jobs
#
# 用法：
#   ..\.venv\Scripts\python.exe sync_jobs.py            # 同步所有站点
#   ..\.venv\Scripts\python.exe sync_jobs.py --limit 3  # 调试：每站只抓前 3 个岗位的 JD
import sys
import csv
import json
import time
from pathlib import Path
from datetime import datetime

from job_provider_moka import scrape_job_list, scrape_job_detail

BASE_DIR = Path(__file__).resolve().parent.parent
CLI_DIR = Path(__file__).resolve().parent
SITES_FILE = CLI_DIR / "sites.txt"
JOBS_FILE = BASE_DIR / "jobs.csv"
LOG_FILE = BASE_DIR / "logs" / "sync.log"


def log(msg):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    LOG_FILE.parent.mkdir(exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_sites():
    """读站点清单 → [(公司名, URL)]；空行和 # 注释跳过。"""
    sites = []
    for line in SITES_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(",", 1)
        if len(parts) == 2:
            sites.append((parts[0].strip(), parts[1].strip()))
        else:
            log(f"⚠️ 清单行格式错误，跳过: {line}")
    return sites


def load_jobs_csv():
    with open(JOBS_FILE, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def save_jobs_csv(rows):
    fieldnames = ["公司", "岗位", "城市", "JD", "链接"]
    with open(JOBS_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def detail_url(job):
    detail = job.get("detail", "")
    if detail.startswith("http"):
        return detail
    base = job.get("base", "")
    return base + detail if detail.startswith("#") else base.rstrip("/") + detail


def upsert(rows, company, title, jd, url):
    """匹配更新；没匹配到就新增（公司名来自站点清单）。"""
    for row in rows:
        if title == row["岗位"]:
            row["JD"] = jd
            row["链接"] = url
            return "更新"
    rows.append({"公司": company, "岗位": title, "城市": "", "JD": jd, "链接": url})
    return "新增"


def sync_site(company, url, limit=None):
    """同步一个站点：抓列表 → 逐个抓 JD。单个失败不中断。"""
    log(f"开始同步 {company}: {url}")
    jobs = scrape_job_list(url)
    log(f"  抓到 {len(jobs)} 个岗位，开始抓 JD...")
    for i, j in enumerate(jobs):
        if limit and i >= limit:
            log(f"  --limit {limit}，停止")
            break
        try:
            time.sleep(2)                                  # 请求间停顿，防限流
            jd = scrape_job_detail(j["base"], j["detail"])
            j["jd"] = jd
            log(f"  [{i+1}/{len(jobs)}] {j['title']} JD {len(jd)} 字")
        except Exception as e:
            log(f"  [{i+1}/{len(jobs)}] {j['title']} 抓取失败: {e}")   # 不中断
    return jobs


def main():
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    rows = load_jobs_csv()
    for company, url in load_sites():
        jobs = sync_site(company, url, limit)
        for j in jobs:
            if not j.get("jd"):
                continue                                   # 没抓到的跳过
            action = upsert(rows, company, j["title"], j["jd"], detail_url(j))
            log(f"  {action}: {j['title']}")
    save_jobs_csv(rows)
    log(f"同步完成，jobs.csv 现有 {len(rows)} 行")


if __name__ == "__main__":
    main()
```
