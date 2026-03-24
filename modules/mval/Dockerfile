FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir .

COPY scripts/ scripts/
COPY migrations/ migrations/

EXPOSE 8000

CMD ["uvicorn", "mval.main:app", "--host", "0.0.0.0", "--port", "8000"]
