FROM python:3.12-slim

WORKDIR /app

# Install useful CLI tools for shell command execution
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    jq \
    bc \
    && rm -rf /var/lib/apt/lists/*

# Install shared package
COPY shared/ /shared/
RUN pip install --no-cache-dir /shared/

# Install requirements
COPY modules/code_executor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY modules/ /app/modules/

ENV PYTHONPATH="/app:/shared"

EXPOSE 8000

CMD ["uvicorn", "modules.code_executor.main:app", "--host", "0.0.0.0", "--port", "8000"]
