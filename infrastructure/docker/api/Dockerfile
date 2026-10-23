FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY services/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/api .
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
# Apply versioned, idempotent migrations before starting the API.
# Alembic exits nonzero if a migration fails, preventing a half-updated API.
CMD ["sh", "-c", "alembic -c alembic.ini upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
