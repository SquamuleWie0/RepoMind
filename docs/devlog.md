# RepoMind 开发记录

## 2026-05-02

今天主要完成了 RepoMind 的基础数据链路搭建，包括 `repo_loader`、`file_scanner`、`file_reader`、`repo_analyzer` 和 `report_generator`。现在系统已经可以输入 GitHub URL，将仓库克隆到本地，扫描项目目录，筛选并读取关键文件，再通过规则分析项目类型、技术栈、入口文件、依赖文件和核心目录，最后生成一份 Markdown 基础报告。我使用 `https://github.com/mco-org/squad` 做了测试，成功生成了报告。目前这个版本还只是规则分析，报告只能输出比较基础的项目信息，不能真正理解项目功能、模块关系和运行逻辑。今天的主要收获是打通了 RepoMind 的基础数据流：GitHub URL → 克隆仓库 → 扫描目录 → 读取关键文件 → 规则分析 → 生成报告。

---

## 2026-05-03

今天主要接入了 DeepSeek API，让 RepoMind 从规则分析推进到大模型项目导读阶段。我新增了 `llm_client` 和 `llm_analyzer`，把文件树、规则分析结果和关键文件内容交给大模型生成项目导读，并多次调整 Prompt，让报告更自然、易读。同时开始接触 `ripgrep / rg`，验证了它可以在本地仓库中快速搜索代码内容，并初步加入 `code_searcher`，为后续项目问答做准备。今天的核心理解是：RepoMind 不能只是把项目直接丢给大模型，而是要先整理项目材料，再让模型基于上下文生成更可靠的结果。

---

## 2026-05-04

今天主要完善了 RepoMind 的 Agent 问答链路和 Web 交互。新增了 `memory_manager`、`question_router`、`query_planner`、`context_builder`、`result_evaluator`、`embedding_indexer`、`vector_searcher` 和 `retrieval_router` 等模块，让系统可以支持多轮对话、问题路由、代码检索、上下文扩展、检索结果自评、二次检索和轻量混合检索。前端也从简单结果展示调整成了更像聊天窗口的形式，支持 Markdown 渲染和连续问答。今天最大的收获是更清楚地理解了 Agent 的核心：不是单次调用大模型，而是让 LLM 在问题判断、检索规划、检索方式选择、结果评估和最终回答等环节中与工具协作。