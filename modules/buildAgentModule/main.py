import os
import json
from typing import Optional
from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from rag_tool import rag_search
import time
import random
# =========================
# CONFIG
# =========================
BASE_DIR = os.path.abspath("./repo")

llm = ChatOpenAI(
    model="qwen/qwen3-4b-thinking-2507",
    api_key="",
    base_url="http://127.0.0.1:1234/v1",
)


# =========================
# SAFE FS LAYER
# =========================
def _safe_path(path: str) -> str:
    """Force path to stay inside repo (no crash)"""

    # убираем абсолютные пути
    if os.path.isabs(path):
        path = path.lstrip("/")

    # убираем ../
    path = os.path.normpath(path)

    # если всё ещё пытается выйти — просто обрезаем
    while path.startswith(".."):
        path = path[3:]

    full_path = os.path.abspath(os.path.join(BASE_DIR, path))

    # финальная защита (но без падения)
    if not full_path.startswith(BASE_DIR):
        # fallback — пишем в корень repo
        full_path = os.path.join(BASE_DIR, os.path.basename(path))

    return full_path


def write_file(path: str, content: str) -> str:
    """Write file inside repo"""
    full_path = _safe_path(path)

    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)

    return f"Written: {path}"


def read_file(path: str) -> str:
    """Read file inside repo"""
    full_path = _safe_path(path)

    if not os.path.exists(full_path):
        return "File does not exist"

    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()


def list_files(path: str = "") -> list:
    """List files inside repo"""
    full_path = _safe_path(path if path else ".")

    result = []
    for root, dirs, files in os.walk(full_path):
        for name in files:
            rel = os.path.relpath(os.path.join(root, name), BASE_DIR)
            result.append(rel)

    return result


# =========================
# SYSTEM PROMPT
# =========================
SYSTEM_PROMPT = """
Ты AI агент, который генерирует код агентов из JSON архитектуры.

ОБЯЗАТЕЛЬНЫЙ процесс:

1. Сначала вызови write_todos чтобы создать план
2. Затем выполняй шаги СТРОГО по одному
3. Каждый шаг:
   - подумай (reasoning)
   В ответе на первый шаг agent должен ответить строго так:

{"name":"write_todos","arguments":{"todos":[{"content":"...","status":"pending"}]}}

Никаких пояснений, маркдауна или текста вокруг JSON!
   - сгенерируй код
   - вызови write_file

ПРАВИЛА:

- НЕ генерируй всё сразу
- 1 шаг = 1 файл или изменение
- ВСЕ файлы должны быть внутри repo
- Используй read_file перед изменением
- Код должен быть рабочим
- Делай модульную структуру

Никаких пояснений, reasoning, markdown или текста вокруг JSON
Если не уверен — делай простой рабочий вариант

У тебя есть инструмент `rag_search(query)` который возвращает релевантные фрагменты из документальной
базы. Используй его когда нужно уточнить информацию или добыть документный контекст.

ЦЕЛЬ:
Создать полностью рабочий Python проект агентов
"""


# =========================
# AGENT
# =========================
def create_agent():
    return create_deep_agent(
        tools=[write_file, read_file, list_files, rag_search],
        system_prompt=SYSTEM_PROMPT,
        model=llm
    )


# =========================
# RUNNER
# =========================



def run_agent(json_input: dict, max_retries: int = 5):
    os.makedirs(BASE_DIR, exist_ok=True)

    agent = create_agent()

    input_data = {
        "messages": [
            {
                "role": "user",
                "content": f"""
Сгенерируй проект агентов по следующему JSON:

{json.dumps(json_input, indent=2)}
"""
            }
        ]
    }

    print("🚀 Starting agent...\n")

    for attempt in range(max_retries):
        try:
            for chunk in agent.stream(input_data, stream_mode="values"):
                if "messages" in chunk:
                    msg = chunk["messages"][-1]

                    content = getattr(msg, "content", None)
                    if content:
                        print(content)

            return

        except Exception as e:
            error_str = str(e)

            if "429" in error_str or "rate_limit" in error_str:
                wait_time = (2 ** attempt) + random.uniform(0, 1)

                print(f"\n⚠️ Rate limit. Retry {attempt + 1}/{max_retries} in {wait_time:.2f}s...\n")
                time.sleep(wait_time)
            else:
                raise e

    raise RuntimeError("❌ Max retries exceeded")


# =========================
# CLI
# =========================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, required=True, help="Path to JSON file")

    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    run_agent(data)