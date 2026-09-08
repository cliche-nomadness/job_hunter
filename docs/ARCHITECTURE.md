# 校招虾（Campus Recruitment Assistant）架构设计

> 版本 v0.3.1 · 状态：待评审
> （v0.2 引入 DSH 角色定位；v0.3 新增「自动进度同步」；**v0.3.1 岗位/JD 数据源升级为自动抓取，与进度抓取对称**）
> 作者：AI Agent 架构工程师（运行于 DeepSeek Harness）
> 技术栈：Python 3.11+ / LangGraph / FastAPI / PostgreSQL / 飞书开放平台 / DeepSeek Harness

---

## 1. 产品定位

「校招虾」是一个**接入飞书**的个人校招求职助手，作为飞书机器人常驻在用户的聊天中，承担三件事：

1. **跟踪投递进度** —— 维护「投递 → 笔试 → 面试 → Offer → 结果」的完整状态机；**自动扫描招聘网站（只读）获取最新进度**，辅以手动补充，变化主动推送到飞书。
2. **每日更新可投递岗位** —— 每天定时**自动抓取招聘网站公开岗位（无需登录）**，或从用户在线表格（腾讯文档 / 石墨文档）拉取，去重、归一化、入库，并推送「今日新增/关闭」摘要。
3. **按岗位改简历** —— 针对某个具体岗位（JD），给出简历匹配度分析、修改意见，并在用户确认后**直接改写简历**，产出新版 Markdown 并渲染成 PDF。

非目标（v1 不做）：自动投递、模拟面试、多个用户协同、简历海投批量生成。

---

## 2. 核心引擎：DeepSeek Harness（DSH）的角色

### 2.1 DSH 是什么

**DeepSeek Harness（DSH）** 是本项目"开发、运行、演进"三位一体的承载平台：

- 它是驱动架构师 Agent（即本设计的作者）的**多智能体编排环境**，自带子代理扇出（`subagent`/`subagent_fork`）、大规模工作流（`workflow`）、目标持久化（`goal`）、新智体循环（`ralph`）等能力。
- 它运行在 **DeepSeek 模型**之上，与校招虾运行期调用的 LLM **同源**。
- 它的编排原语，正是校招虾 LangGraph 编排层的**设计范式来源**。

一句话：**校招虾 ≈ DSH 用自己（多智能体编排 + DeepSeek 模型）设计并建造出来的一个"求职垂直领域的小 DSH"。**

### 2.2 三重角色总览

| 阶段 | DSH 角色 | 关键体现 | 依赖的 DSH 能力 |
|---|---|---|---|
| **开发期**（现在） | 总架构师 + 施工队 | 设计 → 拆解 → 并行实现 → 测试 → 联调 | `subagent` / `subagent_fork` / `workflow` / `goal` / `ralph` / 文件与 shell / `web_search` |
| **运行期**（交付后） | 智能中枢的模型与范式内核 | 意图路由、JD 归一化、匹配、简历改写的"大脑" + 编排范式 | DeepSeek 模型（结构化输出/工具调用/长上下文）+ 编排原语映射 |
| **演进期** | 常驻工程师 | 改 prompt、加数据源、修 bug、调优 | 全部工具 + `goal` 跨轮续跑 |

### 2.3 开发期：总架构师 + 施工队

DSH 把"建造校招虾"从"人手写代码"变成"多智能体并行施工"：

| DSH 能力 | 在建造校招虾时的用途 |
|---|---|
| `subagent` / `subagent_fork` | T1（骨架）/ T2（领域模型）/ T3（飞书接入）三个子代理**并行施工**，互不阻塞 |
| `workflow` | 大规模同构任务扇出：批量生成 5 类飞书卡片模板、批量写单测、批量代码评审 |
| `goal` | 把"建造校招虾"注册为**跨多轮续跑的长期目标**，断点不丢、自动推进、可恢复 |
| `ralph` | 对"简历改写质量"这类难量化指标做**多轮新智体迭代打磨** |
| 文件/shell | 直接写代码、跑 `pytest`、建目录、验证依赖 |

### 2.4 运行期：模型内核 + 编排范式内核

- **模型内核**：校招虾运行期的 LLM 层直接调用 DeepSeek 模型（与驱动 DSH 的模型同家族），承载意图路由、JD 归一化、匹配打分、简历改写、卡片文案——这是产品的"大脑"。
- **编排范式内核**：DSH 的四个编排原语，一一映射到 LangGraph 运行期：

| DSH 原语 | 校招虾运行期对应 |
|---|---|
| `subagent` 扇出 | `JobSyncGraph` / `ProgressSyncGraph` 批量归一化时的并行子任务 |
| `workflow` 流水线 | 岗位 diff、进度 diff、匹配打分等分阶段流水线 |
| `goal` 持久化 | 投递跟踪的"长事务"——一个 offer 从投递到签约跨数月，状态机持久化 |
| `ralph` 新智体循环 | 简历改写：每次以「JD + 当前简历」为独立上下文的新智体，产出有界结构化结果、多轮收敛 |

### 2.5 演进期：常驻工程师

交付后 DSH 持续迭代校招虾——改 prompt、加数据源、修 bug、调优——成为常驻迭代引擎，而非一次性交付后离场。

### 2.6 边界声明（诚实边界）

校招虾运行期是独立的 FastAPI + LangGraph 进程，**不把 DSH 整个嵌进运行时二进制**（避免与单一 harness 强耦合）。DSH 的运行时贡献体现在"**模型同源 + 编排范式复用**"；开发期贡献则是实打实的"用这些能力把它造出来"。若未来需要更深的运行时耦合，可评估"DSH Agent 即服务"形态，但 v1 不依赖此假设。

---

## 3. 需求拆解与能力映射

| 需求 | 触发方式 | 核心能力 | 关键产物 |
|---|---|---|---|
| 跟踪投递进度 | 用户消息 + **定时自动扫描** | 投递记录的 CRUD + 状态机 + **自动抓取招聘网站进度（只读）+ LLM 整理 + diff 更新 + 主动推送** | `Application` 实体 + 进度卡片 + 状态变更推送 |
| 每日更新岗位 | 定时任务（cron）| **自动抓取招聘网站公开岗位（无需登录）+ 用户表格** → 归一化 → 去重 → 入库 → 推送 diff | `Job` 实体 + 每日摘要卡片 |
| 简历修改意见 | 用户消息 + 指定岗位/链接 | JD-简历 匹配度分析 + 差距诊断（JD 来自**自动岗位库**或**按需链接抓取**）| 匹配报告卡片 |
| 直接修改简历 | 卡片「确认修改」按钮 | 结构化改写 + 版本管理 + 渲染 PDF | 新版 `Resume` + PDF 文件 |

---

## 4. 总体架构

采用**分层 + 多 Agent 编排**架构，六层结构；顶部叠加 **DSH 开发期编排覆盖层**：

```
┌────────────────────────────────────────────────────────────────┐
│ ◆ DSH 开发期编排覆盖层（构建与演进时）                            │
│   subagent 并行施工 · workflow 批量扇出 · goal 长期目标 ·        │
│   ralph 质量迭代 · 文件/shell 施工                                │
└────────────────────────────────────────────────────────────────┘
        ▲ 只在"建造/演进校招虾"时生效，交付后不进入运行时
┌────────────────────────────────────────────────────────────────┐
│ ① 接入层 Access Layer                                          │
│    飞书事件回调网关（验签/解密） · 消息 · 卡片交互 · 文件上传     │
└───────────────────────────┬────────────────────────────────────┘
                            │ Webhook / SDK
┌───────────────────────────▼────────────────────────────────────┐
│ ② 编排层 Orchestration Layer（LangGraph，范式来自 DSH）          │
│    IntentRouter（意图路由）                                     │
│    ├─ TrackingGraph   投递进度子图（手动补充）                   │
│    ├─ JobSyncGraph    每日岗位更新子图（定时触发，★v0.3.1 自动抓取）│
│    ├─ ProgressSyncGraph 自动进度同步子图（定时触发，★v0.3）      │
│    ├─ MatchingGraph   岗位匹配/推荐子图                          │
│    └─ ResumeGraph     简历优化子图（分析→建议→改写→渲染）        │
└───────────────────────────┬────────────────────────────────────┘
                            │ 工具调用（Tool Call）
┌───────────────────────────▼────────────────────────────────────┐
│ ③ 工具层 Tool Layer                                            │
│    query_jobs / get_job / add_application / update_status       │
│    list_applications / analyze_match / rewrite_resume /         │
│    render_pdf / pull_jobs / pull_progress                       │
└───────────────────────────┬────────────────────────────────────┘
                            │ 接口调用
┌───────────────────────────▼────────────────────────────────────┐
│ ④ 领域服务层 Domain Service Layer                               │
│    JobService · ApplicationService · ResumeService ·            │
│    MatchingService · SpreadsheetService · ProgressSyncService · │
│    NotifyService                                                 │
└───────────────────────────┬────────────────────────────────────┘
                            │ ORM / 驱动
┌───────────────────────────▼────────────────────────────────────┐
│ ⑤ 数据层 Data Layer                                            │
│    PostgreSQL(+pgvector) · Redis · 对象存储(MinIO/S3)            │
└────────────────────────────────────────────────────────────────┘
        ▲ 横切：⑥ 定时任务调度层（APScheduler / Celery Beat；含每日岗位与进度扫描）
        ▲ 横切：⑦ LLM 层（DeepSeek 模型，与 DSH 同源）
```

分层职责边界清晰，便于并行开发：接入层与领域服务层可独立开发、通过工具层契约对接。

---

## 5. 技术选型

| 关注点 | 选型 | 理由 |
|---|---|---|
| **开发载体** | **DeepSeek Harness（DSH）** | 多智能体编排环境：`subagent` 并行施工、`workflow` 批量扇出、`goal` 长期目标、`ralph` 质量迭代（见 §2） |
| 编排框架 | **LangGraph** | 图状态机，适合多步、可中断、需人工确认的流程（如「确认修改」）；范式映射自 DSH 原语 |
| 后端服务 | **FastAPI** | 异步、类型友好，承载飞书回调 endpoint 与健康检查 |
| LLM 调用 | **langchain-core + 可插拔 ChatModel** | 通过 `with_structured_output` 拿 Pydantic 结构化结果，切换模型零改动 |
| 主模型 | DeepSeek（默认），可切 GPT/Claude | 便宜、中文好、支持结构化输出；与 DSH 同源 |
| Embedding | 本地 **BGE-M3**（sentence-transformers）/ 或 API embedding | 隐私可控、零调用成本；量大可换 API |
| 向量库 | **pgvector**（PostgreSQL 扩展） | 少一套中间件，事务一致，单用户规模足够 |
| 关系库 | **PostgreSQL 15+** | 岗位、投递、简历、审计日志 |
| 缓存/队列 | **Redis** | 会话状态、幂等去重、限流 |
| 定时任务 | **APScheduler**（内置）→ 规模上来换 Celery Beat | 单用户先跑在进程内，简单可靠 |
| 表格解析 | openpyxl / pandas + `qq-doc` / 石墨中台 API | 见 §10.1 |
| 浏览器自动化（★v0.3） | **Playwright**（`channel="msedge"` 用系统 Edge，Windows 免下载）| 登录态抓取投递进度页；公开页抓岗位/JD；兼 PDF 渲染候选 |
| PDF 渲染 | **Markdown → Jinja2 HTML 简历模板 → Playwright/WeasyPrint → PDF** | 简历需要排版美观，纯 Markdown 直出 PDF 太丑 |
| 对象存储 | MinIO（本地）/ S3（生产） | 存 PDF、表格快照、简历历史版本 |

---

## 6. 核心领域模型

```text
User
  id            PK
  feishu_open_id  unique      # 飞书用户身份，多用户隔离
  name
  profile_json             # 意向城市/岗位/行业/学历/届数
  active_resume_id         # 当前生效简历版本

Job                         # 可投递岗位（来自自动抓取或用户表格）
  id            PK
  title  company  city  dept  category
  jd_text                   # 原始 JD（自动抓取或表格提供）
  jd_embedding  vector(1024)   # 归一化后的向量
  link                      # 投递链接（自动抓取时兼作去重键）
  source                    # job_provider | tencent_docs | shimo | filedrop
  source_row_id             # 表格行 ID 或抓取源 ID，用于幂等去重
  status                    # open | closed
  first_seen_date  last_seen_date
  expires_at                # 过期时间（若表格提供）

Application                  # 投递记录
  id            PK
  user_id  job_id
  status                    # 状态机枚举
  status_history jsonb      # [{status, at, note}]
  notes
  applied_at  updated_at

Resume                       # 简历（版本化）
  id            PK
  user_id
  version       int
  markdown      text
  structured    jsonb        # 结构化（教育/实习/项目/技能）
  base_version  int?         # 由哪个版本派生
  created_at

ResumeEdit                   # 简历改写审计（可回滚、可解释）
  id  resume_id  job_id
  section                    # 被改的区块
  before  after  reason
  created_at
```

### 投递状态机（Application.status）

```text
applied(已投递) ──► screening(筛选中) ──► written_test(笔试)
   │                      │                    │
   │                      │                    ├─► interview(面试)
   │                      └─► rejected(凉凉)    │      │  interview 内部记录轮次
   │                                           │      ├─► hr_interview(HR面)
   │                                           │      └─► rejected
   └───────────────────────────────────────────┴─► offer(Offer)
                                                       ├─► accepted(已签约)
                                                       └─► declined(已拒)
```

规则：
- `rejected / accepted / declined` 为终态，进入后不可再推进。
- `interview` 阶段轮次（一面/二面/终面）记录在 `status_history` 的 `round` 字段，不单独建状态。
- 每次状态变更写入 `status_history`，支撑「时间线」展示与「N 天无进展」提醒。

---

## 7. 模块详解

### 7.1 接入层（飞书）

- **事件订阅**：`POST /feishu/event` 接收消息事件与卡片回调事件。
- **安全**：飞书请求头验签（`X-Lark-Signature` + 时间戳 + body），消息内容 `encrypt` 解密。
- **消息类型**：文本消息 → 走意图路由；**卡片回调**（`card.action.trigger`）→ 走已定义按钮动作。
- **鉴权前提**：飞书开放平台创建企业自建应用，开通 `im:message`（收发消息）、`im:resource`（上传下载文件）、`bitable:app`（可选，若用飞书多维表格做跟踪备份）等权限。

### 7.2 编排层（LangGraph，范式映射自 DSH）

**IntentRouter**（主图入口）：用一次轻量 LLM 调用把用户输入分类到子图，并顺带抽取必要实体，减少无效工具调用。

| 意图 | 子图 | 说明 | DSH 范式来源 |
|---|---|---|---|
| 记录/更新投递 | TrackingGraph | 「投了字节后端」「腾讯进二面了」 | `goal` 持久化（长事务状态机） |
| 查询进度 | TrackingGraph | 「我的进度」「字节到哪一步了」 | `goal` 持久化 |
| 看岗位/推荐 | MatchingGraph | 「今天有什么适合我的」 | `workflow`（检索→打分流水线） |
| 改简历 | ResumeGraph | 「针对腾讯后端帮我改简历」/ 粘贴岗位链接 | `ralph`（新智体循环收敛） |
| （定时） | JobSyncGraph / ProgressSyncGraph | 每日自动抓岗位/JD 与投递进度，不走意图路由 | `subagent`（独立任务） |
| 闲聊/其它 | 默认回复 | 引导语 + 可用指令菜单 | — |

**关键：ResumeGraph 需要「人工确认」节点**。LangGraph 用 `interrupt`（`interrupt_before` / 动态 interrupt）在「改写」前暂停，把差异卡片推给用户，等卡片按钮回调后再继续执行实际改写。这是「给意见」与「直接改」的分水岭。

### 7.3 工具层

每个 Agent 可调用的工具（`@tool` 装饰、带 Pydantic 入参）：

| 工具 | 入参 | 出参 | 说明 |
|---|---|---|---|
| `query_jobs` | 关键词/城市/类别、top_k | Job[] | 关键词 + 向量混合检索 |
| `get_job` | job_id | Job 详情 | |
| `add_application` | job_id, status, note | Application | 幂等：同 job 已有则拒绝 |
| `update_status` | application_id, new_status, round?, note | Application | 校验状态机合法性 |
| `list_applications` | status? | Application[] | 我的投递列表 |
| `analyze_match` | job_id, resume_id | MatchReport | 匹配度 + 差距诊断 |
| `rewrite_resume` | job_id, resume_id, sections[] | 新版 Resume + diff | 需人工确认后才执行 |
| `render_pdf` | resume_id | 文件 key | 渲染 PDF 并上传 |
| `pull_jobs`（★v0.3.1） | provider 名 | RawJobRow[] | 拉取岗位（招聘网站公开页或用户表格，仅定时任务触发） |
| `pull_progress`（★v0.3） | provider 名 | 网页文本 | 拉取投递进度页文本（仅定时任务触发，只读） |

### 7.4 领域服务层

- **JobService**：岗位 upsert（按 `source + source_row_id`/`link` 幂等）、**自动抓取招聘网站公开岗位（JobProvider）**、过期关闭、diff 计算（今日新增/关闭/更新）。
- **ApplicationService**：状态机校验、时间线记录、变更通知。
- **ResumeService**：Markdown ↔ 结构化互转、按 section 改写、版本管理（派生新版本、保留旧版）、审计。
- **MatchingService**：简历+意向向量化、JD 向量检索、LLM 精排打分、差距诊断。
- **SpreadsheetService**：用户表格 Provider 抽象 + 岗位归一化流水线（见 §10.1）。
- **ProgressSyncService**（★v0.3）：招聘网站进度 Provider 抽象 + 文本抓取 + LLM 整理 + 状态 diff + 更新（见 §10.3）。
- **NotifyService**：飞书卡片模板渲染与发送的统一出口。

### 7.5 数据层

- **PostgreSQL**：业务主库（`jobs / applications / resumes / resume_edits / users` + 审计表）。
- **pgvector**：`Job.jd_embedding`、简历向量，用于相似度检索。
- **Redis**：飞书事件幂等键（去重）、限流、`ResumeGraph` 中断恢复的临时状态。
- **对象存储**：PDF 产物、岗位快照、简历历史渲染件。

### 7.6 定时任务层

- 每日 `JobSyncGraph`（★v0.3.1）：**定时抓取岗位（招聘网站公开页 + 用户表格）→ 归一化 → 去重 upsert → 算 diff → 推飞书卡片**。
- 每日 `ProgressSyncGraph`（★v0.3）：**定时扫描招聘网站投递进度（只读）→ LLM 整理 → 与本地 diff → 更新状态机 → 推送变更**。
- 提醒任务：扫描 `Application` 中 N 天无进展的非终态记录，推送「跟进提醒」。
- 快照任务：每日保存岗位快照到对象存储，便于追溯。

### 7.7 LLM 层（DeepSeek，与 DSH 同源）

- 统一 `ChatModel` 抽象（DeepSeek 默认），`with_structured_output(PydanticModel)` 保证输出可解析。
- 四个关键结构化 Schema：
  - `NormalizedJob`（网页/表格行 → 岗位字段：公司/岗位/城市/类别/JD/链接）
  - `ProgressSnapshot`（★v0.3：网页文本 → 公司/岗位/状态/时间）
  - `MatchReport`（匹配度分项、差距点、修改优先级）
  - `ResumeSectionEdit`（section、改写后文本、修改理由）
- 温度策略：抽取/归一化用低温（0.1），改写建议用中温（0.5）。

---

## 8. 关键工作流（LangGraph 图）

### 8.1 每日岗位更新流 JobSyncGraph（定时，★v0.3.1 自动抓取）

```
start → pull_jobs(JobProvider：招聘网站公开页 / 用户表格)
      → normalize(LLM, 批量，DSH workflow 范式并行)
      → dedup(按 link 或 source+row_id) → upsert(JobService)
      → diff(新增/关闭/更新) → notify(每日摘要卡片) → end
```

失败处理：抓取失败 → 走用户表格（FileDropProvider）兜底；仍失败 → 记录日志 + 推「今日岗位拉取失败」告警卡片。

**按需链接抓取**（用户触发）：用户粘贴岗位链接 → `fetch_jd(url)` 当场抓取 JD → 直接进入简历分析，不必等每日任务。

### 8.2 投递进度跟踪流 TrackingGraph（手动补充）

```
start → 意图细分(新增 or 更新 or 查询)
新增: 解析实体(公司/岗位) → 检索 Job 匹配 → add_application → notify(确认卡片)
更新: 定位 Application → update_status(校验状态机) → notify(时间线更新卡片)
查询: list_applications → 渲染进度总览卡片
```

### 8.3 岗位匹配推荐流 MatchingGraph

```
start → 载入 profile + 生效简历 → 向量化 → query_jobs(top-k 混合检索)
      → LLM 精排(结合意向+简历) → 渲染推荐卡片(含「投递了」按钮) → end
```

### 8.4 简历优化流 ResumeGraph（核心，含人工确认）

```
start → 定位岗位(job_id 或 按需链接) → analyze_match(JD vs 简历) → 生成 MatchReport
      → notify(匹配报告卡片 + 「查看建议」/「确认改写」按钮)
      → [interrupt 等待用户选择]
      ├─ 仅看建议 → 结束
      └─ 确认改写 → rewrite_resume(指定 sections) → 版本化保存
                    → render_pdf → notify(差异卡片 + PDF 文件) → end
```

改写采用「**区块级**」而非整篇重写：只改 `项目经历 / 个人总结 / 技能` 等与 JD 强相关的 section，避免篡改事实。所有改写写入 `ResumeEdit`，可解释、可回滚。此流程正是 DSH `ralph` 新智体循环的 LangGraph 落地：每次改写以「JD + 当前简历」为独立上下文，产出有界结构化结果。

### 8.5 自动进度同步流 ProgressSyncGraph（★v0.3，定时触发）

```
start → [APScheduler 每日] → pull_progress(ProgressProvider，只读抓取网页文本)
      → extract(LLM 整理：网页文本 → ProgressSnapshot[公司/岗位/状态/时间])
      → diff(与本地 ApplicationBook 比对)
      → 有变化 → map_status(LLM 映射到状态机合法状态) → update_status + 时间线
      → notify(飞书推送「×× 状态变更」) → end
      无变化 → 静默结束
```

失败处理：抓取失败 → 跳过当天 + 推送「今日进度抓取失败」；站点改版导致解析异常 → 保留本地状态不变，推送告警。

**与手动 TrackingGraph 的关系**：自动扫描为主、手动输入为辅（双轨）。网站看不到的信息（HR 私聊、邮件进度）由用户手动补充。

---

## 9. 飞书交互设计

- **消息卡片（Interactive Card）**：岗位推荐、每日摘要、进度总览、匹配报告、简历 diff 均用卡片承载，卡片底部带按钮。
- **按钮动作映射**：
  - `投递了` → 创建 Application（带 job_id 回传）
  - `更新状态` → 弹状态选择器（下拉/按钮组）
  - `确认改写` / `只看建议` → 触发 ResumeGraph 的 interrupt 恢复
  - `下载 PDF` → 返回文件消息
- **斜杠指令 / 快捷菜单**：`/新增投递 /更新进度 /我的进度 /今日岗位 /改简历 /帮助`。
- **状态可视化**：进度总览用「看板式」卡片，按状态分组 + 时间线。
- **主动推送**（★v0.3）：`ProgressSyncGraph` 检测到状态变更时，主动推送「×× 从『笔试』变为『面试』」消息（无需用户询问）。

---

## 10. 数据源接入（用户表格 / 招聘网站公开岗位 / 投递进度网站）

### 10.1 岗位数据源：SpreadsheetProvider（用户表格：腾讯文档 / 石墨文档 / FileDrop）

**核心抽象**：

```python
class SpreadsheetProvider(Protocol):
    def pull(self) -> list[RawJobRow]: ...   # 返回原始行 dict
```

| Provider | 方式 | 前置条件 |
|---|---|---|
| `TencentDocsProvider` | 腾讯文档开放平台 [open API v2](https://docs.qq.com/open/document/)（社区封装 [`qq-doc`](https://github.com/easy-wx/qq-doc)） | 创建应用 + 企业/账号授权，拿 access_token |
| `ShimoProvider` | 石墨文档[开放平台中台](https://open.shimo.im/docs/06API-document/overview)（[鉴权](https://sdk.shimo.im/docs/api-be-authentication/)） | 创建应用 + 授权 |
| `FileDropProvider` | 监听本地/对象存储目录，解析导出文件 `.xlsx/.csv` | **零依赖，引导期兜底** |

**归一化流水线**：原始行（列名可能不规范）→ LLM 映射到 `NormalizedJob` → 校验必填字段（公司+岗位+链接）→ 入库。同一行以 `source + source_row_id` 幂等。

> 定位：用户表格是**兜底与补充**——自动抓取覆盖不到的岗位（内推、猎头、内部渠道）由用户表格提供。

### 10.2 岗位/JD 自动抓取：JobProvider（招聘网站公开页，★v0.3.1）

**核心抽象**（与 SpreadsheetProvider 同构）：

```python
class JobProvider(Protocol):
    def pull(self) -> list[RawJobRow]: ...   # 招聘网站/公司招聘页的公开岗位行
```

**实现要点**：

| 要点 | 设计 |
|---|---|
| 公开性 | **无需登录**（岗位/JD 是公开页面），无登录态、无 ToS 登录风险——比进度抓取简单且安全 |
| 抓取 | 每日低频（一次）抓公司招聘页/招聘网站列表页 → 提取文本（不依赖脆弱选择器）|
| 归一化 | LLM：文本 → `NormalizedJob`（公司/岗位/城市/JD/链接）|
| 去重 | 按 `link` 幂等（同链接不重复入库）|
| 按需 | `fetch_jd(url)`：用户粘贴岗位链接 → 当场抓 JD → 直接简历分析（§8.1）|
| 合规 | 只抓公开页、每日一次低频、不绕过登录墙，尊重站点 robots 与频率限制 |

**采集技术（Playwright 页面抓取，★v0.3.1 实测）**：

核心是"**渲染页面 → 抓取 → 文本兜底**"，不依赖 API、不硬编码脆弱选择器：

| 技术点 | 做法 |
|---|---|
| 浏览器 | Playwright + **系统 Edge**（`channel="msedge"`）—— Windows 免下载 Chromium |
| SPA 渲染 | `wait_until="load"` + `wait_for_timeout(8s)` 等异步岗位数据渲染出来 |
| 找岗位 | 优先找详情链接（`#/job/{id}`、`/job/`、`jobAdId=`）；兜底提取文本行（岗位名带编号）|
| 抓 JD | 进详情页 → `inner_text("body")` 拿全文 → 正则标出"职位描述/任职要求"区段 |
| 拦截响应 | 岗位 id 藏在 JS 状态里时，`page.on("response")` 监听页面自发的岗位接口拿结构化数据 |
| 网络健壮性 | **重试 3 次 + 超时 100s + 请求间停顿**（国内站偶发 `ERR_CONNECTION_TIMED_OUT`/限流的标配）|

**两种适配器（跨 SaaS 扩展的真实成本）**：

| 平台类型 | 特征 | 采集方式 |
|---|---|---|
| **Moka 类**（id 在 DOM）| 岗位是 `<a href="#/job/{id}">` | 纯页面抓取，零 API 依赖（已跑通）|
| **zhiye 类**（id 在 JS）| 岗位是 JS 渲染 div，`jobAdId`(UUID) 不在 DOM | 监听页面自发 XHR 拿结构化岗位 |

> **参考实现**：`cli/scrape_jobs.py`（统一入口：传列表 URL 抓岗位列表，加序号抓对应 JD；Moka 已验证）。教学见课程大纲 L12。

**与简历分析的关系**：`ResumeGraph` 的 JD 来源 = 自动岗位库（JobSyncGraph 每日同步）**或**用户粘贴链接的按需抓取——**不再依赖用户手工维护 JD**。

### 10.3 进度数据源：ProgressProvider（招聘网站，需登录态，★v0.3）

**核心抽象**（与 SpreadsheetProvider 同构）：

```python
class ProgressProvider(Protocol):
    def pull(self) -> str: ...   # 返回"我的投递"页面的可见文本（原始）
```

**实现要点**：

| 要点 | 设计 |
|---|---|
| 会话 | **用户手动登录一次** → agent 保存 cookie/session 复用；**不自动登录**（规避验证码/风控/ToS） |
| 抓取 | Playwright 打开"我的投递"页 → 提取**页面可见文本**（不依赖脆弱 DOM 选择器） |
| 整理 | LLM：网页文本 → `ProgressSnapshot`（公司/岗位/状态/时间），容忍格式变化 |
| 状态映射 | LLM 映射到状态机合法状态 + 兜底规则（"已结束/不合适"→终态；"流程中"→保持现状） |
| 只读边界 | **只读不写**（只抓页面、不点按钮），降低封号风险；单站点 MVP 起步 |
| 失败降级 | 抓取失败跳过当天 + 推送告警；站点改版 → 保留本地状态 + 告警 |

> 风险声明：自动登录多数招聘网站违反其 ToS，可能封号。**手动登录 + 只读抓取**是安全边界，不是功能缺失。

---

## 11. 安全与合规

- 飞书回调验签 + 消息解密，防伪造请求。
- 用户按 `feishu_open_id` 严格隔离（单用户为主，但数据模型天然支持多用户）。
- 密钥（飞书 app secret、腾讯/石墨 token、LLM key）走环境变量 / 密钥管理，不入库不进 git。
- 简历属高敏感个人数据：对象存储私有桶、传输加密、`ResumeEdit` 全量审计、支持回滚。
- LLM 调用点统一打日志（不落简历正文，只落 token 与结构化结果摘要）。
- **进度抓取合规**（★v0.3）：手动登录 + 只读抓取，不自动登录、不写操作，规避招聘网站风控与 ToS 风险；cookie 本机保存，不随代码分发。
- **岗位抓取合规**（★v0.3.1）：只抓公开页面、每日低频一次、不绕过登录墙，尊重站点 robots 与频率限制。

---

## 12. 部署架构

**引导期（单机，最简单）**：

```
Docker Compose
  ├─ app（FastAPI + APScheduler 同进程）
  ├─ postgres(+pgvector)
  ├─ redis
  └─ minio
```

- 飞书回调需要**公网可达** HTTPS 地址：开发期用内网穿透（ngrok / frp / cloudflared），生产挂域名 + 反代。
- 定时任务初期与 web 同进程（APScheduler），后续拆 Celery Worker + Beat。

**生产演进**：app 与 worker 分离、PostgreSQL 托管、对象存储换 S3、加监控（Prometheus + 结构化日志）。

---

## 13. 里程碑规划（DSH 驱动开发）

| 里程碑 | 内容 | 验收标志 | DSH 执行方式 |
|---|---|---|---|
| M0 项目骨架 | 仓库结构、依赖、配置、飞书回调通 | 飞书能收到机器人回声 | `subagent` ×3 并行（T1/T2/T3） |
| M1 投递跟踪 | Application 领域 + 工具 + TrackingGraph + 卡片 | 能记录/更新/查进度 | `subagent`（T4） |
| M2 岗位接入（★v0.3.1） | JobProvider（公开页抓取）+ 用户表格 + 每日任务 | 每天自动入库公开岗位，表格兜底，推送摘要 | `subagent`（T5）+ `workflow` 批量归一化 |
| M3 简历优化 | 简历结构化 + MatchingGraph + ResumeGraph | 能出匹配报告（JD 来自自动岗位库/按需链接）并确认改写产出 PDF | `subagent`（T6）+ `ralph` 迭代改写质量 |
| M4 增强 | 官方 API 适配器、提醒、向量精排调优 | 全流程稳定运行 | 持续迭代（常驻工程师） |
| M5 自动进度同步（★v0.3） | ProgressProvider + 单站点抓取 + LLM 整理 + diff 更新 + 定时 | 每天自动更新投递进度并推送变更 | `subagent`（适配器）+ `workflow`（多站点扇出） |

全程以 `goal` 把"建造校招虾"注册为长期目标，跨多轮续跑、断点可恢复。

---

*本文档为 v0.3.1 评审稿（v0.2 新增 §2 DSH 角色定位；v0.3 新增 §8.5、§10.3「自动进度同步」；v0.3.1 §8.1、§10.2 岗位/JD 数据源升级为自动抓取，与进度抓取对称）。任务执行层面的具体拆解见 [TASK_BREAKDOWN.md](./TASK_BREAKDOWN.md)。*
