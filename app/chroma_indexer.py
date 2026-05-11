from pathlib import Path
import hashlib

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings


IGNORE_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    "target",
    "dist",
    "build",
    ".venv",
    "venv",
    ".repomind",
}

INDEX_SUFFIXES = {
    ".py",
    ".rs",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".go",
    ".java",
    ".md",
    ".toml",
    ".json",
    ".yml",
    ".yaml",
    ".txt",
}

INDEX_FILE_NAMES = {
    "README",
    "README.md",
    "Cargo.toml",
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "go.mod",
    "pom.xml",
}

_embedding_model = None


def get_embedding_model():
    """
    本地 embedding 模型。
    使用全局缓存，避免每次检索都重新加载模型权重。
    """
    global _embedding_model

    if _embedding_model is None:
        _embedding_model = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

    return _embedding_model

def should_index_file(file_path: Path) -> bool:
    if set(file_path.parts) & IGNORE_DIRS:
        return False

    if file_path.name in INDEX_FILE_NAMES:
        return True

    return file_path.suffix in INDEX_SUFFIXES


def safe_collection_name(repo_path: str | Path) -> str:
    raw = str(Path(repo_path).resolve())
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]
    return f"repomind_{digest}"


def read_repo_documents(repo_path: str | Path) -> list[Document]:
    repo_path = Path(repo_path).resolve()
    documents: list[Document] = []

    for file_path in repo_path.rglob("*"):
        if not file_path.is_file():
            continue

        if not should_index_file(file_path):
            continue

        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        if not text.strip():
            continue

        relative_path = str(file_path.relative_to(repo_path))

        documents.append(
            Document(
                page_content=text,
                metadata={
                    "source": relative_path,
                    "path": relative_path,
                },
            )
        )

    return documents


def split_documents(documents: list[Document]) -> list[Document]:
    """
    将长文件切成适合检索的小块。
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
    )

    return splitter.split_documents(documents)


def build_chroma_index(repo_path: str | Path) -> Chroma:
    """
    为当前项目构建 Chroma 向量索引。
    """
    repo_path = Path(repo_path).resolve()
    persist_dir = repo_path / ".repomind" / "chroma"

    documents = read_repo_documents(repo_path)

    if not documents:
        raise RuntimeError("没有可索引的项目文件。")

    chunks = split_documents(documents)

    if not chunks:
        raise RuntimeError("文档切块为空。")

    embeddings = get_embedding_model()
    collection_name = safe_collection_name(repo_path)

    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=collection_name,
        persist_directory=str(persist_dir),
    )

    return vector_store


def load_chroma_index(repo_path: str | Path) -> Chroma:
    """
    加载已经构建过的 Chroma 索引。
    """
    repo_path = Path(repo_path).resolve()
    persist_dir = repo_path / ".repomind" / "chroma"

    embeddings = get_embedding_model()
    collection_name = safe_collection_name(repo_path)

    return Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=str(persist_dir),
    )


def search_chroma(
    repo_path: str | Path,
    query: str,
    top_k: int = 6,
) -> str:
    """
    根据用户问题进行语义检索，返回相关项目片段。
    """
    vector_store = load_chroma_index(repo_path)

    docs = vector_store.similarity_search(
        query=query,
        k=top_k,
    )

    if not docs:
        return "没有找到相关语义片段。"

    sections = []

    for index, doc in enumerate(docs, start=1):
        source = doc.metadata.get("source", "unknown")

        sections.append(
            f"## 片段 {index}: {source}\n\n"
            f"```text\n{doc.page_content}\n```"
        )

    return "\n\n".join(sections)

def search_chroma_with_sources(
    repo_path: str | Path,
    query: str,
    top_k: int = 6,
) -> dict:
    """
    根据用户问题进行语义检索，返回结构化检索结果：
    - context: 给 LLM 使用的上下文文本
    - sources: 去重后的来源文件列表
    - chunks: 每个检索片段的结构化信息
    """
    vector_store = load_chroma_index(repo_path)

    docs = vector_store.similarity_search(
        query=query,
        k=top_k,
    )

    if not docs:
        return {
            "context": "没有找到相关语义片段。",
            "sources": [],
            "chunks": [],
        }

    chunks = []
    sources = []

    for index, doc in enumerate(docs, start=1):
        source = (
            doc.metadata.get("source")
            or doc.metadata.get("path")
            or "unknown"
        )

        content = doc.page_content.strip()

        chunks.append(
            {
                "index": index,
                "source": source,
                "content": content,
            }
        )

        if source not in sources:
            sources.append(source)

    context_parts = []

    for chunk in chunks:
        context_parts.append(
            f"## 片段 {chunk['index']}\n"
            f"来源文件：{chunk['source']}\n\n"
            f"```text\n{chunk['content']}\n```"
        )

    return {
        "context": "\n\n".join(context_parts),
        "sources": sources,
        "chunks": chunks,
    }


def test_chroma(repo_path: str):
    print("[Chroma] building index...")
    build_chroma_index(repo_path)

    print("[Chroma] searching...")
    result = search_chroma(
        repo_path=repo_path,
        query="How does this project handle tasks or commands?",
    )

    print(result[:3000])


if __name__ == "__main__":
    test_chroma("data/repos/squad")