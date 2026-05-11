# Legacy Modules

This folder contains earlier experimental modules from previous RepoMind iterations, including old retrieval routing, QA agent logic, patch generation, runner, and error analysis modules.

The current main workflow is implemented in:

- `app/api.py`
- `app/langgraph_agent.py`
- `app/chroma_indexer.py`
- `app/langchain_llm.py`
- `app/memory_manager.py`

These legacy files are kept for reference and are not part of the current FastAPI + LangGraph Agentic RAG pipeline.
