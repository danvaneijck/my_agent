FROM python:3.12-slim

WORKDIR /app

# Install shared package
COPY shared/ /shared/
RUN pip install --no-cache-dir /shared/

# Install requirements
COPY comms/slack_bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY comms/ /app/comms/

ENV PYTHONPATH="/app:/shared"

CMD ["python", "-m", "comms.slack_bot.main"]
