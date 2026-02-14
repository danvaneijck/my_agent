FROM python:3.12-slim

WORKDIR /app

# Install Docker CLI (needed to manage sibling containers via mounted socket)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg && \
    install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg \
        -o /etc/apt/keyrings/docker.asc && \
    chmod a+r /etc/apt/keyrings/docker.asc && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
        https://download.docker.com/linux/debian bookworm stable" \
        > /etc/apt/sources.list.d/docker.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends docker-ce-cli docker-compose-plugin && \
    rm -rf /var/lib/apt/lists/*

# Install shared package
COPY shared/ /shared/
RUN pip install --no-cache-dir /shared/

# Install module requirements
COPY modules/deployer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY modules/ /app/modules/

ENV PYTHONPATH="/app:/shared"

EXPOSE 8000

CMD ["uvicorn", "modules.deployer.main:app", "--host", "0.0.0.0", "--port", "8000"]
