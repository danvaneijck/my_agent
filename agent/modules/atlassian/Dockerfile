FROM python:3.12-slim

WORKDIR /app

# Install shared package
COPY shared/ /shared/
RUN pip install --no-cache-dir /shared/

# Install module requirements
COPY modules/atlassian/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (only this module)
COPY modules/__init__.py /app/modules/__init__.py
COPY modules/atlassian/ /app/modules/atlassian/

ENV PYTHONPATH="/app:/shared"

EXPOSE 8000

CMD ["uvicorn", "modules.atlassian.main:app", "--host", "0.0.0.0", "--port", "8000"]
