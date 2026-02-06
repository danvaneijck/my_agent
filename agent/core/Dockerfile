FROM python:3.12-slim

WORKDIR /app

# Install shared package
COPY shared/ /shared/
RUN pip install --no-cache-dir /shared/

# Install core requirements
COPY core/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY core/ /app/core/
COPY alembic.ini /app/
COPY alembic/ /app/alembic/
COPY cli.py /app/

# Add shared to PYTHONPATH
ENV PYTHONPATH="/app:/shared"

EXPOSE 8000

CMD ["uvicorn", "core.main:app", "--host", "0.0.0.0", "--port", "8000"]
