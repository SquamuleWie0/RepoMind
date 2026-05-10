import json
import re
from pathlib import Path

from code_searcher import search_code_with_plan
from llm_client import ask_deepseek
from query_planner import create_search_plan
from question_router import route_question
from result_evaluator import evaluate_search_result
from retrieval_router import route_retrieval
from vector_searcher import search_vector_index


def clean_answer(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def truncate_context(text: str, max_chars: int = 12000) -> str:
    if len(text) <= max_chars:
        return text

    return text[:max_chars] + "\n\n[上下文过长，已截断]"


def build_general_prompt(
    question: str,
    file_tree: str,
    analysis_result: dict | None,
    route_info: dict,
    memory_context: str = "",
) -> str:
    analysis_json = json.dumps(analysis_result or {}, ensure_ascii=False, indent=2)
    file_tree_preview = truncate_context(file_tree, max_chars=5000)

    return f"""
你是一个开源项目理解助手，正在帮助用户理解一个 GitHub 项目。

用户问题：

{question}

对话记忆上下文：

{memory_context}

问题路由判断：

{json.dumps(route_info, ensure_ascii=False, indent=2)}

项目规则分析结果：

{analysis_json}

项目文件树摘要：

{file_tree_preview}

回答要求：

- 第一句话直接回答用户问题，不要寒暄、不要铺垫。
- 优先用通俗语言解释；如果必须使用专业术语，要顺手解释一句。
- 根据问题选择最合适的表达形式，不要固定写成两三段说明文。
- 如果适合流程说明，可以用 A → B → C 的形式。
- 如果适合对比，可以用简短列表。
- 回答要精炼，但不要为了短而牺牲清楚。
- 重点帮助用户理解项目本身，不要主动深入代码细节。
- 可以用类比或“你可以把它理解成……”降低理解成本。
- 不要堆文件路径、函数名和术语；只有在对理解有帮助时才提关键文件。
- 对话记忆只作为参考，当前问题是新问题时不要强行关联历史。
- 不要写成论文、报告或代码审计。
- 不要编造上下文里没有依据的实现。
- 通常控制在 150 到 400 字；如果问题很简单，可以更短。
"""


def build_dev_prompt(
    question: str,
    file_tree: str,
    analysis_result: dict | None,
    route_info: dict,
    memory_context: str = "",
) -> str:
    analysis_json = json.dumps(analysis_result or {}, ensure_ascii=False, indent=2)
    file_tree_preview = truncate_context(file_tree, max_chars=5000)

    return f"""
你是一个开源项目开发助手，正在帮助用户判断如何学习、复刻或二次开发一个项目。

用户问题：

{question}

对话记忆上下文：

{memory_context}

问题路由判断：

{json.dumps(route_info, ensure_ascii=False, indent=2)}

项目规则分析结果：

{analysis_json}

项目文件树摘要：

{file_tree_preview}

回答要求：

- 第一句话直接回答用户问题，不要寒暄、不要铺垫。
- 回答要偏行动建议，告诉用户应该保留什么、可以先不做什么、下一步怎么尝试。
- 优先用通俗语言解释；如果必须使用专业术语，要顺手解释一句。
- 根据问题选择最合适的表达形式，不要固定写成两三段说明文。
- 如果适合，可以使用“先保留 / 暂时不做 / 下一步尝试”的结构。
- 如果适合流程说明，可以用 A → B → C。
- 回答要现实、可执行，不要好高骛远，不要建议大规模重构。
- 不要堆代码细节，除非用户明确要求。
- 对话记忆只作为参考，当前问题是新需求时不要强行关联历史。
- 回答要精炼，但不要为了短而牺牲清楚。
- 不要写成论文、报告或空泛建议。
- 不要编造上下文里没有依据的实现。
- 通常控制在 150 到 400 字；如果问题很简单，可以更短。
"""


def build_code_prompt(
    question: str,
    search_plan: dict,
    retrieval_route: dict,
    search_context: str,
    evaluation_result: dict,
    memory_context: str = "",
) -> str:
    search_context = truncate_context(search_context)

    return f"""
你是一个开源项目理解助手，正在帮助用户理解一个 GitHub 项目。

你的核心任务是：先回答用户真正问的问题。检索到的文件、函数、代码片段只是辅助证据，不是回答主体。

用户问题：

{question}

对话记忆上下文：

{memory_context}

搜索计划：

{json.dumps(search_plan, ensure_ascii=False, indent=2)}

检索方式判断：

{json.dumps(retrieval_route, ensure_ascii=False, indent=2)}

检索结果评估：

{json.dumps(evaluation_result, ensure_ascii=False, indent=2)}

检索到的项目上下文：

{search_context}

回答要求：

- 第一句话直接回答用户问题，不要寒暄、不要铺垫。
- 先给结论，再解释关键原因。
- 优先用通俗语言解释；如果必须使用专业术语，要顺手解释一句。
- 根据问题选择最合适的表达形式，不要固定写成两三段说明文。
- 如果问题适合流程说明，优先用调用链形式，例如：入口 → 处理函数 → 核心逻辑。
- 可以提到关键文件、函数或模块，但只提最关键的 1 到 3 个。
- 不要把检索到的代码逐段复述，要提炼出用户真正需要的结论。
- 检索到的内容只是依据，不是回答主体。
- 对话记忆只作为参考，当前问题是新问题时不要强行关联历史。
- 如果上下文仍不足，就自然说明，不要让不确定性盖过回答本身。
- 回答要精炼，但不要为了短而牺牲清楚。
- 不要写成代码审计报告。
- 不要编造上下文里没有依据的实现。
- 通常控制在 150 到 400 字；如果问题很简单，可以更短。
"""


def build_hybrid_context(
    repo_path: str | Path,
    question: str,
    search_plan: dict,
    retrieval_route: dict,
    vector_index: dict | None,
) -> str:
    method = retrieval_route.get("method", "hybrid")
    sections = []

    if method in {"rg", "hybrid"}:
        rg_context = search_code_with_plan(
            repo_path=repo_path,
            plan=search_plan,
        )
        sections.append("【ripgrep 关键词检索结果】\n" + rg_context)

    if method in {"vector", "hybrid"}:
        vector_query = retrieval_route.get("semantic_query") or question
        vector_context = search_vector_index(
            query=vector_query,
            vector_index=vector_index,
        )
        sections.append("【向量语义检索结果】\n" + vector_context)

    if not sections:
        rg_context = search_code_with_plan(
            repo_path=repo_path,
            plan=search_plan,
        )
        sections.append("【兜底 ripgrep 检索结果】\n" + rg_context)

    return "\n\n".join(sections)


def answer_question(
    repo_path: str | Path,
    question: str,
    file_tree: str = "",
    analysis_result: dict | None = None,
    memory_context: str = "",
    vector_index: dict | None = None,
) -> str:
    route_info = route_question(
        question=question,
        file_tree=file_tree,
        analysis_result=analysis_result,
        memory_context=memory_context,
    )

    route = route_info.get("route", "general_understanding")
    needs_code_search = route_info.get("needs_code_search", False)

    if not needs_code_search:
        if route == "dev_suggestion":
            prompt = build_dev_prompt(
                question=question,
                file_tree=file_tree,
                analysis_result=analysis_result,
                route_info=route_info,
                memory_context=memory_context,
            )
        else:
            prompt = build_general_prompt(
                question=question,
                file_tree=file_tree,
                analysis_result=analysis_result,
                route_info=route_info,
                memory_context=memory_context,
            )

        answer = ask_deepseek(prompt)
        return clean_answer(answer)

    search_plan = create_search_plan(
        question=question,
        file_tree=file_tree,
        analysis_result=analysis_result,
    )

    retrieval_route = route_retrieval(
        question=question,
        route_info=route_info,
        analysis_result=analysis_result,
        memory_context=memory_context,
    )

    first_context = build_hybrid_context(
        repo_path=repo_path,
        question=question,
        search_plan=search_plan,
        retrieval_route=retrieval_route,
        vector_index=vector_index,
    )

    evaluation_result = evaluate_search_result(
        question=question,
        search_plan=search_plan,
        search_context=first_context,
    )

    final_context = first_context

    if not evaluation_result.get("is_sufficient", True):
        follow_up_plan = evaluation_result.get("follow_up_plan", {})
        has_follow_up_terms = follow_up_plan.get("primary_terms") or follow_up_plan.get("fallback_terms")

        if has_follow_up_terms:
            second_context = search_code_with_plan(
                repo_path=repo_path,
                plan=follow_up_plan,
            )

            final_context = (
                "【第一轮检索结果】\n"
                f"{first_context}\n\n"
                "【第二轮补充检索结果】\n"
                f"{second_context}"
            )

    prompt = build_code_prompt(
        question=question,
        search_plan=search_plan,
        retrieval_route=retrieval_route,
        search_context=final_context,
        evaluation_result=evaluation_result,
        memory_context=memory_context,
    )

    answer = ask_deepseek(prompt)
    return clean_answer(answer)