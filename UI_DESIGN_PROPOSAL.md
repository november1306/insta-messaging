# UI Web Layer Design Proposal
**Instagram-like Messaging Interface for Live Demo & Testing**

---

## 1. Requirements Analysis

Based on your existing FastAPI backend, the UI needs to:

✅ **Core Features**
- Display Instagram conversations in real-time
- Send messages through your existing `/api/v1/messages/send` endpoint
- View message history from the database
- Monitor webhook activity (incoming Instagram messages)
- Show message delivery status
- Manage multiple Instagram accounts
- Auto-reply rule configuration interface

✅ **Non-Functional Requirements**
- Easy to implement and maintain
- Lives in same repository as FastAPI service
- Single deployment unit
- Works for demonstration and live testing
- Real-time updates for incoming messages

---

## 2. Proposed Architecture

### **System Overview**

```
┌─────────────────────────────────────────────────────────┐
│                    Web Browser                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │    UI Layer (Vue/React/HTMX)                     │  │
│  │    - Conversation List                           │  │
│  │    - Message Thread View                         │  │
│  │    - Send Message Form                           │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
           │                              ▲
           │ HTTP/WebSocket               │ Real-time updates
           ▼                              │
┌─────────────────────────────────────────────────────────┐
│              FastAPI Backend (Existing)                 │
│  ┌────────────────────┐  ┌──────────────────────────┐  │
│  │  New UI Endpoints  │  │  Existing API Endpoints  │  │
│  │  GET /             │  │  POST /webhooks/...      │  │
│  │  GET /chat         │  │  POST /api/v1/messages   │  │
│  │  WS  /ws/messages  │  │  GET  /api/v1/messages   │  │
│  └────────────────────┘  └──────────────────────────┘  │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │         Existing Message Repository             │   │
│  │         (messages, accounts, outbound)          │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### **Key Design Decisions**

1. **Single Deployment**: UI served by FastAPI (no separate frontend server)
2. **WebSocket for Real-time**: Push new messages instantly to UI
3. **RESTful API**: Leverage existing endpoints where possible
4. **Stateless UI**: All state in database, UI just renders it

---

## 3. Tech Stack Options

### **Option A: HTMX + Jinja2 + Tailwind** ⭐ **EASIEST**

**Stack:**
- **Frontend**: HTMX (hypermedia-driven)
- **Templates**: Jinja2 (FastAPI native)
- **Styling**: Tailwind CSS + DaisyUI components
- **Real-time**: Server-Sent Events (SSE) via HTMX

**Pros:**
- ✅ Minimal JavaScript (~14KB HTMX)
- ✅ Server-side rendering (SEO-friendly)
- ✅ Native FastAPI integration (Jinja2 built-in)
- ✅ No build step required
- ✅ Easiest to maintain
- ✅ Perfect for internal tools/demos

**Cons:**
- ❌ Less interactive than SPA
- ❌ Full page refreshes for some actions
- ❌ Limited mobile app feel

**File Structure:**
```
app/
├── templates/
│   ├── base.html
│   ├── chat.html
│   ├── components/
│   │   ├── message.html
│   │   ├── conversation_list.html
│   │   └── send_form.html
│   └── partials/
│       └── message_thread.html
├── static/
│   ├── css/
│   │   └── styles.css (Tailwind)
│   ├── js/
│   │   └── htmx.min.js
│   └── images/
├── api/
│   └── ui.py (new UI routes)
```

**Example Code:**
```python
# app/api/ui.py
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/")
async def home(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})

@router.get("/messages/{account_id}")
async def get_messages(request: Request, account_id: str):
    # Fetch from existing repository
    messages = await message_repo.get_by_account(account_id)
    return templates.TemplateResponse(
        "partials/message_thread.html",
        {"request": request, "messages": messages}
    )
```

---

### **Option B: Vue 3 + Vite + Tailwind** ⭐ **RECOMMENDED**

**Stack:**
- **Frontend**: Vue 3 (Composition API)
- **Build Tool**: Vite (fast, modern)
- **Styling**: Tailwind CSS
- **State**: Pinia (Vue store)
- **Real-time**: WebSocket (native FastAPI support)
- **HTTP Client**: Axios

**Pros:**
- ✅ Modern, reactive UI
- ✅ Excellent developer experience
- ✅ Easier than React (smaller API surface)
- ✅ Great documentation
- ✅ True real-time messaging feel
- ✅ Component reusability
- ✅ Mobile-responsive out of the box

**Cons:**
- ❌ Build step required
- ❌ More complex than HTMX
- ❌ Slightly larger bundle size

**File Structure:**
```
frontend/
├── src/
│   ├── components/
│   │   ├── ConversationList.vue
│   │   ├── MessageThread.vue
│   │   ├── MessageBubble.vue
│   │   ├── SendMessageForm.vue
│   │   └── AccountSwitcher.vue
│   ├── views/
│   │   └── ChatView.vue
│   ├── stores/
│   │   └── messages.js (Pinia)
│   ├── api/
│   │   └── client.js (Axios instance)
│   ├── composables/
│   │   └── useWebSocket.js
│   ├── App.vue
│   └── main.js
├── public/
├── index.html
├── vite.config.js
├── tailwind.config.js
└── package.json

app/
└── api/
    └── websocket.py (new WebSocket endpoint)
```

**Example Code:**
```vue
<!-- ConversationList.vue -->
<template>
  <div class="flex flex-col h-screen">
    <div v-for="conv in conversations"
         :key="conv.id"
         @click="selectConversation(conv)"
         class="p-4 border-b hover:bg-gray-50 cursor-pointer">
      <div class="flex items-center gap-3">
        <img :src="conv.avatar" class="w-12 h-12 rounded-full" />
        <div class="flex-1">
          <h3 class="font-semibold">{{ conv.name }}</h3>
          <p class="text-sm text-gray-500">{{ conv.lastMessage }}</p>
        </div>
        <span class="text-xs text-gray-400">{{ conv.timestamp }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useMessagesStore } from '@/stores/messages'

const store = useMessagesStore()
const conversations = ref([])

onMounted(async () => {
  conversations.value = await store.fetchConversations()
})

const selectConversation = (conv) => {
  store.setActiveConversation(conv.id)
}
</script>
```

```python
# app/api/websocket.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

@router.websocket("/ws/messages")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # Handle incoming messages if needed
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

---

### **Option C: React + Vite + Tailwind** (Most Popular)

**Stack:**
- **Frontend**: React 18 (Hooks)
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **State**: Zustand (lightweight)
- **Real-time**: WebSocket
- **HTTP Client**: Axios

**Pros:**
- ✅ Largest ecosystem
- ✅ Most community resources
- ✅ Best for scaling team
- ✅ Highly interactive

**Cons:**
- ❌ Steeper learning curve
- ❌ More boilerplate
- ❌ Larger bundle size
- ❌ More complex state management

*(File structure similar to Vue option)*

---

## 4. Recommended Choice: **Option B (Vue 3)**

**Why Vue 3?**
- ✅ **Easy to learn**: Simpler than React, more powerful than HTMX
- ✅ **Great DX**: Vite is blazing fast, hot reload works perfectly
- ✅ **Perfect balance**: Not too simple, not too complex
- ✅ **Excellent docs**: Vue documentation is top-tier
- ✅ **Future-proof**: Modern, actively maintained, growing community
- ✅ **Mobile-ready**: Responsive by default with Tailwind

**For internal demos**, Vue hits the sweet spot between simplicity and capability.

---

## 5. UI/UX Design Concept

### **Layout: Instagram-inspired 3-Column Design**

```
┌─────────────────────────────────────────────────────────────┐
│  InstaMessenger                          🔔  ⚙️  [Account] │
├──────────┬────────────────────┬──────────────────────────────┤
│          │                    │                              │
│  Conv 1  │  Alice Johnson     │  Account Info                │
│  ────────│  ──────────────────│  ────────────────────────    │
│  Conv 2  │  Hey, when does... │  📧 alice@example.com        │
│  ────────│            [10:30] │  📱 @alice_insta             │
│  Conv 3  │                    │  ──────────────────────────  │
│  ────────│  I'm interested... │  Auto-Reply Rules            │
│  Conv 4  │            [09:15] │  ☑️ Welcome message         │
│  ────────│                    │  ☐ Business hours          │
│  Conv 5  │  Thank you!        │  ──────────────────────────  │
│  ────────│            [08:00] │  Stats                       │
│          │                    │  📊 24 msgs today           │
│  + New   │  ┌───────────────┐ │  ⚡ 2.3s avg response       │
│          │  │ Type message  │ │                              │
│          │  └───────────────┘ │                              │
├──────────┴────────────────────┴──────────────────────────────┤
│  Powered by InstagramMessenger • Real-time updates active   │
└─────────────────────────────────────────────────────────────┘
```

### **Key Components**

1. **Left Sidebar (Conversations)**
   - List of all conversations
   - Search/filter
   - Account switcher
   - New conversation button

2. **Center Panel (Message Thread)**
   - Instagram-style message bubbles
   - Sent (blue, right) vs Received (gray, left)
   - Timestamps
   - Delivery status indicators (✓✓)
   - Send message input at bottom
   - File/image upload support

3. **Right Sidebar (Details)**
   - Active conversation info
   - Customer details from CRM
   - Auto-reply rule status
   - Quick actions (mute, archive)
   - Analytics/stats

### **Color Scheme**
```css
Primary: #0095F6 (Instagram blue)
Secondary: #8E8E8E (gray)
Success: #0ACF83 (green)
Background: #FAFAFA
Text: #262626
Border: #DBDBDB
```

---

## 6. API Requirements

### **New Endpoints Needed**

```python
# GET /api/v1/ui/conversations
# Returns list of unique conversations grouped by sender
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

# GET /api/v1/ui/messages/{sender_id}
# Returns full message thread with a sender
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

# WebSocket /ws/messages
# Pushes new messages in real-time
{
  "event": "new_message",
  "data": {
    "id": 3,
    "sender_id": "instagram_user_456",
    "text": "I'm interested in your product",
    "direction": "inbound",
    "timestamp": "2025-11-15T10:45:00Z"
  }
}
```

### **Leverage Existing Endpoints**
- `POST /api/v1/messages/send` - Already implemented ✅
- `GET /api/v1/messages/{id}/status` - Already implemented ✅
- `POST /api/v1/accounts` - Already implemented ✅

---

## 7. Implementation Plan

### **Phase 1: Foundation (Week 1)**
- [ ] Set up Vue 3 + Vite project in `/frontend`
- [ ] Configure Tailwind CSS
- [ ] Create basic layout (3-column design)
- [ ] Add static/mock data for UI development
- [ ] Configure FastAPI to serve built frontend

### **Phase 2: Backend Integration (Week 2)**
- [ ] Create new UI endpoints in `/app/api/ui.py`
- [ ] Implement conversation list endpoint
- [ ] Implement message thread endpoint
- [ ] Add WebSocket support for real-time updates
- [ ] Connect Vue app to real API

### **Phase 3: Core Features (Week 2-3)**
- [ ] Message sending functionality
- [ ] Real-time message reception
- [ ] Conversation switching
- [ ] Account switcher
- [ ] Message status indicators

### **Phase 4: Polish & Demo Features (Week 3-4)**
- [ ] Auto-reply rule toggle UI
- [ ] Webhook activity monitor
- [ ] Search/filter conversations
- [ ] Analytics dashboard
- [ ] Mobile responsive design
- [ ] Error handling & loading states

### **Phase 5: Testing & Documentation**
- [ ] E2E testing with Playwright
- [ ] User documentation
- [ ] Demo video/screenshots
- [ ] Deployment guide

---

## 8. File Structure (Final)

```
insta-messaging/
├── app/
│   ├── api/
│   │   ├── webhooks.py (existing)
│   │   ├── messages.py (existing)
│   │   ├── ui.py (NEW - UI endpoints)
│   │   └── websocket.py (NEW - WebSocket)
│   ├── templates/ (NEW - if using HTMX)
│   ├── static/ (NEW - served assets)
│   └── main.py (update to include UI routes)
│
├── frontend/ (NEW - Vue app)
│   ├── src/
│   │   ├── components/
│   │   ├── views/
│   │   ├── stores/
│   │   ├── api/
│   │   └── main.js
│   ├── public/
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── package.json
│
├── tests/
│   └── ui/ (NEW - UI tests)
│
└── docs/
    └── UI_SETUP.md (NEW)
```

---

## 9. Deployment Strategy

### **Development**
```bash
# Terminal 1: Backend
uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend (dev server)
cd frontend && npm run dev
```

### **Production**
```bash
# Build frontend
cd frontend && npm run build

# FastAPI serves built files from frontend/dist
# Single deployment artifact
```

**FastAPI configuration:**
```python
# app/main.py
from fastapi.staticfiles import StaticFiles

app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="assets")

@app.get("/")
async def serve_spa():
    return FileResponse("frontend/dist/index.html")
```

---

## 10. Estimated Effort

| Phase | Effort | Description |
|-------|--------|-------------|
| Setup | 4 hours | Vue + Tailwind + FastAPI integration |
| UI Layout | 8 hours | 3-column design, components |
| Backend API | 6 hours | New endpoints + WebSocket |
| Integration | 8 hours | Connect UI to real data |
| Features | 12 hours | Sending, receiving, real-time |
| Polish | 8 hours | Responsive, error handling |
| **Total** | **~46 hours** | **~1 week for experienced dev** |

---

## 11. Next Steps

**To proceed, please confirm:**

1. ✅ **Tech stack choice**: Vue 3 (recommended) or HTMX (simpler)?
2. ✅ **Scope**: Full Instagram-like UI or minimal demo interface?
3. ✅ **Priority features**: Real-time updates? Auto-reply UI? Analytics?
4. ✅ **Timeline**: Need it ASAP or can take 1-2 weeks?

Once confirmed, I'll:
1. Set up the chosen frontend framework
2. Create the basic layout
3. Implement the new API endpoints
4. Wire everything together
5. Add real-time WebSocket support

---

## 12. Questions for You

1. Do you have a preference between Vue, React, or HTMX?
2. Will this be used publicly or just internal demos?
3. Do you need mobile app (PWA) support?
4. Any specific Instagram features you want to replicate?
5. Should we show CRM forwarding status in the UI?

Let me know your preferences and I'll start building! 🚀
