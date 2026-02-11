FROM python:3.12-slim

WORKDIR /app

# Install Chromium, Xvfb (virtual display), and supporting packages
# Xvfb is required because SeleniumBase UC Mode cannot run headless —
# it needs a display to bypass Cloudflare Turnstile via uc_gui_click_captcha().
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium chromium-driver \
    xvfb xauth x11-utils xfonts-base \
    libxcomposite1 libxcursor1 libxdamage1 libxfixes3 \
    libxi6 libxrandr2 libxtst6 libxss1 \
    libglib2.0-0 libnss3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libgbm1 \
    libasound2 libpango-1.0-0 libcairo2 fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Install shared package
COPY shared/ /shared/
RUN pip install --no-cache-dir /shared/

# Install module requirements
COPY modules/myfitnesspal/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# myfitnesspal requires rich<13 but seleniumbase requires rich>=14.
# We only use myfitnesspal as a library (Client API), not its CLI,
# so rich is not needed at runtime.  Install it --no-deps and pull
# its actual runtime dependencies separately.
RUN pip install --no-cache-dir --no-deps myfitnesspal>=2.0 \
    && pip install --no-cache-dir \
       blessed lxml measurement python-dateutil \
       browser_cookie3 typing-extensions cloudscraper

# SeleniumBase needs to know where Chromium lives
ENV CHROME_BIN="/usr/bin/chromium"
ENV CHROMEDRIVER_PATH="/usr/bin/chromedriver"

# Copy application code
COPY modules/ /app/modules/

ENV PYTHONPATH="/app:/shared"

EXPOSE 8000

CMD ["uvicorn", "modules.myfitnesspal.main:app", "--host", "0.0.0.0", "--port", "8000"]
