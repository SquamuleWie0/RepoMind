# RepoMind

RepoMind 是一个面向代码仓库理解场景的 Agentic RAG 工程项目，基于 FastAPI、LangGraph、LangChain 和 Chroma 构建，覆盖仓库分析、源码语义检索、Tool Calling、多轮问答、来源引用、检索评估、问题重写、Agent Trace 和最小 Eval 测试闭环。该项目重点展示 AI Agent 在真实代码理解场景中的工程化落地能力。

用户输入 GitHub 仓库地址后，RepoMind 会自动克隆仓库、扫描项目结构、生成 AI 项目导读、构建代码语义索引，并通过 LangGraph Tool Calling Agent 围绕项目源码进行多轮问答，帮助用户快速理解陌生代码仓库。

---

## Quick Start

### 方式一：Docker（推荐，最快）

```bash
git clone https://github.com/SquamuleWie0/RepoMind.git
cd RepoMind

cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY=你的 DeepSeek Key

docker compose up --build
```

启动后浏览器打开：

```text
http://127.0.0.1:8000
```

### 方式二：本地直接运行

```bash
git clone https://github.com/SquamuleWie0/RepoMind.git
cd RepoMind

python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY=你的 DeepSeek Key

uvicorn app.api:app --host 0.0.0.0 --port 8000
```

启动后浏览器打开：

```text
http://127.0.0.1:8000
```

> 两种方式都启动成功后，可在下方 [Demo Flow](#demo-flow) 中输入 GitHub 仓库地址开始体验。

---

## Features

- GitHub 仓库克隆与项目文件扫描
- AI 项目导读生成
- 基于 Chroma 的源码语义检索
- 基于 LangGraph 的 Agentic RAG 工作流
- LangChain Tool Calling 与 ToolNode 工具调用
- metadata / source citation 来源引用
- grade_documents 检索结果评估
- rewrite_question 检索问题重写
- 多轮对话 memory
- Agent Trace 执行日志
- FastAPI 后端服务
- Web 前端 Demo
- 最小 Eval 测试集与回归脚本

---

## Tech Stack

| Layer | Tech |
|---|---|
| Backend Service | FastAPI |
| Agent Orchestration | LangGraph |
| LLM Framework | LangChain |
| LLM API | DeepSeek API |
| Vector Database | Chroma |
| Embedding Model | HuggingFace Embeddings |
| RAG Retrieval | Chroma Semantic Search |
| ORM / Storage | SQLAlchemy / SQLite |
| Frontend Demo | HTML / JavaScript |
| Evaluation | Custom Minimal Eval Scripts |

---

## Highlights

- 构建面向 GitHub 代码仓库理解的端到端 Agentic RAG 系统。
- 基于 LangGraph StateGraph 设计多节点 Agent 工作流，覆盖工具调用、上下文收集、检索评估、问题重写与回答生成。
- 将 Chroma 向量检索封装为 LangChain Tool，使模型能够自主判断是否需要检索源码上下文。
- 基于 metadata 实现 source citation，回答时返回真实参考文件，降低代码问答中的来源幻觉。
- 引入 grade_documents 检索评估机制，避免在上下文不相关时强行生成回答。
- 引入 rewrite_question 问题重写机制，在问题模糊或检索不足时自动优化查询。
- 设计 project_report / memory_context / retrieved_context 上下文分层机制，支持围绕项目导读和历史问答继续追问。
- 基于 FastAPI 提供项目分析、Agent 问答、历史项目和问答记录接口。
- 设计最小 Eval 测试集，用于验证 Tool Calling、source citation、检索评估、问题重写和回答稳定性。

---

## Architecture

```text
GitHub Repository
    ↓
Repo Loader
    ↓
File Scanner
    ↓
Project Analyzer
    ↓
AI Project Report
    ↓
Chroma Vector Index
    ↓
LangGraph Tool Calling Agent
    ↓
chroma_search_tool
    ↓
collect_context
    ↓
grade_documents
    ↓
rewrite_question if needed
    ↓
answer with source citation
    ↓
FastAPI + Web Demo
```

---

## Agentic RAG Workflow

RepoMind 的核心问答流程基于 LangGraph StateGraph 构建。

```text
entry_router
    ↓
agent
    ↓
ToolNode
    ↓
collect_context
    ↓
grade_documents
    ↓
rewrite_question
    ↓
answer
```

在问答过程中，Agent 会根据用户问题自主判断是否需要调用检索工具：

```text
User Question
    ↓
LLM Agent
    ↓
decide whether to call tool
    ↓
chroma_search_tool
    ↓
ToolMessage
    ↓
context collection
    ↓
retrieval grading
    ↓
answer generation
```

如果检索结果足够相关，系统会直接生成回答；如果检索结果不足或不相关，系统会触发问题重写，再次进入 Agent 流程进行检索和回答。

---

## Tool Calling

RepoMind 将 Chroma 代码语义检索封装为 LangChain Tool：

```text
chroma_search_tool
```

Agent 通过 `bind_tools()` 获得工具调用能力，并通过 `ToolNode` 执行工具。

核心流程：

```text
LLM receives question
    ↓
LLM decides whether retrieval is needed
    ↓
LLM generates tool_call
    ↓
ToolNode executes chroma_search_tool
    ↓
ToolMessage is written back to messages
    ↓
Agent continues reasoning with retrieved context
```

该设计使模型不再被动接收固定上下文，而是能够根据问题自主决定是否检索源码，从而更贴近真实 Agent 应用中的工具调用模式。

---

## Source Citation

RepoMind 的检索结果不只是普通文本，而是包含结构化来源信息：

```json
{
  "context": "...",
  "sources": ["main.py", "app/database.py"],
  "chunks": []
}
```

字段说明：

| Field | Description |
|---|---|
| context | 提供给 LLM 的源码检索上下文 |
| sources | 从 metadata 中提取出的真实来源文件 |
| chunks | 结构化检索片段信息 |

最终回答会附带参考文件：

```text
参考文件：
- main.py
- app/database.py
```

该机制可以提升回答的可追溯性，并降低模型编造文件路径或文件来源的风险。

---

## Retrieval Grading

RepoMind 引入 `grade_documents` 节点，对检索结果进行质量评估。

示例输出：

```json
{
  "is_relevant": true,
  "reason": "检索上下文包含 API 路由定义，足以回答问题。"
}
```

主要作用：

- 判断检索上下文是否足够回答用户问题
- 避免基于不相关上下文强行回答
- 为问题重写提供依据
- 提升复杂问题和模糊追问下的回答稳定性

---

## Query Rewriting

当检索结果不相关或信息不足时，RepoMind 会触发问题重写。

```text
original_question
+ current_query
+ grade_reason
+ retrieved_context summary
    ↓
rewritten_question
    ↓
back to agent
```

系统会将原始问题、当前查询、检索评估原因和已有上下文摘要传入重写节点，生成更适合检索的问题。

为避免无限循环，系统通过 `rewrite_count` 控制重写次数，当前最多重写一次。

---

## Memory Design

RepoMind 支持基础多轮对话记忆，用于连续追问场景。

Memory 主要包括：

| Memory Field | Description |
|---|---|
| recent_turns | 保存最近几轮问答 |
| conversation_summary | 压缩较早对话 |
| key_findings | 保存项目理解中的关键结论 |

在 `/ask-v2` 流程中，系统会将 memory 转换为 `memory_context`，并传入 Agent 回答节点，使用户可以围绕同一个项目持续追问。

---

## Context Layering

RepoMind 将不同来源的上下文进行分层管理：

```text
project_report
memory_context
retrieved_context
```

| Context | Description |
|---|---|
| project_report | AI 项目导读，提供项目整体背景 |
| memory_context | 多轮对话历史，支持连续追问 |
| retrieved_context | 本轮问题检索到的源码上下文 |

这种设计避免所有上下文混在一起，也让 Agent 能够更清晰地区分项目概览、历史对话和本轮检索结果。

---

## Backend API

RepoMind 基于 FastAPI 构建后端服务。

### POST `/analyze`

负责 GitHub 仓库分析与索引构建。

```text
GitHub URL
    ↓
clone_repo
    ↓
scan_repo / scan_and_build_tree
    ↓
read_key_files
    ↓
analyze_repo
    ↓
generate_llm_report
    ↓
build_chroma_index
    ↓
save project state
```

主要输出：

- 项目名称
- 项目结构
- 技术栈分析
- AI 项目导读
- Chroma 向量索引
- 初始项目状态

### POST `/ask-v2`

负责 Agentic RAG 项目问答。

```text
question
    ↓
LangGraph Agent
    ↓
tool calling
    ↓
context collection
    ↓
retrieval grading
    ↓
query rewrite if needed
    ↓
answer with sources
```

### Project History APIs

RepoMind 基于 SQLite + SQLAlchemy 实现项目级持久化存储，支持：

- 保存已分析仓库
- 保存 AI 项目导读
- 保存历史问答记录
- 项目切换
- 报告恢复
- 对话恢复
- 历史项目继续追问

---

## Agent Trace

RepoMind 在关键节点输出 Agent Trace，方便调试和展示 Agent 行为。

示例：

```text
[Agent] question: 这个项目的 API 路由是怎么设计的？
[Agent] tool_calls: [...]
[Collect] context length: 9776
[Collect] sources: ['README.md', 'main.py', 'requirements.txt']
[Grade] is_relevant: True
[Grade] reason: 检索上下文包含完整 API 路由定义。
[Answer] answer length: 324
```

Agent Trace 可以帮助观察：

- 是否触发 Tool Calling
- 调用了哪些工具
- 检索到了哪些来源文件
- 检索结果是否相关
- 是否触发 Query Rewrite
- 最终回答是否生成成功

---

## Evaluation

RepoMind 提供最小 Eval 测试集，用于验证核心能力是否稳定。

文件结构：

```text
eval/eval_cases.json
scripts/run_eval.py
```

运行方式：

```bash
python -m scripts.run_eval
```

> 注意：Eval 脚本默认对本地已分析过的仓库 `data/repos/SimpleFastPyAPI` 运行
> （`data/` 不进版本库）。因此首次运行前，需要先在界面上分析一个仓库，
> 或修改 `scripts/run_eval.py` 里的 `REPO_PATH` 指向你自己的目标仓库目录。

当前 Eval 检查内容：

- 是否成功返回 answer
- answer 是否非空
- 是否包含 expected keywords
- 是否包含参考文件
- 是否出现异常

示例 case：

```json
{
  "id": "api_routes_001",
  "question": "这个项目的 API 路由是怎么设计的？",
  "expected_keywords": ["API", "路由", "GET", "POST"],
  "require_sources": true
}
```

示例输出：

```text
[Eval] Running api_routes_001
[PASS] api_routes_001

[Eval] Passed 6/6
```

---

## JD-Oriented Capabilities

| Agent Engineering Capability | Implementation in RepoMind |
|---|---|
| Agent Workflow | LangGraph StateGraph 多节点工作流 |
| Tool Calling | LangChain Tool + bind_tools + ToolNode |
| RAG | Chroma Semantic Search + HuggingFace Embeddings |
| Retrieval Quality Control | grade_documents 检索评估 |
| Query Optimization | rewrite_question 问题重写 |
| Memory | recent_turns + conversation_summary + key_findings |
| Backend Service | FastAPI endpoints |
| Persistence | SQLite + SQLAlchemy |
| Observability | Agent Trace 执行日志 |
| Evaluation | Minimal Eval regression scripts |
| Source Grounding | metadata-based source citation |
| Web Demo | HTML / JavaScript frontend |

---

## Demo Flow

1. 打开前端页面：

```text
http://127.0.0.1:8000
```

2. 输入 GitHub 仓库地址：

```text
https://github.com/BaseMax/SimpleFastPyAPI
```

3. 点击分析项目。

4. 围绕项目进行提问：

```text
这个项目主要解决什么问题？
```

```text
这个项目的 API 路由是怎么设计的？
```

```text
这个项目的数据模型和数据库连接分别在哪里实现？
```

5. 查看回答和参考文件：

```text
参考文件：
- main.py
- app/database.py
- app/models.py
```

---

## Local Setup

### 1. Clone Repository

```bash
git clone https://github.com/SquamuleWie0/RepoMind.git
cd RepoMind
```

### 2. Create Virtual Environment

推荐 Python 版本：

```text
Python 3.11 或 Python 3.12
```

创建虚拟环境：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

在项目根目录创建 `.env`：

```env
DEEPSEEK_API_KEY=your_deepseek_api_key
```

也可以参考 `.env.example`：

```env
DEEPSEEK_API_KEY=
```

### 4. Start Backend

```bash
uvicorn app.api:app --host 0.0.0.0 --port 8000
```

然后打开：

```text
http://127.0.0.1:8000
```

注意：分析仓库时不建议使用 `--reload`，因为克隆仓库和 Chroma 索引会写入 `data/repos`，可能触发自动重启。

---

## Current Capabilities

RepoMind 当前支持：

- GitHub 仓库克隆与扫描
- 项目结构分析
- AI 项目导读生成
- Chroma 代码语义索引
- LangGraph Tool Calling Agent
- 基于 metadata 的来源引用
- 检索结果评估 grade_documents
- 检索问题重写 rewrite_question
- 多轮对话 memory
- Agent trace 日志
- 最小 Eval 测试流程
- FastAPI + Web 前端 Demo
- SQLite + SQLAlchemy 项目历史持久化

---

## Limitations

当前版本仍有一些限制：

- 主要检索后端是 Chroma 语义检索
- Eval 仍是关键词和来源存在性检查
- Query Rewrite 当前最多重试一次
- Source Citation 当前是文件级引用，不包含行号
- 前端保持轻量，主要用于 Demo
- LangChain / Chroma 环境建议使用 Python 3.11 或 Python 3.12

---

## Roadmap

后续计划：

- 增加 keyword search / ripgrep tool
- 增加 repo tree inspection tool
- 增加 file reader tool，实现指定文件精读
- 将 source citation 扩展到行号级别
- 增加更丰富的 Eval 指标
- 增加 Docker 支持
- 在前端展示 Agent Trace
- 增加部署配置
- 支持更复杂的多仓库知识管理

---

## Summary

RepoMind 不是一个普通聊天机器人，而是一个围绕代码仓库理解场景构建的 Agentic RAG 工程项目。

它覆盖了 AI Agent 工程项目中的多个关键能力：

- Agentic Workflow 编排
- Tool Calling 工具调用
- RAG 检索增强生成
- Source Citation 来源引用
- Retrieval Grading 检索评估
- Query Rewriting 问题重写
- Multi-turn Memory 多轮记忆
- Agent Trace 可观测性
- Minimal Eval 回归测试
- FastAPI 服务化与 Web Demo

该项目目标是展示 AI Agent 在真实代码理解场景中的工程落地能力，适合作为 AI Agent 工程师、RAG 工程师、Python 后端 AI 应用开发相关岗位的项目展示。