# RepoMind：面向代码仓库理解与开发辅助的 Agentic RAG 工作台

RepoMind 是一个面向 **Repository Understanding / Coding Understand** 场景的 Agentic RAG 工作台。

用户输入 GitHub 仓库地址后，系统会自动克隆仓库、扫描项目结构、生成 AI 项目导读、构建 Chroma 语义索引，并通过 LangGraph Tool Calling Agent 支持围绕项目进行多轮源码问答、实现定位、架构理解、项目历史恢复和持续追问。

RepoMind 不仅可以用于从 0 理解陌生开源项目，也可以用于复盘自己的项目、辅助继续开发前的上下文恢复，以及作为代码仓库理解类任务的 Agentic RAG 工程实践。

---

## 1. 项目定位

RepoMind 的目标是帮助用户理解、管理和持续追问一个代码仓库，无论是陌生开源项目，还是自己的开发项目。

典型流程：

```text
输入 GitHub URL
→ 克隆仓库
→ 扫描项目结构
→ 生成 AI 项目导读
→ 构建 Chroma 代码语义索引
→ 保存项目历史
→ 围绕项目进行自然语言提问
→ Agent 调用检索工具
→ 基于源码上下文生成回答
→ 返回参考文件来源
→ 后续可从历史项目继续追问
```

适用场景：

- 从 0 理解未知代码仓库
- 快速理解陌生 GitHub / 开源项目
- 复盘和梳理自己的项目代码库
- 分析项目架构、核心流程和模块关系
- 定位具体功能的实现文件
- 理解函数、模块、API、数据库连接和调用流程
- 基于源码上下文进行可追溯问答
- 在继续开发前快速恢复项目上下文
- 保存多个项目的分析报告和问答历史
- 作为 Repository Understanding / Agentic RAG / Tool Calling / Eval / 后端持久化 的工程实践项目

---

## 2. 核心能力

当前版本支持：

- GitHub 仓库克隆与项目结构扫描
- AI 项目导读生成
- Chroma 代码语义索引
- LangGraph Tool Calling Agent
- Chroma 检索工具封装
- metadata / source citation 来源引用
- grade_documents 检索结果评估
- rewrite_question 检索问题重写
- project_report / memory_context / retrieved_context 上下文分层
- 项目导读上下文路由
- 多轮对话 memory
- SQLite / SQLAlchemy 项目历史持久化
- 历史项目恢复与继续追问
- 左侧历史项目栏
- 项目导读 / 项目对话 Tab 切换
- Agent trace 执行日志
- 最小 Eval 测试集
- FastAPI 服务化
- Web 工作台展示

---

## 3. 技术栈

| 层级 | 技术 |
|---|---|
| Agent 编排 | LangGraph StateGraph |
| Tool Calling | LangGraph ToolNode / LangChain Tool |
| LLM 框架 | LangChain |
| 大模型接口 | DeepSeek API |
| RAG 检索 | Chroma Semantic Search |
| 向量数据库 | Chroma |
| Embedding | HuggingFace Embeddings |
| 检索质量控制 | grade_documents / query rewrite |
| 上下文管理 | project_report / memory_context / retrieved_context |
| 数据持久化 | SQLite / SQLAlchemy |
| 后端服务 | FastAPI |
| 前端展示 | HTML / JavaScript |
| 测试评估 | 自定义最小 Eval 脚本 |

---

## 4. 系统架构

```text
Frontend Workspace
  ↓
FastAPI
  ↓
/analyze
  ↓
Repo Loader
  ↓
File Scanner
  ↓
Repo Analyzer
  ↓
AI Project Report
  ↓
Chroma Index
  ↓
SQLite Project Store

/projects
  ↓
Project History
  ↓
Restore AI Report / Chat History

/projects/{project_id}/ask
  ↓
Load Project Context from DB
  ↓
LangGraph Agent
  ↓
Entry Router
  ├─ report_answer
  └─ Tool Calling Agent
      ↓
      chroma_search_tool
      ↓
      collect_context
      ↓
      grade_documents
      ↓
      rewrite_question if needed
      ↓
      answer with sources
      ↓
      Save Message to DB
```

---

## 5. 项目分析流程

`POST /analyze` 负责项目分析、报告生成、索引构建和项目历史保存。

流程：

```text
GitHub URL
→ clone_repo
→ scan_repo / scan_and_build_tree
→ read_key_files
→ analyze_repo
→ generate_markdown_report
→ generate_llm_report
→ build_chroma_index
→ save_project
→ save CURRENT_PROJECT state
```

主要输出：

- 项目 ID
- 项目名称
- 项目类型
- 技术栈
- 文件树
- analysis_result
- AI 项目导读
- Chroma 向量索引
- SQLite 项目历史记录
- 初始 memory 状态

---

## 6. Agentic RAG 问答流程

RepoMind 当前支持两类问答入口：

- `POST /ask-v2`：围绕当前内存中的项目提问
- `POST /projects/{project_id}/ask`：围绕历史项目继续提问

当前 LangGraph 主流程：

```text
entry_router
├─ report_answer → END
└─ agent
    ↓
    tools_condition
    ├─ no tool_call → direct_answer → END
    └─ tool_call → tools
                  ↓
              collect_context
                  ↓
              grade_documents
              ├─ relevant → answer → END
              └─ not relevant → rewrite_question → agent
```

这个流程让 RepoMind 不只是简单的“检索后回答”，而是具备：

- 工具调用决策
- 检索上下文收集
- 检索结果评估
- 问题重写
- 项目导读上下文路由
- 多轮上下文利用
- 来源文件追踪

---

## 7. 上下文分层与项目导读路由

RepoMind 将不同上下文分开管理：

```text
project_report
= 项目级长期上下文，来自 /analyze 生成的 AI 项目导读

memory_context
= 对话级历史上下文，来自多轮问答记录

retrieved_context
= 本轮检索上下文，来自 Chroma 检索结果
```

当用户询问：

```text
项目导读内容是什么？
上面的报告为什么这么说？
你刚才生成的报告里提到了什么？
为什么项目导读会这么评价这个项目？
```

系统会走：

```text
entry_router → report_answer
```

直接基于 `project_report` 回答，不触发 Chroma 检索。

这样可以避免 Agent 将“项目导读”误解为 README、main.py 或代码中的介绍函数。

---

## 8. Tool Calling 与 RAG 检索

RepoMind 将 Chroma 检索封装为 LangChain Tool：

```text
chroma_search_tool
```

Agent 通过 `bind_tools()` 获得工具能力，由模型自行判断是否需要调用工具。

流程：

```text
LLM receives question
→ decides whether retrieval is needed
→ generates tool_call
→ ToolNode executes chroma_search_tool
→ ToolMessage is written back to messages
```

Chroma 检索结果会返回结构化内容：

```json
{
  "context": "...",
  "sources": ["main.py", "app/database.py"],
  "chunks": []
}
```

字段说明：

- `context`：给 LLM 使用的检索上下文
- `sources`：程序从 metadata 中提取出的真实来源文件
- `chunks`：结构化的检索片段信息

最终回答会附带参考文件，提升回答可追溯性，并降低模型编造文件来源的风险。

---

## 9. 检索评估与问题重写

### Retrieval Grading

`grade_documents_node` 会判断检索结果是否足够回答用户问题。

价值：

- 避免拿不相关上下文强行回答
- 让 Agent 具备检索结果反思能力
- 为 query rewrite 提供依据

### Query Rewrite

如果检索结果不相关，Agent 会触发问题重写：

```text
original_question
+ current_query
+ grade_reason
+ retrieved_context summary
→ rewritten_question
```

然后重新回到 `agent`，再次触发检索。

为避免无限循环，系统使用 `rewrite_count` 控制重写次数，当前最多重写一次。

---

## 10. 项目历史工作台

当前版本新增了项目历史工作台能力。

### 10.1 SQLite / SQLAlchemy 持久化

RepoMind 使用 SQLite + SQLAlchemy 保存项目和问答历史。

当前主要数据表：

```text
projects
project_messages
```

`projects` 保存：

- GitHub 仓库地址
- 项目名称
- 技术栈
- 本地 repo_path
- file_tree
- analysis_result
- AI 项目导读 ai_report
- 基础报告 basic_report
- created_at / updated_at

`project_messages` 保存：

- project_id
- 用户问题 question
- Agent 回答 answer
- timestamp

### 10.2 历史项目恢复

用户刷新页面或重新打开应用后，可以通过左侧历史项目栏恢复已分析项目。

恢复内容包括：

- 项目名称
- GitHub URL
- AI 项目导读
- 历史问答记录
- 项目分析上下文
- 本地仓库路径
- Chroma 索引路径

### 10.3 历史项目继续追问

新增接口：

```text
POST /projects/{project_id}/ask
```

流程：

```text
project_id
→ 从数据库读取项目上下文
→ 恢复 repo_path / file_tree / analysis_result / ai_report
→ 读取最近历史问答作为 memory_context
→ 调用 LangGraph Agent
→ 生成回答
→ 保存新一轮问答
```

这使 RepoMind 不再依赖单次内存状态，而是可以围绕历史项目持续使用。

---

## 11. Memory 多轮对话记忆

RepoMind 维护基础多轮对话记忆：

- `recent_turns`：保存最近问答
- `conversation_summary`：压缩较早对话
- `key_findings`：保存关键结论

在 `/ask-v2` 中，系统会将 memory 转为 `memory_context`，传入 Agent 回答节点，使连续追问可以复用历史上下文。

在历史项目问答接口 `/projects/{project_id}/ask` 中，系统会从数据库读取最近若干轮问答，拼接为 `memory_context`，从而支持历史项目继续追问。

---

## 12. Agent Trace 执行日志

RepoMind 在关键节点输出执行日志，方便调试和展示 Agent 行为。

普通代码问答示例：

```text
[EntryRouter] route: agent
[Agent] question: 这个项目的 API 路由是怎么设计的？
[Agent] tool_calls: [...]
[Collect] context length: 9776
[Collect] sources: ['README.md', 'main.py', 'requirements.txt']
[Grade] is_relevant: True
[Grade] reason: 检索上下文包含完整 API 路由定义。
[Answer] answer length: 324
```

项目导读问题示例：

```text
[EntryRouter] route: report_answer
[ReportAnswer] use project_report directly
```

这些日志可以帮助判断：

- 是否触发项目导读路由
- 是否触发 Tool Calling
- 调用了哪些工具
- 检索到了哪些来源文件
- 检索结果是否相关
- 是否触发 query rewrite
- 最终回答是否生成

---

## 13. Eval 最小测试集

RepoMind 提供最小 Eval 测试集，用于验证核心能力是否稳定。

文件结构：

```text
eval/eval_cases.json
scripts/run_eval.py
```

运行：

```bash
python -m scripts.run_eval
```

当前 Eval 检查：

- 是否成功返回 answer
- answer 是否非空
- 是否包含 expected keywords
- 是否包含参考文件
- 是否出现异常

---

## 14. API 简览

### 项目分析

```text
POST /analyze
```

用于分析 GitHub 仓库、生成 AI 项目导读、构建 Chroma 索引并保存项目历史。

### 当前项目问答

```text
POST /ask-v2
```

用于围绕当前内存中的项目进行 Agentic RAG 问答。

### 项目历史

```text
GET /projects
```

获取历史项目列表。

```text
GET /projects/{project_id}
```

获取指定项目详情，包括 AI 项目导读、项目结构和分析结果。

```text
GET /projects/{project_id}/messages
```

获取指定项目的历史问答记录。

```text
POST /projects/{project_id}/ask
```

围绕历史项目继续提问，并将新问答继续保存到数据库。

---

## 15. 快速开始

```bash
git clone https://github.com/SquamuleWie0/RepoMind.git
cd RepoMind
pip install -r requirements.txt
uvicorn app.api:app
```

打开：

```text
http://127.0.0.1:8000
```

示例仓库：

```text
https://github.com/BaseMax/SimpleFastPyAPI
```

注意：分析仓库时不建议使用 `--reload`，因为克隆仓库和 Chroma 索引会写入 `data/repos`，可能触发自动重启。

---

## 16. 当前限制

当前版本仍有一些限制：

- 主要检索后端是 Chroma 语义检索
- Source citation 当前是文件级引用，不包含行号
- Query rewrite 当前最多重试一次
- Eval 仍是关键词和来源存在性检查
- 当前尚未支持用户注册 / 登录，多用户数据隔离仍未完成
- 项目历史目前基于本地 SQLite，暂未接入 PostgreSQL
- 前端仍是轻量原生 HTML / JavaScript，主要用于 MVP 演示
- LangChain / Chroma 环境建议使用 Python 3.11 或 3.12

---

## 17. Roadmap

### 检索与工具层增强

- 增加 keyword search / ripgrep tool，补充语义检索之外的精确关键词检索能力
- 增加 repo tree inspection tool，用于查看项目目录结构
- 增加 file reader tool，实现指定文件精读
- 将 source citation 扩展到行号级别

### Eval 与可观测性

- 增加更丰富的 Eval 指标，例如 source 命中率、rewrite 触发率、回答稳定性等
- 在前端展示 Agent trace，方便观察 tool call、grade_documents、rewrite_question 等执行过程
- 保存每轮问答的 sources、grade 结果和 rewrite 记录，提升可复盘性

### 用户系统与部署

- 增加用户注册 / 登录
- 实现多用户项目隔离
- 增加服务器部署配置
- 增加 Docker 支持
- 后续可将 SQLite 替换为 PostgreSQL

---

## 18. 项目亮点

RepoMind 是一个基于 LangChain / LangGraph Tool Calling 的代码仓库理解与开发辅助 Agentic RAG 工作台。

它覆盖了 Agent 工程项目中的多个关键能力：

- Repository Understanding 代码仓库理解任务
- Tool abstraction 工具抽象
- Agentic RAG 编排
- Chroma 语义检索
- metadata / source citation 来源引用
- Retrieval grading 检索质量评估
- Query rewriting 问题重写
- Project report context routing 项目导读上下文路由
- Multi-turn memory 多轮上下文
- SQLite / SQLAlchemy 后端持久化
- Project history workspace 项目历史工作台
- Agent trace 可观测性
- Minimal Eval 回归测试
- FastAPI 服务化
- Web 工作台展示

这个项目的目标不是做一个普通聊天机器人，而是围绕代码仓库理解与开发辅助场景，构建一个可展示、可解释、可评测、可持续使用的 Agentic RAG 工程项目。
