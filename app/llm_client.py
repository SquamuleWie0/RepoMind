# 统一封装 DeepSeek API 调用

import os
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


def get_deepseek_client() -> OpenAI:
    api_key = os.getenv("DEEPSEEK_API_KEY")

    if not api_key:
        raise ValueError("未找到 DEEPSEEK_API_KEY，请检查根目录 .env 文件")

    return OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",
    )


def ask_deepseek(prompt: str) -> str:
    client = get_deepseek_client()

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "你是一个专业的软件项目分析助手。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )

    return response.choices[0].message.content