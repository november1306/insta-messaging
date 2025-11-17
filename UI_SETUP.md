# UI Web Layer Setup Guide
**Instagram-like Messaging Interface for Live Demo & Testing**

---

## Overview

The UI web layer provides an Instagram-style chat interface for:
- Viewing real-time Instagram conversations
- Sending messages through your Instagram Business Account
- Monitoring webhook activity
- Testing the messaging automation system

**Tech Stack:**
- **Frontend**: Vue 3 + Vite + Tailwind CSS
- **Real-time**: Server-Sent Events (SSE)
- **Backend**: FastAPI (existing)

---

## Quick Start

### Option 1: Development Mode (Recommended)

Run both backend and frontend with hot reload:

**Linux/Mac:**
```bash
./dev.sh
```

**Windows (CMD):**
```cmd
dev.bat
```

**Windows (PowerShell):**
```powershell
.\dev.ps1
```

**Access:**
- Vue Frontend (dev): http://localhost:5173
- FastAPI Backend: http://localhost:8000
- API Documentation: http://localhost:8000/docs

### Option 2: Production Mode

Build frontend and run from single server:

**Linux/Mac:**
```bash
# Build frontend
./build.sh

# Run server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Windows (CMD):**
```cmd
REM Build frontend
build.bat

REM Run server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Windows (PowerShell):**
```powershell
# Build frontend
.\build.ps1

# Run server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Access:**
- Chat UI: http://localhost:8000/chat
- API: http://localhost:8000/api/v1
- Docs: http://localhost:8000/docs

---

## Installation

### Prerequisites

- Python 3.12+
- Node.js 18+ and npm
- All backend dependencies installed (`pip install -r requirements.txt`)

### Frontend Setup

```bash
# Install frontend dependencies
cd frontend
npm install
cd ..
```

---

## Development Workflow

### Starting Development

**Linux/Mac:**
```bash
# Start both servers
./dev.sh

# OR manually:
# Terminal 1: Backend
uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev
```

**Windows:**
```cmd
REM Start both servers
dev.bat

REM OR manually:
REM Terminal 1: Backend
uvicorn app.main:app --reload --port 8000

REM Terminal 2: Frontend
cd frontend
npm run dev
```

### Making Changes

**Frontend changes:**
- Edit files in `frontend/src/`
- Hot reload is automatic
- Access at http://localhost:5173

**Backend changes:**
- Edit files in `app/`
- FastAPI auto-reloads
- API accessible at http://localhost:8000

---

## Project Structure

```
insta-messaging/
├── app/
│   ├── api/
│   │   ├── webhooks.py         # Instagram webhook handler (SSE broadcast added)
│   │   ├── messages.py         # Message sending API
│   │   ├── ui.py              # NEW: UI endpoints (conversations, messages)
│   │   └── events.py          # NEW: SSE endpoint for real-time updates
│   ├── main.py                 # Updated with frontend serving
│   └── ...
│
├── frontend/                   # NEW: Vue.js application
│   ├── src/
│   │   ├── components/
│   │   │   ├── ConversationList.vue
│   │   │   ├── MessageThread.vue
│   │   │   ├── MessageBubble.vue
│   │   │   └── ConversationDetails.vue
│   │   ├── views/
│   │   │   └── ChatView.vue
│   │   ├── stores/
│   │   │   └── messages.js      # Pinia store for state
│   │   ├── api/
│   │   │   └── client.js        # Axios API client
│   │   ├── composables/
│   │   │   └── useSSE.js        # SSE connection hook
│   │   ├── router/
│   │   │   └── index.js         # Vue Router config
│   │   ├── App.vue
│   │   ├── main.js
│   │   └── style.css            # Tailwind styles
│   ├── vite.config.js           # Vite + proxy config
│   ├── tailwind.config.js
│   └── package.json
│
├── dev.sh                       # NEW: Development startup script
├── build.sh                     # NEW: Production build script
└── UI_DESIGN_PROPOSAL.md        # Design documentation
```

---

## URL Structure

| URL | Description | Environment |
|-----|-------------|-------------|
| `http://localhost:5173` | Vue dev server with hot reload | Development |
| `http://localhost:8000/chat` | Production-built UI | Production |
| `http://localhost:8000/api/v1/*` | REST API endpoints | Both |
| `http://localhost:8000/api/v1/events` | SSE endpoint | Both |
| `http://localhost:8000/webhooks/instagram` | Instagram webhook | Both |
| `http://localhost:8000/docs` | Interactive API docs | Both |

---

## How It Works

### Message Flow

#### Incoming Messages (Instagram → UI)

```
Instagram User sends DM
    ↓
POST /webhooks/instagram (Facebook webhook)
    ↓
Save to database
    ↓
Broadcast via SSE to connected clients
    ↓
Vue UI receives SSE event
    ↓
Updates conversation list & message thread
```

#### Outgoing Messages (UI → Instagram)

```
User types in Vue UI
    ↓
POST /api/v1/messages/send
    ↓
FastAPI sends to Instagram API
    ↓
Save to database
    ↓
Return success response
    ↓
Vue UI shows message immediately
```

### Real-Time Updates (SSE)

The frontend connects to `/api/v1/events` and receives:

```javascript
// Event types:
{
  "event": "new_message",
  "data": {
    "id": "msg_123",
    "sender_id": "instagram_user_456",
    "text": "Hello!",
    "direction": "inbound",
    "timestamp": "2025-11-15T10:30:00Z"
  }
}

{
  "event": "message_status",
  "data": {
    "message_id": "msg_123",
    "status": "delivered"
  }
}
```

---

## API Endpoints

### New UI Endpoints

#### GET /api/v1/ui/conversations
Returns list of all conversations grouped by sender.

**Response:**
```json
{
  "conversations": [
    {
      "sender_id": "instagram_user_123",
      "sender_name": "Alice Johnson",
      "last_message": "Thank you!",
      "last_message_time": "2025-11-15T10:30:00Z",
      "unread_count": 2,
      "instagram_account_id": "your_business_account"
    }
  ]
}
```

#### GET /api/v1/ui/messages/{sender_id}
Returns all messages in a conversation thread.

**Response:**
```json
{
  "messages": [
    {
      "id": 1,
      "text": "Hey, when does the sale start?",
      "direction": "inbound",
      "timestamp": "2025-11-15T09:00:00Z",
      "status": null
    },
    {
      "id": 2,
      "text": "The sale starts tomorrow at 9 AM!",
      "direction": "outbound",
      "timestamp": "2025-11-15T09:05:00Z",
      "status": "delivered"
    }
  ],
  "sender_info": {
    "id": "instagram_user_123",
    "name": "Alice Johnson"
  }
}
```

#### GET /api/v1/events (SSE)
Server-Sent Events stream for real-time updates.

**Events:**
- `connected`: Initial connection confirmation
- `new_message`: New Instagram message received
- `message_status`: Delivery status update
- `keepalive`: Connection keep-alive ping (every 30s)

### Existing Endpoints (Used by UI)

- `POST /api/v1/messages/send` - Send message to Instagram
- `GET /api/v1/messages/{id}/status` - Check delivery status
- `POST /api/v1/accounts` - Configure accounts

---

## Testing the UI

### 1. Start Development Server

```bash
./dev.sh
```

### 2. Open Chat UI

Navigate to http://localhost:5173

### 3. Simulate Incoming Message

Send a test webhook (simulates Instagram message):

```bash
curl -X POST http://localhost:8000/webhooks/instagram \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: sha256=$(echo -n '{"entry":[]}' | openssl dgst -sha256 -hmac "your-app-secret" | cut -d' ' -f2)" \
  -d '{
    "entry": [{
      "messaging": [{
        "sender": {"id": "test_user_123"},
        "recipient": {"id": "your_page_id"},
        "message": {
          "mid": "msg_'$(date +%s)'",
          "text": "Hello from test!"
        },
        "timestamp": '$(date +%s000)'
      }]
    }]
  }'
```

**Expected:**
- Message appears in UI conversation list
- Clicking conversation shows message thread
- Real-time update indicator shows "connected"

### 4. Send a Message

1. Select a conversation
2. Type a message in the input box
3. Click "Send"

**Expected:**
- Message appears immediately in thread
- Blue bubble on the right (outbound)
- Status indicator shows ✓ or ✓✓

---

## Troubleshooting

### Frontend won't start

```bash
# Reinstall dependencies
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run dev
```

### Backend can't find frontend

```bash
# Build frontend first
./build.sh

# Check dist directory exists
ls -la frontend/dist
```

### SSE not connecting

**Check:**
1. Backend is running: http://localhost:8000/health
2. SSE endpoint: http://localhost:8000/api/v1/events
3. Browser console for connection errors
4. No proxy/firewall blocking SSE

**Debug:**
```javascript
// In browser console
const sse = new EventSource('http://localhost:8000/api/v1/events')
sse.onmessage = (e) => console.log('SSE:', e.data)
sse.onerror = (e) => console.error('SSE Error:', e)
```

### Proxy errors in development

**Vite proxy not working?**

Check `frontend/vite.config.js`:
```javascript
server: {
  proxy: {
    '/api': 'http://localhost:8000',
    '/webhooks': 'http://localhost:8000'
  }
}
```

Make sure backend is running on port 8000.

---

## Customization

### Change Instagram Blue Color

Edit `frontend/tailwind.config.js`:
```javascript
theme: {
  extend: {
    colors: {
      'instagram-blue': '#0095F6',  // Change this
    }
  }
}
```

### Add New UI Features

1. Create component in `frontend/src/components/`
2. Import in `ChatView.vue`
3. Add to layout
4. Hot reload shows changes immediately

### Modify API Endpoints

1. Edit `app/api/ui.py` or `app/api/events.py`
2. FastAPI auto-reloads
3. Update Vue API calls in `frontend/src/stores/messages.js`

---

## Deployment

### Single Server Deployment

```bash
# Build frontend
./build.sh

# Run with production settings
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Docker Deployment

```dockerfile
FROM python:3.12-slim

# Install Node.js
RUN apt-get update && apt-get install -y nodejs npm

WORKDIR /app

# Backend dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Frontend build
COPY frontend/package*.json frontend/
RUN cd frontend && npm install
COPY frontend/ frontend/
RUN cd frontend && npm run build

# Backend code
COPY app/ app/

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables

Required for production:
```bash
INSTAGRAM_ACCESS_TOKEN=your_token
INSTAGRAM_APP_SECRET=your_secret
FACEBOOK_VERIFY_TOKEN=your_verify_token
DATABASE_URL=your_db_url  # Optional, defaults to SQLite
```

---

## Next Steps

1. **Authentication**: Add proper API authentication (currently uses demo token)
2. **User Management**: Track which customer service rep handles which conversation
3. **Read Receipts**: Implement read/unread tracking
4. **Typing Indicators**: Show when customer is typing
5. **File Uploads**: Support image/video messages
6. **Search**: Add conversation and message search
7. **Notifications**: Browser notifications for new messages
8. **PWA**: Make it installable as mobile app

---

## Support

- **Issues**: Check `UI_DESIGN_PROPOSAL.md` for architecture details
- **API Docs**: http://localhost:8000/docs
- **Logs**: `tail -f logs/app.log` (if configured)

For questions, refer to the main `README.md` or codebase documentation.
