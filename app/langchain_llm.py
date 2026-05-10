import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()


def get_deepseek_llm():
    api_key = os.getenv("DEEPSEEK_API_KEY")

    if not api_key:
        raise RuntimeError("缺少环境变量 DEEPSEEK_API_KEY")

    return ChatOpenAI(
        model="deepseek-chat",
        api_key=api_key,
        base_url="https://api.deepseek.com",
        temperature=0.2,
    )


def ask_with_langchain(prompt: str) -> str:
    llm = get_deepseek_llm()

    prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "你是 RepoMind 的 Agent 助手，回答要简洁、准确、基于上下文。",
            ),
            ("human", "{input}"),
        ]
    )

    chain = prompt_template | llm
    response = chain.invoke({"input": prompt})

    return response.content.strip()


def test_langchain_llm():
    answer = ask_with_langchain(
        "用一句话解释 LangChain 在 Agent 项目里的作用。"
    )

    print(answer)


if __name__ == "__main__":
    test_langchain_llm()