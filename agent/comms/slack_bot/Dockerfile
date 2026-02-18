FROM python:3.12-slim

WORKDIR /app

# Install shared package
COPY shared/ /shared/
RUN pip install --no-cache-dir /shared/

# Install requirements
COPY comms/slack_bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (only this bot)
COPY comms/__init__.py /app/comms/__init__.py
COPY comms/slack_bot/ /app/comms/slack_bot/

ENV PYTHONPATH="/app:/shared"

CMD ["python", "-m", "comms.slack_bot.main"]
