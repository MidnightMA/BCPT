# Bale Control Panel for Telegram Account

A production-quality, modular Python application providing a **Bale-based control panel** for a personal **Telegram** account.

The system connects two distinct platform identities:
1. **Bale Control Bot**: Implemented using `python-telegram-bot` (v21+ with asyncio) configured to use Bale's Telegram-compatible Bot API (`https://tapi.bale.ai/bot`). The user interacts only with this bot on Bale Messenger.
2. **Telegram Personal Account**: Controlled via **Telethon** (MTProto client) directly connecting to Telegram's MTProto API to perform all actual account operations (dialogs, messages, media, permissions, search).

---

## 1. Architecture Overview

The system strictly follows a layered architecture with clean boundaries:

```
Bale Messenger (User Interface)
       │  (HTTPS requests)
       ▼
Bale Bot API (https://tapi.bale.ai/bot<token>/METHOD_NAME)
       │  (Telegram Bot API-compatible protocol)
       ▼
python-telegram-bot UI Engine (app/bot)
       │
       ▼
Handlers / Routing (app/bot/handlers)
       │
       ▼
Service Layer (app/services)
       │
       ▼
Telegram Adapter Layer (app/telegram)
       │
       ▼
Telethon Client Manager (MTProto)
       │
       ▼
Telegram MTProto API
```

### Key Architectural Boundaries:
- **Bale Transport Integration**: The bot UI runs on Bale by pointing `python-telegram-bot` to Bale's Bot API endpoint (`https://tapi.bale.ai/bot`).
- **Telegram Account Preservation**: All Telegram MTProto operations (session, API ID, API Hash, Telethon) remain 100% on Telegram.
- **UI Independence**: The bot UI never calls Telethon directly. Handlers communicate strictly through the Service Layer.
- **Service Decoupling**: Services do not know about python-telegram-bot's `Update`, `ContextTypes`, or `InlineKeyboardMarkup` objects. They consume and return pure Python DTOs (`ChatDTO`, `MessageDTO`, `UserDTO`, `ChatPermissionsDTO`).
- **Adapter Isolation**: Telethon-specific MTProto exceptions (such as `FloodWaitError` and RPC errors) are mapped to domain-specific application exceptions before reaching business logic.
- **Multi-User State Isolation**: User interaction states, navigation history, and preferences are isolated per controller user ID.

---

## 2. Directory Structure

```
project/
├── app/
│   ├── main.py                     # App startup (Telethon + Bale bot polling), shutdown
│   ├── bot/
│   │   ├── formatters/             # Bale Markdown formatters (chats, messages, info)
│   │   ├── handlers/               # Command, message, and callback handlers
│   │   ├── keyboards/              # Inline keyboards and callback data builders
│   │   └── states/                 # User-isolated state machine (Redis/Memory)
│   ├── cache/                      # Redis client with in-memory fallback
│   ├── core/                       # Settings, constants, logging, security, exceptions
│   ├── database/                   # SQLAlchemy 2.0 models, repository, migrations
│   ├── services/                   # Business logic (chat, message, media, search, perms)
│   ├── telegram/                   # Telethon client manager, adapter, MTProto events
│   ├── utils/                      # Pagination, safe Markdown escaping, file cleanup
│   └── workers/                    # Asyncio background queue & recurring tasks
├── data/                           # Persistent storage (session files, sqlite db)
├── tmp/                            # Safe temporary files directory
├── tests/                          # Automated test suite (pytest)
├── setup_telethon.py               # Interactive CLI for first-time Telethon login
├── requirements.txt                # Pinned dependencies
├── pyproject.toml                  # Python package configuration
├── .env.example                    # Environment template
├── Dockerfile                      # Production Docker container
├── docker-compose.yml              # Multi-container orchestration
└── README.md                       # Complete documentation
```

---

## 3. Prerequisites

- **Python 3.12+**
- **Bale Bot Token** (obtain from `@BotFather` on Bale Messenger)
- **Telegram API ID & API Hash** (obtain from [my.telegram.org](https://my.telegram.org) for your Telegram account)
- **Docker & Docker Compose** (optional, for containerized deployment)

---

## 4. Setup Guide

### Step 1: Create Virtual Environment

```bash
# Navigate to project directory
cd /path/to/project

# Create a virtual environment using Python 3.12+
python3.12 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables

Copy the example environment configuration:
```bash
cp .env.example .env
```

Open `.env` in your editor and configure the required values:

| Variable | Description | Example |
| :--- | :--- | :--- |
| `BOT_TOKEN` | Bale Bot API Token from @BotFather on Bale | `123456789:ABCdef...` |
| `BALE_BASE_URL` | Bale Bot API base URL | `https://tapi.bale.ai/bot` |
| `BALE_FILE_URL` | Bale Bot API file download base URL | `https://tapi.bale.ai/file/bot` |
| `API_ID` | Telegram API ID from my.telegram.org | `12345678` |
| `API_HASH` | Telegram API Hash from my.telegram.org | `0123456789abcdef0123456789abcdef` |
| `AUTHORIZED_USER_IDS` | Comma-separated Bale user IDs authorized to use bot | `123456789,987654321` |
| `TELEGRAM_SESSION` | Telethon session path | `data/telegram.session` |
| `DATABASE_URL` | SQLAlchemy async connection string | `sqlite+aiosqlite:///data/app.db` |
| `REDIS_URL` | Redis URL (optional; memory fallback used if omitted) | `redis://localhost:6379/0` |
| `TEMP_DIR` | Directory for temporary file transfers | `tmp` |
| `DATA_DIR` | Directory for persistent sessions | `data` |

> **Finding Your Bale User ID:** Your user ID in Bale can be found by sending a message to your bot or using an ID lookup bot in Bale.

### Step 3: Authenticate the Telethon User Account

Run the dedicated setup script to authenticate your personal Telegram account interactively:
```bash
python setup_telethon.py
```
- Enter your Telegram phone number with country code (e.g., `+1234567890`).
- Enter the verification code received inside your Telegram app.
- Enter your 2FA password if enabled.
- The session is saved securely to `data/telegram.session`.

---

## 5. Running the Application

### Option A: Running Locally

```bash
# Make sure your virtual environment is active
source .venv/bin/activate

# Start the application
python -m app.main
```

### Option B: Running with Docker Compose

```bash
# Build and start services (App, PostgreSQL, Redis)
docker-compose up -d --build

# View logs
docker-compose logs -f app
```

---

## 6. Running Tests

The test suite runs with mocked adapters and does not require an active Telegram or Bale connection:

```bash
# Run all unit and integration tests
pytest

# Run tests with verbose output
pytest -v

# Run with test coverage report
pytest --cov=app tests/
```

---

## 7. Features & User Experience

- **Single-Panel Navigation on Bale**: Most interactions edit the existing message rather than spamming the chat with new messages.
- **Home Dashboard**: Displays connected Telegram account name, username, Telegram ID, and quick action buttons.
- **Telegram Chat Management from Bale**:
  - Paginated dialog list with chat type badges (👤 User, 👥 Group, 📢 Channel, 🤖 Bot, 💾 Saved Messages).
  - Unread badge counter (🔴).
  - Bookmark favorite chats with one-touch toggle (⭐).
- **Direct User Resolution & Public Channel Discovery**:
  - Enter any Telegram `@username`, public link (`t.me/...`), or numeric ID to resolve users or channels via Telethon.
  - Send messages or files to private users directly, even if the personal Telegram account has never contacted them before.
  - Preview public channels, inspect their metadata and recent messages, and join them with one tap using `➕ Join Channel`.
  - Graceful handling of invalid usernames, inaccessible/private channels, and MTProto errors.
- **Complete Message & Media Viewer**:
  - Select any message code (`👁 #ID`) or enter a message ID (`🔍 View #`) to inspect the complete message without truncation.
  - Automatically downloads and delivers original media through the Bale bot:
    - 📷 Photos
    - 🎬 Videos
    - 📁 Documents & arbitrary files
    - 🎵 Audio files & 🎙 voice notes
    - 📦 Multi-item Albums & media groups (sent as media groups with fallback to individual delivery)
  - Full caption and text retention, media metadata (filenames, file sizes, mime types).
  - Temporary disk storage with guaranteed cleanup in `finally` blocks and 50MB upload size guards.
  - Interactive message controls: quick Reply, Edit, Pin, Delete, and return navigation.
- **File Transfers**:
  - Send files, photos, videos, audio, and documents through your Telegram account via Bale.
  - Automatic download to temporary disk storage with guaranteed cleanup in `finally` blocks.
- **Search**:
  - Fast dialog search by name or username.
  - In-chat message text search.
- **Permission Awareness**:
  - Checks if the account can send messages, send media, post, edit, or pin before rendering actions.
  - Read-only channels disable send buttons automatically.
- **Security Hardening**:
  - Whitelist authorization check on every update (`@authorized_only`).
  - Path traversal protection for all file uploads.
  - Automatic secret scrubbing filter on application logs.

---

## 8. Telegram & Bale API Notes

1. **Bale Bot API Compatibility**: Bale provides an API compatible with the Telegram Bot API at `https://tapi.bale.ai/bot<token>/METHOD_NAME`. `python-telegram-bot` communicates with Bale seamlessly via its `base_url` parameter.
2. **Bale Markdown Formatting**: In Bale, message text is formatted using Markdown. Bold text uses ` *text* ` (with spaces before and after asterisks), italics use ` _text_ ` (with spaces before and after underscores), and links use `[Text](URL)`. The formatters escape special characters in untrusted content to ensure reliable rendering.
3. **FloodWait Limits**: Telegram MTProto enforces rate limits on high-frequency actions. The application catches `FloodWaitError` and alerts the user with the exact wait time rather than retrying blindly.
4. **Channel Posting Rights**: Only channel administrators with `post_messages` rights can post to broadcast channels.
5. **File Size Limits**: Normal Bot API file downloads are limited to 20MB for downloads and 50MB for uploads. Files larger than Bot API limits cannot be passed through the bot interface.
6. **Message Edit Expiry**: Telegram limits editing messages after 48 hours in normal chats.

---

## 9. Security Notes

- **Never Commit Secrets**: `data/telegram.session` and `.env` contain authentication tokens and are explicitly ignored in `.gitignore`.
- **Server-Side Session**: The Telethon session file stays entirely on the server and is never transmitted over bot chats.
- **Isolated User State**: Controller states are keyed strictly by user ID, preventing cross-user state corruption in multi-controller deployments.
