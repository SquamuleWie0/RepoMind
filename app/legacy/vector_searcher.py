from embedding_indexer import cosine_similarity, vectorize


def search_vector_index(
    query: str,
    vector_index: dict | None,
    top_k: int = 6,
    max_chars: int = 9000,
) -> str:
    """
    语义检索模块。
    根据 query 在本地向量索引中找相关文本块。
    """
    if not vector_index:
        return "没有可用的向量索引。"

    chunks = vector_index.get("chunks", [])

    if not chunks:
        return "向量索引为空。"

    query_vector = vectorize(query)

    if not query_vector:
        return "查询内容无法向量化。"

    scored_chunks = []

    for chunk in chunks:
        score = cosine_similarity(query_vector, chunk.get("vector"))

        if score <= 0:
            continue

        scored_chunks.append(
            {
                "score": score,
                "relative_path": chunk["relative_path"],
                "start_line": chunk["start_line"],
                "end_line": chunk["end_line"],
                "content": chunk["content"],
            }
        )

    scored_chunks.sort(key=lambda item: item["score"], reverse=True)
    selected = scored_chunks[:top_k]

    if not selected:
        return "没有找到语义相关的项目片段。"

    sections = []
    total_chars = 0

    for item in selected:
        section = (
            f"## 文件：{item['relative_path']}\n"
            f"- 行号范围：{item['start_line']} - {item['end_line']}\n"
            f"- 相似度：{item['score']:.3f}\n\n"
            f"```text\n{item['content']}\n```"
        )

        if total_chars + len(section) > max_chars:
            break

        sections.append(section)
        total_chars += len(section)

    return "\n\n".join(sections)