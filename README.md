# RepoMind

RepoMind 是一个面向 GitHub 开源项目理解场景的 Agentic RAG 系统。

与普通聊天机器人不同的，RepoMind是一个围绕代码仓库理解场景构建的 Agent 工程项目：用户输入 GitHub 仓库地址后，系统会自动克隆仓库、扫描文件、生成项目导读、构建 Chroma 语义索引，并通过 LangGraph Tool Calling Agent 对项目进行问答。

当前版本已支持：

- GitHub 仓库克隆与文件扫描
- AI 项目导读生成
- Chroma 代码语义索引
- LangGraph Tool Calling Agent
- metadata / source citation 来源引用
- grade_documents 检索结果评估
- rewrite_question 检索问题重写
- 多轮对话 memory
- Agent trace 执行日志
- FastAPI 后端服务
- Web 前端 Demo
- 最小 Eval 测试集

---

## 1. 项目定位

RepoMind 的目标是帮助用户快速理解一个陌生 GitHub 项目。

典型使用流程：

```text
输入 GitHub URL
→ 分析项目结构
→ 生成 AI 项目导读
→ 构建 Chroma 代码语义索引
→ 围绕项目进行自然语言提问
→ Agent 自动调用检索工具
→ 基于源码上下文生成回答
→ 返回参考文件来源
```

适用场景：

- 快速理解陌生 GitHub 项目
- 分析项目架构、核心流程和模块关系
- 定位具体功能的实现文件
- 基于源码上下文进行可追溯问答
- 对比不同项目的技术栈和实现方式
- 辅助技术调研、开源学习、面试准备和二次开发
- 作为 Agentic RAG / Tool Calling / Eval 的工程实践项目

---

## 2. 技术栈

| 层级 | 技术 |
|---|---|
| 后端服务 | FastAPI |
| Agent 编排 | LangGraph |
| LLM 框架 | LangChain |
| 大模型接口 | DeepSeek API |
| 向量数据库 | Chroma |
| Embedding | HuggingFace Embeddings |
| RAG 检索 | Chroma Semantic Search |
| 前端 | HTML / JavaScript |
| 测试评估 | 自定义最小 Eval 脚本 |

---

## 3. 系统架构

```text
Frontend
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

/ask-v2
  ↓
LangGraph Agent
  ↓
Tool Calling
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
```

---

## 4. `/analyze` 项目分析流程

`POST /analyze` 负责项目分析和索引构建。

流程：

```text
GitHub URL
→ clone_repo
→ scan_repo / scan_and_build_tree
→ read_key_files
→ analyze_repo
→ generate_llm_report
→ build_chroma_index
→ save CURRENT_PROJECT state
```

主要输出：

- 项目名称
- 项目类型
- 技术栈
- AI 项目导读
- Chroma 向量索引
- 初始 memory 状态

---

## 5. `/ask-v2` Agentic RAG 流程

`POST /ask-v2` 负责项目问答。

当前 LangGraph 主流程：

```text
agent
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

### 5.1 Tool Calling

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

### 5.2 Source Citation 来源引用

Chroma 检索结果不再只是普通文本，而是结构化结果：

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

最终回答会附带参考文件：

```text
参考文件：
- main.py
- app/database.py
```

这让回答更加可追溯，也降低模型编造文件来源的风险。

### 5.3 Retrieval Grading 检索评估

`grade_documents_node` 会判断检索结果是否足够回答用户问题。

输出结构：

```json
{
  "is_relevant": true,
  "reason": "检索上下文包含 API 路由定义，足以回答问题。"
}
```

价值：

- 避免拿不相关上下文强行回答
- 让 Agent 具备检索结果反思能力
- 为 query rewrite 提供依据

### 5.4 Query Rewrite 问题重写

如果检索结果不相关，Agent 会触发问题重写：

```text
original_question
+ current_query
+ grade_reason
+ retrieved_context summary
→ rewritten_question
```

然后重新回到 agent，再次触发检索。

为避免无限循环，系统使用 `rewrite_count` 控制重写次数，当前最多重写一次。

---

## 6. Memory 多轮对话记忆

RepoMind 维护基础多轮对话记忆：

- `recent_turns`：保存最近问答
- `conversation_summary`：压缩较早对话
- `key_findings`：保存关键结论

在 `/ask-v2` 中，系统会将 memory 转为 `memory_context`，传入 Agent 回答节点，使连续追问可以复用历史上下文。

---

## 7. Agent Trace 执行日志

RepoMind 在关键节点输出执行日志，方便调试和展示 Agent 行为。

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

这些日志可以帮助判断：

- 是否触发 Tool Calling
- 调用了哪些工具
- 检索到了哪些来源文件
- 检索结果是否相关
- 是否触发 query rewrite
- 最终回答是否生成

---

## 8. Eval 最小测试集

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

## 9. 本地运行

### 9.1 克隆项目

```bash
git clone https://github.com/SquamuleWie0/RepoMind.git
cd RepoMind
```

### 9.2 创建虚拟环境

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

### 9.3 配置环境变量

在项目根目录创建 `.env`：

```env
DEEPSEEK_API_KEY=your_deepseek_api_key
```

也可以提供 `.env.example`：

```env
DEEPSEEK_API_KEY=
```

### 9.4 启动后端

```bash
uvicorn app.api:app
```

然后打开：

```text
http://127.0.0.1:8000
```

注意：分析仓库时不建议使用 `--reload`，因为克隆仓库和 Chroma 索引会写入 `data/repos`，可能触发自动重启。

---

## 10. Demo 流程

1. 打开前端页面：

```text
http://127.0.0.1:8000
```

2. 输入 GitHub 仓库地址，例如：

```text
https://github.com/BaseMax/SimpleFastPyAPI
```

3. 点击分析项目。

4. 提问：

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

## 11. 当前能力

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

---

## 12. 当前限制

当前版本仍有一些限制：

- 主要检索后端是 Chroma 语义检索
- Eval 仍是关键词和来源存在性检查
- Query rewrite 当前最多重试一次
- Source citation 当前是文件级引用，不包含行号
- 前端保持轻量，主要用于 Demo
- LangChain / Chroma 环境建议使用 Python 3.11 或 3.12

---

## 13. Roadmap

后续计划：

### 检索与工具层增强

- 增加 keyword search / ripgrep tool，补充语义检索之外的精确关键词检索能力
- 增加 repo tree inspection tool，用于查看项目目录结构
- 增加 file reader tool，实现指定文件精读
- 将 source citation 扩展到行号级别

### Eval 与可观测性

- 增加更丰富的 Eval 指标，例如 source 命中率、rewrite 触发率、回答稳定性等
- 在前端展示 Agent trace，方便观察 tool call、grade_documents、rewrite_question 等执行过程
- 保存每轮问答的 sources、grade 结果和 rewrite 记录，提升可复盘性

### 项目历史与工作台

- 接入 SQLite / SQLAlchemy，实现项目分析历史、AI 导读和对话记录持久化
- 增加左侧项目历史栏，支持切换已分析仓库并继续追问

### 工程化与部署

- 增加 Docker 支持
- 增加部署配置

---

## 14. 项目亮点

RepoMind 是一个基于 LangChain / LangGraph Tool Calling 的 GitHub 代码仓库理解 Agent。

它覆盖了 Agent 工程项目中的多个关键能力：

- Tool abstraction 工具抽象
- Agentic RAG 编排
- Chroma 语义检索
- metadata / source citation 来源引用
- Retrieval grading 检索质量评估
- Query rewriting 问题重写
- Multi-turn memory 多轮上下文
- Agent trace 可观测性
- Minimal Eval 回归测试
- FastAPI 服务化与前端 Demo

这个项目的目标不是做一个普通聊天机器人，而是围绕代码仓库理解场景，构建一个可展示、可解释、可评测的 Agentic RAG 工程项目。
