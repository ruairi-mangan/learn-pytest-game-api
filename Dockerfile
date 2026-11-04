FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first, so Docker can cache this layer between code changes.
COPY pyproject.toml README.md LICENSE ./
COPY api ./api
RUN pip install -e ".[test]"

COPY tests ./tests

EXPOSE 5000
CMD ["flask", "--app", "api.mockapi:create_app()", "run", "--host", "0.0.0.0", "--port", "5000"]
