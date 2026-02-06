FROM python:3.12-slim

WORKDIR /app

# Install useful CLI tools and matplotlib system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    jq \
    bc \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

# Pre-configure matplotlib for non-interactive use
ENV MPLBACKEND=Agg

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
