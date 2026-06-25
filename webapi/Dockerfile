# Build context = the "Football Analysts" project root.
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml requirements.txt ./
COPY football_analyst ./football_analyst
COPY webapi ./webapi
RUN pip install --no-cache-dir -e . && \
    pip install --no-cache-dir fastapi "uvicorn[standard]" "httpx>=0.27"
EXPOSE 8001
CMD ["uvicorn", "webapi.app:app", "--host", "0.0.0.0", "--port", "8001"]
