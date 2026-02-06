FROM python:3.11-slim

WORKDIR /app

COPY services/api/pyproject.toml .
RUN pip install --no-cache-dir fastapi uvicorn psycopg2-binary

COPY services/api/src ./src

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
