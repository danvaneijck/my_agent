FROM python:3.12-slim

WORKDIR /app

# Install shared package
COPY shared/ /shared/
RUN pip install --no-cache-dir /shared/

# Install requirements
COPY dashboard/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY dashboard/ /app/dashboard/

ENV PYTHONPATH="/app:/shared"

EXPOSE 8501

CMD ["uvicorn", "dashboard.main:app", "--host", "0.0.0.0", "--port", "8501"]
