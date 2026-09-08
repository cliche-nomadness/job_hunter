# 校招虾（Campus Recruitment Assistant）

接入飞书的个人校招求职助手，帮你：**跟踪投递进度 · 每日更新可投递岗位 · 按岗位改简历**。

## 文档

- [架构设计 `docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) —— 总体架构、领域模型、工作流、数据源接入、部署。
- [任务拆解 `docs/TASK_BREAKDOWN.md`](./docs/TASK_BREAKDOWN.md) —— 子代理任务划分、依赖关系、验收标准。

## 技术栈

Python 3.11+ · LangGraph · FastAPI · PostgreSQL(+pgvector) · Redis · 飞书开放平台 · 腾讯文档/石墨文档开放 API。

**核心引擎**：DeepSeek Harness（DSH）——既是开发期"总架构师 + 施工队"（`subagent`/`workflow`/`goal`/`ralph` 并行施工），也是运行期"智能中枢的模型内核与编排范式来源"（DeepSeek 模型 + LangGraph 范式映射）。详见 [`docs/ARCHITECTURE.md` §2](./docs/ARCHITECTURE.md)。

## 状态

📐 **当前阶段：架构设计评审**（代码尚未开始）。下一步是评审通过后，由 DSH 按 `TASK_BREAKDOWN.md` 第一批（T1 项目骨架、T2 领域模型、T3 飞书接入）并行派发子代理开工。
