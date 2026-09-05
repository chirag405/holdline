# Holdline on Amazon Bedrock AgentCore Runtime.
FROM public.ecr.aws/docker/library/python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY pyproject.toml requirements.lock.txt ./
COPY src ./src
RUN pip install -e ".[agentcore]"

COPY deploy/agentcore/app.py ./app.py

# AgentCore Runtime speaks HTTP/WebSocket to the container on 8080.
EXPOSE 8080
ENV STATE_BACKEND=dynamodb MEMORY_BACKEND=agentcore USE_GRAPH=true

CMD ["python", "app.py"]
