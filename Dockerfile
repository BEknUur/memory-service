FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md CHANGELOG.md alembic.ini ./
COPY migrations ./migrations
COPY src ./src

RUN pip install --no-cache-dir .

EXPOSE 8080

CMD ["sh", "-c", "alembic upgrade head && uvicorn memory_service.main:app --host 0.0.0.0 --port 8080"]