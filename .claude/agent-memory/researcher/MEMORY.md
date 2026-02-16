# Telegram Bot API Research

## BotFather Setup
- Search for @BotFather in Telegram
- Command: `/newbot` to create a bot
- You'll receive a token in format: `<numeric_id>:<secret_string>`
- Keep token secure (treat like password)
- Token is per-bot and can be revoked via @BotFather

## API Base URL
All requests: `https://api.telegram.org/bot<TOKEN>/<METHOD>`

## getUpdates (Polling)
**Endpoint**: `GET/POST https://api.telegram.org/bot<TOKEN>/getUpdates`

**Parameters**:
- `offset` (int, optional) - First update ID to return. Must be >1 than highest previous update_id. Prevents duplicates. Use negative values to get updates from end of queue backward.
- `timeout` (int, optional) - Seconds to wait for updates (long polling). 0=short polling (default). Use 30+ for production.
- `allowed_updates` (array, optional) - Limit update types (e.g., `["message"]`). Defaults to all except chat_member, message_reaction, message_reaction_count.

**Response**: JSON with `ok` (bool), `result` (array of Update objects)

**Key behavior**: Updates confirmed when getUpdates called with offset > update_id. Can track offset to avoid reprocessing.

## sendMessage
**Endpoint**: `POST https://api.telegram.org/bot<TOKEN>/sendMessage`

**Required Parameters**:
- `chat_id` (int or string) - Chat ID or username
- `text` (string) - Message text

**Common Optional Parameters**:
- `parse_mode` (string) - "HTML" or "Markdown" for formatting
- `reply_parameters` - Reply to another message
- `reply_markup` - Inline keyboards/markup

**Response**: JSON with `ok` (bool), `result` (Message object)

## Rate Limits
- **Per-chat**: 1 message/second max
- **Groups/channels**: 20 messages/minute max
- **Global**: 30 requests/second max
- **Flood handling**: API returns 429 status with `retry_after` header. Must handle gracefully.
- **Note**: Telegram doesn't publish exact limits (intentionally). Just handle 429 errors with backoff.

## Polling Strategy for Cron
1. Store last processed update_id in state file
2. Call getUpdates with `offset=last_id+1` and `timeout=0` (or small timeout)
3. Process each update in response
4. Update stored offset to max(update_id) + 1
5. Exit (next cron run continues from there)
6. Handle 429 errors with exponential backoff

## Useful Fields in Update Object
- `update_id` (int) - Unique ID
- `message` - Message object if message update
  - `message_id` - Unique message ID
  - `from` - User who sent it
  - `chat` - Chat object
  - `text` - Message text
  - `date` - Unix timestamp

## Python Requests Pattern
```python
import requests

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_URL = f"https://api.telegram.org/bot{TOKEN}"

# Get updates
def get_updates(offset):
    resp = requests.get(f"{API_URL}/getUpdates", params={"offset": offset, "timeout": 0})
    return resp.json()

# Send message
def send_message(chat_id, text):
    resp = requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": text})
    return resp.json()
```

**Source files for reference**: [Telegram Bot API](https://core.telegram.org/bots/api), [BotFather Tutorial](https://core.telegram.org/bots/tutorial), [Bots FAQ](https://core.telegram.org/bots/faq)
