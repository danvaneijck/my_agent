FROM python:3.12-slim

WORKDIR /app

# Install Chromium and chromedriver for Selenium-based MFP authentication
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Install shared package
COPY shared/ /shared/
RUN pip install --no-cache-dir /shared/

# Install module requirements
COPY modules/myfitnesspal/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY modules/ /app/modules/

ENV PYTHONPATH="/app:/shared"

EXPOSE 8000

CMD ["uvicorn", "modules.myfitnesspal.main:app", "--host", "0.0.0.0", "--port", "8000"]
