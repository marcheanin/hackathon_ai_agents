FROM python:3.11-slim

WORKDIR /app

COPY src/ src/

RUN pip install --no-cache-dir \
    fastapi>=0.110.0 \
    uvicorn[standard]>=0.27.0 \
    pydantic>=2.6.0 \
    pydantic-settings>=2.1.0 \
    asyncpg>=0.29.0 \
    structlog>=24.1.0 \
    httpx>=0.27.0 \
    langchain>=0.1.0 \
    langchain-community>=0.0.20 \
    langgraph

ENV PYTHONPATH=/app/src

COPY scripts/ scripts/
COPY migrations/ migrations/

EXPOSE 8000

CMD ["uvicorn", "analyst.main:app", "--host", "0.0.0.0", "--port", "8000"]

