FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 7860

# Ollama 跑在 host 上：執行容器時加 --add-host=host.docker.internal:host-gateway
# 並設定 -e OLLAMA_BASE_URL=http://host.docker.internal:11434
ENV OLLAMA_BASE_URL=http://host.docker.internal:11434

CMD ["python", "cli.py", "ui"]
