# Communication Layer Documentation

Documentation for platform bots and cross-platform messaging patterns.

## Purpose

This directory documents the communication layer — the bot implementations for Discord, Telegram, and Slack that connect users to the core orchestrator.

## Documents

| Document | Purpose | Read When |
|----------|---------|-----------|
| [Overview](overview.md) | Common bot patterns | Understanding bot architecture |
| [Discord Bot](discord-bot.md) | Discord.py implementation | Working with Discord bot |
| [Telegram Bot](telegram-bot.md) | python-telegram-bot implementation | Working with Telegram bot |
| [Slack Bot](slack-bot.md) | slack-bolt implementation | Working with Slack bot |
| [File Pipeline](file-pipeline.md) | Cross-platform file handling | Working with file uploads/downloads |

## Bot Architecture

All bots follow a common pattern:

1. **Receive platform event** (message, mention, etc.)
2. **Normalize to IncomingMessage** (with file attachments)
3. **POST to core `/message`**
4. **Format AgentResponse** for platform
5. **Send reply** (with file attachments)

## Key Files

- **Discord**: `agent/comms/discord_bot/bot.py`
- **Telegram**: `agent/comms/telegram_bot/bot.py`
- **Slack**: `agent/comms/slack_bot/bot.py`
- **Shared Utilities**: `agent/shared/shared/file_utils.py`

## Message Flow

```
Platform Event
  ↓
Bot Normalizes → IncomingMessage
  ↓
Upload Attachments to MinIO
  ↓
POST /message to Core
  ↓
Core Returns AgentResponse
  ↓
Bot Formats for Platform
  ↓
Send Reply
```

## Related Documentation

- [Adding Platform Bot](../features/adding-platform-bot.md) — Integration guide
- [File Pipeline](file-pipeline.md) — File handling details
- [Core Endpoints](../api-reference/core-endpoints.md) — Core API reference

---

[Back to Documentation Index](../INDEX.md)
