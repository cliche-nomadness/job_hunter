# 校招虾 · 任务拆解（子代理分配方案）

> 配套文档：[ARCHITECTURE.md](./ARCHITECTURE.md)（§2 为 DSH 角色定位）
> 原则：每个子任务（可交给一个子代理）都**输入明确、产出可验收、依赖清晰**，尽量可并行。

## 执行载体：DeepSeek Harness（DSH）

本拆解由 DSH 直接执行，映射关系如下：

| 拆解元素 | DSH 执行方式 |
|---|---|
| 单个子任务（T1~T7） | `subagent` / `subagent_fork` 派发，独立上下文施工 |
| 同构批量任务（卡片模板/单测/评审） | `workflow` 扇出 |
| 简历改写质量打磨 | `ralph` 新智体循环迭代 |
| 整体进度与断点续跑 | `goal` 长期目标持久化 |

---

---

## 依赖关系总览

```text
T1 项目骨架 ──────────────┬──► T4 投递跟踪（依赖 T1 契约）
                          ├──► T5 岗位接入（依赖 T1 契约）
                          └──► T6 简历优化（依赖 T1 契约）
T2 领域模型（可并行，T3/T4/T5 都依赖其 schema）
T3 飞书接入（可并行，产出卡片/回调 SDK 封装，供 T4/T5/T6 复用）
```

**执行建议**：先并行做 **T1、T2、T3**（纯基础能力，互不依赖）；三件落地后，**T4、T5、T6 并行**；最后 **T7 集成联调**。

---

## T1 项目骨架（基础设施）

**目标**：可运行的 FastAPI 工程 + Docker Compose + 配置与日志体系。

**输入**：`ARCHITECTURE.md` §4、§11。

**产出/验收**：
- 仓库目录结构（`app/`、`app/api/`、`app/core/`、`app/services/`、`app/graphs/`、`app/tools/`、`app/models/`、`tests/`）
- `pyproject.toml` 或 `requirements.txt` 锁定依赖（fastapi、langgraph、langchain-core、openai/deepseek 客户端、sqlalchemy、asyncpg、redis、minio、openpyxl、jinja2、weasyprint 或 playwright）
- `docker-compose.yml` 拉起 postgres(pgvector)+redis+minio
- 配置管理（pydantic-settings，读 `.env`）+ 结构化日志
- 健康检查 `GET /healthz`

**依赖**：无（最先启动）。

---

## T2 领域模型与数据访问

**目标**：建表 + SQLAlchemy ORM + Alembic 迁移 + 基础仓储接口。

**输入**：`ARCHITECTURE.md` §5（User/Job/Application/Resume/ResumeEdit 及状态机）。

**产出/验收**：
- Alembic 迁移脚本，建齐五张表 + pgvector 扩展 + 索引（`Job.source+source_row_id` 唯一索引、`Application.user_id+job_id` 唯一索引、向量索引）
- ORM 模型与 Pydantic schema
- `ApplicationStatus` 枚举 + **状态机合法性校验函数**（含单元测试：非法迁移被拒绝）
- 仓储层接口（`JobRepo` / `ApplicationRepo` / `ResumeRepo`）

**依赖**：T1（数据库连接）。

---

## T3 飞书接入层（可并行）

**目标**：飞书回调网关 + 卡片 SDK 封装 + 文件上传下载。

**输入**：`ARCHITECTURE.md` §6.1、§8。

**产出/验收**：
- `POST /feishu/event`：验签、消息解密、事件分发（`message.receive`、`card.action.trigger`）
- 幂等去重（Redis 存事件 ID）
- 卡片模板工具：岗位卡片 / 进度卡片 / 匹配报告卡片 / 简历 diff 卡片 / 每日摘要卡片（Jinja2 模板 + 按钮动作定义）
- 文本消息回复、文件上传/下载封装
- 一组可在本地无真实飞书环境跑通的**单元测试**（mock SDK）

**依赖**：T1。

---

## T4 投递进度跟踪（业务线 A）

**目标**：TrackingGraph + 相关工具 + 状态卡片，实现「记录/更新/查询进度」。

**输入**：`ARCHITECTURE.md` §6.3（add_application/update_status/list_applications）、§7.2。

**产出/验收**：
- 工具：`add_application`、`update_status`、`list_applications`（调 T2 仓储）
- `TrackingGraph`（新增/更新/查询三支）
- 意图实体抽取 Prompt + 结构化 schema（公司/岗位/新状态/轮次）
- 进度总览卡片 + 时间线渲染
- 端到端测试：`"投了字节后端"` → 建记录；`"字节进二面了"` → 状态迁移 + 历史写入

**依赖**：T2、T3。

---

## T5 岗位接入与每日更新（业务线 B）

**目标**：SpreadsheetService（Provider 抽象 + FileDrop 落地）+ JobSyncGraph + 每日任务。

**输入**：`ARCHITECTURE.md` §6.4、§6.6、§9、§7.1。

**产出/验收**：
- `SpreadsheetProvider` 协议 + `FileDropProvider`（openpyxl/pandas 解析 `.xlsx/.csv`，容忍列名不规范）
- 归一化：原始行 → LLM `NormalizedJob`（批量、低温、失败行跳过并记录）
- `JobService`：幂等 upsert（source+row_id）、过期关闭、diff（新增/关闭/更新）
- `JobSyncGraph` + APScheduler 每日 cron + 每日摘要卡片推送
- 测试：构造一份样例表格 → 跑图 → 库中出现岗位 → 第二次跑无重复 → 改表格后 diff 正确

**依赖**：T2、T3。

---

## T6 简历优化（业务线 C，核心）

**目标**：简历结构化 + MatchingGraph + ResumeGraph（含 interrupt 人工确认 + 改写 + PDF）。

**输入**：`ARCHITECTURE.md` §6.3、§7.4、简历 Markdown→PDF 方案 §4。

**产出/验收**：
- 简历导入：Markdown 解析为结构化 `Resume.structured`（教育/实习/项目/技能）
- `analyze_match`：JD vs 简历匹配报告（`MatchReport` schema：分项得分、差距点、优先级）
- `rewrite_resume`：区块级改写（`ResumeSectionEdit`），版本派生 + `ResumeEdit` 审计
- `render_pdf`：Jinja2 简历模板 → Playwright/WeasyPrint → 对象存储，返回下载
- `ResumeGraph`：**LangGraph `interrupt`** 在「确认改写」前暂停，卡片回调恢复
- 测试：给定 JD + 一份简历 → 出报告 → 确认 → 新版本生成、diff 正确、旧版可回滚、PDF 可下载

**依赖**：T2、T3。

---

## T7 集成联调与端到端验收

**目标**：把所有子图接入 IntentRouter 主图，端到端跑通，写运行手册。

**输入**：T1–T6 全部产出。

**产出/验收**：
- `IntentRouter` 主图 + 指令菜单（`/帮助 /新增投递 ...`）
- 全链路 E2E：飞书消息 → 意图 → 子图 → 卡片 → 回调 → 落库/出 PDF
- `.env.example`、`README.md` 运行手册、飞书应用配置 checklist（权限清单）
- 完整测试套件 + CI（可选）

**依赖**：T4、T5、T6。

---

## 并行与顺序小结

| 阶段 | 可并行子任务 | 说明 |
|---|---|---|
| 第一批（并行 3 个） | T1、T2、T3 | T2/T3 都只依赖 T1 的契约，可同时开工 |
| 第二批（并行 3 个） | T4、T5、T6 | 各业务线，共享 T2 仓储 + T3 卡片 |
| 第三批（串行收口） | T7 | 依赖全部业务线 |

---

## 给子代理的统一交付规范

每个子任务完成时须交付：
1. 代码 + 对应测试（能 `pytest` 跑绿）；
2. 一个简短的 `docs/notes/T{n}.md`，说明实现要点、偏离架构处、遗留 TODO；
3. 明确声明**对外接口/契约**（工具签名、schema、卡片按钮 action 值），供其它子任务对接。
