FROM python:3.12-slim

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

EXPOSE 8080

CMD ["sh", "-c", "wrg-mcp-server --transport streamable-http --host 0.0.0.0 --port ${PORT:-8080} --mcp-path /mcp"]
