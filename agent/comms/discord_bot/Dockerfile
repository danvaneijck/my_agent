FROM python:3.12-slim

WORKDIR /app

# Install shared package
COPY shared/ /shared/
RUN pip install --no-cache-dir /shared/

# Install requirements
COPY comms/discord_bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (only this bot)
COPY comms/__init__.py /app/comms/__init__.py
COPY comms/discord_bot/ /app/comms/discord_bot/

ENV PYTHONPATH="/app:/shared"

CMD ["python", "-m", "comms.discord_bot.main"]
