# Lesson 14 · 工程化 + 求职补强 ★ 工程级落地 + 简历就绪

> 目标：可靠性（版本控制 / 测试 / 数据库）+ 简历就绪（GitHub 作品 + 简历 bullet + 面试故事），两件事一起做。
> 前置：L12/L13 完成（`.env` 已就绪；L13 的部署验证可**与本课并行**——git/pytest 都是本地工作，互不冲突）。
> 顺序逻辑：**先保护代码（git）→ 再保护质量（pytest）→ 再升级数据层（PostgreSQL）→ Redis（YAGNI 讨论）→ 选做 → 简历收口**。
> 本课产出：GitHub 仓库（可克隆）+ `tests/` 全绿 + PostgreSQL 数据迁移 + 可写进简历的项目描述。

---

## 0. 本课要解决的问题（三个"裸奔"）

```
代码裸奔：没有版本控制 —— 改坏了无法回滚，历史丢失，出事只能靠手动备份
质量裸奔：没有测试     —— 改一行代码，不知道崩了哪里（你已被 server.py 覆盖事件教育过一次）
简历裸奔：没有 GitHub  —— 面试官无法验证你做过什么；JD 上的 pytest/git 是硬缺口
```

**为什么 git 放第一**：它是后面一切的保护网（测试改坏可回滚、重构敢下手），且 GitHub 链接是简历硬通货——**越早 init 越好，历史本身就是作品**。

---

## Part A · git + GitHub（★ 先做）

### A1. `.gitignore` 决策表（哪些进、哪些绝不进）

**我已经帮你把 `.gitignore` 建好了**（原来只有 2 行，现在完整版）：

| 类别 | 内容 | 为什么 |
|---|---|---|
| 🔑 密钥 | `.env` / `keys/` / `plugins/` | **进 git = 密钥公开 = 任何人能冒用你的飞书应用/刷你的 DeepSeek 余额** |
| 运行产物 | `logs/` `__pycache__/` `*.pyc` | 可再生，不属于源代码 |
| 个人数据 | `resume*.md` `applications.json` `jobs.csv` `jobs_out.json` | 简历/投递记录是**隐私**；公开的是代码，不是你的求职数据 |
| 环境 | `.venv/` | 可重建（requirements.txt 负责）|

> **核心原则：代码公开，密钥和隐私数据绝不公开。** 数据文件被忽略后，换机器克隆会缺数据——正式做法是提交一个 `jobs.sample.csv` 样例（两行假数据），README 说明"复制改名即可用"。

### A2. 初始化五步（你终端，项目根 `D:\job_hunter`）

```bat
git init
git add .gitignore README.md        # 先单独提交保护网（体现意识）
git commit -m "chore: 添加 .gitignore，隔离密钥与个人数据"
git add .
git commit -m "feat: 校招虾 v0.4——飞书机器人+LangGraph简历优化+Playwright岗位采集"
git log --oneline                   # 看提交历史
```

> 如果 `git add .` 后想检查有什么不该进：`git status` 逐个看——**提交前 30 秒的检查，胜过事后泄密的补救**。

### A3. GitHub 上仓

1. GitHub 建空仓库（先 **Private**，README 完整后再转 Public）；
2. `git remote add origin https://github.com/你的用户名/xiaozhaoxia.git`
3. `git branch -M main` + `git push -u origin main`

### A4. 公开前的安全自查（三步，养成习惯）

```bat
findstr /s /i "sk- cli_ APP_SECRET" cli\*.py *.cmd *.md     # 源码里扫密钥痕迹
git log --all --full-history -- "*.env"                      # 历史里查敏感文件
type .gitignore | findstr ".env"                             # 确认保护仍在
```

> ⚠️ **git 的特殊性**：一旦 commit 过密钥，即使下个版本删掉，**历史里仍然在**（得改写历史才干净）。所以防线前置：`.gitignore` 必须在**第一个 commit 之前**就位（A2 就是这个顺序）。

### A5. 日常习惯（两条就够）

1. **小步提交**：一个功能/一次修复 = 一个 commit（不要攒一周一次性提）；
2. **message 写"为什么"**：`fix: 卡片回调去重，避免飞书重投导致重复确认` 比 `修改代码` 有价值一万倍——面试官会看你的 commit 历史。

### A6. README 重写（现有的已过时——还写着"代码尚未开始"）

骨架模板（内容你填，这是你的作品门面）：

```markdown
# 校招虾 · 接入飞书的个人校招求职助手
一句话：跟踪投递进度 · 每日自动抓取岗位 · AI 按岗位改写简历

## 架构一览（配一张图：飞书 ↔ bot ↔ LangGraph ↔ DeepSeek / Playwright ↔ 招聘官网）
## 功能演示（2-3 张聊天截图）
## 快速开始（clone → pip install -r requirements.txt → 复制 .env.example 填密钥 → run_bot.cmd）
## 技术亮点（3-4 条：长连接卡片回调+幂等去重 / LangGraph interrupt 人工确认 / Playwright 双适配器 / 定时同步+日志兜底）
```

> 顺手做：建 `requirements.txt`（`pip freeze > requirements.txt`）和 `.env.example`（键名保留、值留空）——别人克隆后能照着跑，是开源作品的基本礼仪。

---

## Part B · pytest 单元测试（★ 真缺口）

> ⚠️ **进度决策（2026-08-31）**：本部分**跳过，记为欠账**（同 PDF 从 L11 延后 L14 的处理方式）。`tests/` 参考实现保留在仓库，README 不声称有测试。以后补做时从 B5 的两条命令开始即可。

### B1. 先测什么：纯逻辑（bug 温床 + 零环境依赖）

| 模块 | 为什么值得测 |
|---|---|
| `TRANSITIONS` 状态机 | 业务规则的"宪法"：非法迁移/终态必须被挡住 |
| `ApplicationBook` | 数据入口：add/update/delete 的边界（越界、非法状态）|
| `extract_jd`（L12）| 正则切分容易过切/漏切 |
| `upsert` / `detail_url` / `load_sites`（L13）| 合并策略与 URL 拼接是纯函数 |

**不优先测**：`send_text`（要走网络）、`cmd_*`（依赖 bot 上下文）——那是集成测试的事，先不碰（YAGNI）。

### B2. 最小概念（会这四个就够开工）

```python
def test_名字():        # test_ 开头，pytest 自动发现
    assert 结果 == 期望  # 断言失败 = 测试红
```
- 运行：`pytest tests\ -v`（-v 显示每个用例名）；
- **tmp_path**（pytest 内置夹具）：每个测试拿到一个临时目录——测文件读写**不会污染你的真实数据**；
- 失败输出从下往上读：最后一行是断言差异，上面是调用栈。

### B3. 用"拆需求模板③边界"推用例（测试设计 = 边界清单）

| 模块 | 边界 | 用例 |
|---|---|---|
| TRANSITIONS | 迁移目标都是合法状态？终态无出边？ | 3 条结构性断言 |
| ApplicationBook.add | 新记录初始状态？落盘了吗？ | 正常 + **重开文件数据还在**（持久化）|
| update_status | 非法迁移？终态再变？ | 拒绝后**状态保持不变** |
| delete | 删对条目？ | 删 [0] 后剩的是原来的第 2 条 |
| extract_jd | 正常切分/找不到关键词 | 页脚被切掉 / 兜底返回 |
| upsert | 已存在→更新？不存在→新增？ | 返回值 + 行内容双断言 |

### B4. 参考实现（已建好：`tests/conftest.py` + `tests/test_core.py`，全部验证通过）

`tests/conftest.py`（让 pytest 找到 `cli/` 里的模块）：

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cli"))
```

`tests/test_core.py` 精选片段（完整见文件）：

```python
from application_book import ApplicationBook, TRANSITIONS
from job_provider_moka import extract_jd
from sync_jobs import upsert, detail_url


def test_terminal_states_have_no_exits():
    for s in ("已接受", "已拒绝", "凉凉"):
        assert TRANSITIONS[s] == []

def test_update_illegal_transition_rejected(tmp_path):
    book = ApplicationBook(str(tmp_path / "a.json"))
    book.add("字节", "后端")
    book.update_status(0, "Offer")            # 已投递 → Offer 非法
    assert book.applications[0]["status"] == "已投递"   # 状态没被改

def test_data_persists_across_reload(tmp_path):
    book = ApplicationBook(str(tmp_path / "a.json"))
    book.add("字节", "后端")
    book2 = ApplicationBook(str(tmp_path / "a.json"))   # 重新打开
    assert book2.applications[0]["company"] == "字节"
```

### B5. 安装 + 运行

```bat
..\.venv\Scripts\python.exe -m pip install pytest -i https://pypi.tuna.tsinghua.edu.cn/simple
..\.venv\Scripts\python.exe -m pytest tests\ -v
```

**验收：全绿。** 然后做"弄坏再修"第 1 条（把 TRANSITIONS 改坏一条，看测试抓出来）——你会第一次直观感受到"测试在保护你"。

---

## Part C · PostgreSQL（数据层升级——L5 设计在这里兑现）

### C1. 先诚实回答：你现在需要吗？

- **单用户 + 单进程 + 小数据**：JSON 文件其实够用（YAGNI）；
- 但**为什么还是要做**：① JD 高频要求 ② `ApplicationBook` 当初封装成类就是为了这一天——**接口不变、底层可换**，现在验证这个设计 ③ 为"多用户/多进程"铺路。
- 本课范围：迁移 `applications`（投递记录）；`jobs.csv` 进库作选做。

### C2. 安装（Windows）

1. 官网下载 PostgreSQL 安装器（EDB），一路下一步，记住你设的密码；
2. 自带的 pgAdmin（图形界面）建库：`CREATE DATABASE xiaozhaoxia;`
3. 装驱动：`..\.venv\Scripts\python.exe -m pip install psycopg2-binary -i https://pypi.tuna.tsinghua.edu.cn/simple`

### C3. 表设计 + 建表

```sql
CREATE TABLE IF NOT EXISTS applications (
    id         SERIAL PRIMARY KEY,
    company    TEXT NOT NULL,
    position   TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT '已投递',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

> 对比 JSON：每行有了**主键**（不用再靠列表下标定位）、**时间戳**（什么时候投的终于有记录了）、**事务**（写一半断电不会坏文件）。

### C4. `ApplicationBook` 换后端——接口不变，只换底层

L5 把数据和操作封装进类，就是为了今天。新建 `cli/book_pg.py`，**方法签名和 JSON 版完全一致**：

```python
# cli/book_pg.py —— ApplicationBook 的 PostgreSQL 版（同接口，可无缝替换）
import psycopg2
from application_book import TRANSITIONS

class PgApplicationBook:
    def __init__(self, dsn):                    # dsn 例: "dbname=xiaozhaoxia user=postgres password=*** host=localhost"
        self.conn = psycopg2.connect(dsn)

    def add(self, company, position):
        with self.conn, self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO applications (company, position) VALUES (%s, %s)",
                (company, position))

    def all(self):
        with self.conn.cursor() as cur:
            cur.execute("SELECT company, position, status FROM applications ORDER BY id")
            return [{"company": c, "position": p, "status": s}
                    for c, p, s in cur.fetchall()]

    def update_status(self, index, new_status):
        rows = self.all()
        current = rows[index]["status"]
        if new_status not in TRANSITIONS.get(current, []):
            print(f"[!] 不能从「{current}」变成「{new_status}」")
            return
        with self.conn, self.conn.cursor() as cur:
            cur.execute(
                "UPDATE applications SET status=%s, updated_at=now() WHERE id="
                "(SELECT id FROM applications ORDER BY id OFFSET %s LIMIT 1)",
                (new_status, index))

    def delete(self, index):
        with self.conn, self.conn.cursor() as cur:
            cur.execute(
                "DELETE FROM applications WHERE id="
                "(SELECT id FROM applications ORDER BY id OFFSET %s LIMIT 1)", (index,))
```

**切换成本**：`server.py` 里 `book = ApplicationBook(...)` 一行换成 `book = PgApplicationBook(dsn)`——调用方（cmd_add/cmd_progress/...）**一行都不用改**。这就是封装的红利。

> 注意：`PgApplicationBook` 没有 `.applications` 列表属性（server.py 的 cmd_progress 用了它）——把 `book.applications` 换成 `book.all()` 即可，正好借此复习"接口设计"：**列表属性是 JSON 版的实现细节，不该泄到调用方**。

### C5. 迁移脚本 + 行数对账（验收标准：迁移无丢失）

```python
# cli/migrate_json_to_pg.py —— 一次性迁移：JSON → PostgreSQL
import json, sys
from application_book import ApplicationBook
from book_pg import PgApplicationBook

def main():
    dsn = sys.argv[1]                       # 从命令行传，不写死
    old = ApplicationBook("applications.json")
    pg = PgApplicationBook(dsn)
    for r in old.applications:              # 保留原状态迁移过去
        pg.add(r["company"], r["position"])
        # 已不是"已投递"的，补一次状态推进
    print(f"JSON {len(old.applications)} 条 → 迁移完成，请用 SELECT count(*) 对账")
```

**验收动作**：迁移前后 `SELECT count(*)` 与 JSON 条数一致；抽 2 条对比 status。

### C6. 回滚预案（工程素养）

JSON 文件**保留不删**；切换用一个开关（环境变量 `BOOK_BACKEND=pg|json`）——出问题 30 秒切回。**永远给自己留退路。**

---

## Part D · Redis（一节"YAGNI 讨论课"）

### D1. 先回答：你现在需要吗？——**不需要**

`_processed_messages`（消息去重 dict）在**单进程**里活得好好的。Redis 解决的是：

| Redis 的价值 | 你现在有这个问题吗 |
|---|---|
| 多进程共享状态（bot + 同步 + API 分进程）| ❌ 还在一个进程 |
| 重启不丢（dict 重启清空）| ⚠️ 轻微——去重丢了最多重复回一条消息 |
| 分布式锁/限流 | ❌ 单机用不上 |

**结论**：概念必须会（JD 高频），实操**标选做**——等 L15 多进程/上云再真上。

### D2. 最小实践（选做，30 分钟）

Windows 上装 Memurai（Redis 兼容）或 WSL 里 `apt install redis-server`；`pip install redis`；把 `_is_dup` 的 dict 换成：

```python
import redis
r = redis.Redis(decode_responses=True)

def _is_dup(key):
    return not r.set(key, "1", nx=True, ex=600)   # NX=不存在才写 EX=10分钟过期——一行顶原来八行
```

**教学点**：Redis 的 `SET NX EX` 把"检查+记录+过期"变成一个**原子操作**——比手写 dict + 定时清理更简洁且并发安全。

---

## Part E · 选做：PDF + 对象存储（L11 延后的账，一句话方案）

- **PDF**：你已经会 Playwright——`page.pdf()` 就能渲染。路径：Markdown 简历 → 简单 HTML 模板 → Playwright 打印成 PDF。一个下午的活，想做再做。
- **对象存储**：简历版本目前本地文件够了；等上云（L15）再考虑 OSS/MinIO。**别为不存在的问题引入基础设施。**

---

## Part F · 简历就绪（求职主线收口）

### F1. GitHub 侧

- 仓库转 Public，README 按 A6 重写完，**置顶**；
- 检查：无密钥、无隐私数据、README 让陌生人 10 分钟能跑起来。

### F2. 简历 bullet 模板（技术点 + 数字 + 结果，别写流水账）

```
· 基于飞书开放平台 + LangGraph 构建个人求职 Agent：消息/卡片回调全走 WebSocket 长连接，
  针对 at-least-once 投递设计 message_id 幂等去重与回调串行化，误触率降为 0
· 设计简历优化工作流（analyze → interrupt 人工确认 → rewrite）：状态守卫 + 10 分钟超时 + 卡片按钮，
  解决"跨消息等待"的幽灵确认与悬挂问题
· 用 Playwright 实现招聘官网岗位采集（DOM/XHR 双适配器），JD 经正则粗切 + LLM 清洗双层管道后
  入库，每日定时同步并留日志兜底
· pytest 覆盖状态机/数据层/清洗管道核心逻辑；PostgreSQL 化投递数据（接口不变换底层）；
  .env 管理密钥，任务计划程序守护 7×24 运行
```

（数字/措辞换成你的真实情况——面试官会追问每一条，**bullet 上的每句你都要能展开讲 3 分钟**。）

### F3. 面试故事弹药库（每条都来自你踩过的坑，STAR 直接讲）

| 问题 | 你的故事 |
|---|---|
| "遇到过最难的 bug？" | 长连接卡片回调无响应 → 读 SDK 源码发现旧客户端 CARD 分支空实现 → 换新通道层 + 探针验证 payload |
| "如何保证消息不重复处理？" | 至少一次投递 → message_id 去重 + 卡片回调身份去重（SDK 内置）|
| "为什么用 interrupt 而不是普通函数？" | 改简历必须人工确认；checkpointer 记住暂停态，thread_id=open_id 天然多用户隔离 |
| "爬虫怎么应对不同网站？" | id 在 DOM 走遍历、在 JS 走 XHR 拦截——两种适配器，接口一致可替换 |
| "服务怎么保证可用？" | 开机自启 + 失败重启 + 日志兜底 + 单点失败不中断同步 |

---

## 验证清单（做完逐条打勾）

- [ ] `git log --oneline` 有历史；GitHub 仓库可克隆；`git status` 干净（.gitignore 生效）
- [ ] `findstr` 密钥扫描无命中（源码/历史）
- [ ] `pytest tests\ -v` 全绿；改坏 TRANSITIONS 后测试变红（弄坏再修）
- [ ] PostgreSQL：迁移后 `SELECT count(*)` 与 JSON 条数一致；bot 换 PgApplicationBook 功能不变
- [ ] README 重写完成；`requirements.txt` + `.env.example` 就位
- [ ] （选做）Redis 版 `_is_dup` 跑通

## 弄坏再修（必做）

1. **删掉 `TRANSITIONS["已投递"]` 里的 "凉凉"** → 跑 pytest → 状态机结构测试变红 → 修回——亲眼看测试抓住回归；
2. **把 `.env` 改名 `.env.bak` 再跑 bot** → 缺密钥报错 → 理解"密钥只有 .env 一处来源"；
3. **故意 `git add .env`** → 被 .gitignore 挡住（`git check-ignore -v .env` 看是哪条规则挡的）——验证保护网真的在工作。

## 自测题（能口头回答才算过关）

- 为什么 `.gitignore` 必须在第一个 commit 之前就位？commit 过的密钥为什么"删了也还在"？
- 为什么先测纯逻辑（状态机/JD切分），不先测 `send_text`？
- `tmp_path` 夹具解决了什么问题（不用它会怎样）？
- `ApplicationBook` 换 PostgreSQL 为什么调用方几乎不用改？哪一行暴露了"实现细节泄漏"（`.applications`）？
- 什么时候才真的需要 Redis？`SET NX EX` 一行替代了原来哪三步？
- 你简历上的每条 bullet，能展开讲 3 分钟吗？

---

*做完把 GitHub 仓库链接贴回来，我 review README/commit 历史/测试。下一课 L15（选做增强）：多站点 Provider、工具调用显式化（LangGraph tools）、PDF 渲染。到这里，校招虾已经是一个值得写进简历、经得起面试追问的作品了。*
