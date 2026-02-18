FROM python:3.12-slim

WORKDIR /app

# Install shared package
COPY shared/ /shared/
RUN pip install --no-cache-dir /shared/

# Install requirements
COPY modules/file_manager/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (only this module)
COPY modules/__init__.py /app/modules/__init__.py
COPY modules/file_manager/ /app/modules/file_manager/

ENV PYTHONPATH="/app:/shared"

EXPOSE 8000

CMD ["uvicorn", "modules.file_manager.main:app", "--host", "0.0.0.0", "--port", "8000"]
