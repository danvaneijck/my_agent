FROM python:3.12-slim

WORKDIR /app

# Install shared package
COPY shared/ /shared/
RUN pip install --no-cache-dir /shared/

# Install module requirements
COPY modules/git_platform/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (only this module)
COPY modules/__init__.py /app/modules/__init__.py
COPY modules/git_platform/ /app/modules/git_platform/

ENV PYTHONPATH="/app:/shared"

EXPOSE 8000

CMD ["uvicorn", "modules.git_platform.main:app", "--host", "0.0.0.0", "--port", "8000"]
