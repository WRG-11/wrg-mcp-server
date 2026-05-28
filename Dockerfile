FROM python:3.12-slim

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

EXPOSE 8080

CMD ["sh", "-c", "wrg-mcp-server --transport ${MCP_TRANSPORT:-stdio} --host ${MCP_HOST:-127.0.0.1} --port ${PORT:-8080} --mcp-path ${MCP_PATH:-/mcp}"]
