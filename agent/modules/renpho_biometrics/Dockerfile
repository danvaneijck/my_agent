FROM python:3.12-slim

WORKDIR /app

# Install shared package
COPY shared/ /shared/
RUN pip install --no-cache-dir /shared/

# Install requirements
COPY modules/renpho_biometrics/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (only this module)
COPY modules/__init__.py /app/modules/__init__.py
COPY modules/renpho_biometrics/ /app/modules/renpho_biometrics/

ENV PYTHONPATH="/app:/shared"

EXPOSE 8000

CMD ["uvicorn", "modules.renpho_biometrics.main:app", "--host", "0.0.0.0", "--port", "8000"]
