<template>
  <div class="flex h-screen bg-white">
    <!-- Left Sidebar: Conversation List -->
    <div class="w-96 border-r border-instagram-border flex flex-col">
      <!-- Header -->
      <div class="border-b border-instagram-border bg-white">
        <!-- Account Info -->
        <div class="px-6 py-4 border-b border-instagram-border">
          <div v-if="store.currentAccount" class="flex items-center gap-3">
            <img
              v-if="store.currentAccount.profile_picture_url"
              :src="getProxiedImageUrl(store.currentAccount.profile_picture_url)"
              :alt="store.currentAccount.username"
              class="w-12 h-12 rounded-full object-cover shadow-sm"
            />
            <div
              v-else
              class="w-12 h-12 rounded-full bg-gradient-to-br from-purple-500 via-pink-500 to-orange-500 flex items-center justify-center text-white font-bold text-lg shadow-sm"
            >
              {{ getAccountInitial(store.currentAccount.username) }}
            </div>
            <div class="flex-1 min-w-0">
              <div class="font-semibold text-base truncate">{{ store.currentAccount.username }}</div>
              <div class="text-xs text-gray-500 truncate">Business account</div>
            </div>
            <button
              @click="handleLogout"
              class="text-gray-600 hover:text-red-600 transition-colors p-2 hover:bg-gray-50 rounded-full"
              title="Logout"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
            </button>
          </div>
          <div v-else class="flex items-center gap-3">
            <div class="w-12 h-12 rounded-full bg-gray-200 animate-pulse"></div>
            <div class="flex-1">
              <div class="h-4 bg-gray-200 rounded animate-pulse mb-2"></div>
              <div class="h-3 bg-gray-200 rounded animate-pulse w-2/3"></div>
            </div>
          </div>
        </div>

        <!-- Messages Header -->
        <div class="h-14 flex items-center justify-between px-6">
          <h1 class="text-xl font-bold">Messages</h1>
          <div class="flex gap-2">
            <button
              @click="showOAuthModal = true"
              class="text-instagram-blue hover:text-blue-700 transition-colors px-3 py-1.5 hover:bg-gray-50 rounded-lg text-sm font-medium flex items-center gap-1.5"
              title="Add Instagram account"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
              </svg>
              Add Account
            </button>
            <button
              @click="refreshConversations"
              class="text-instagram-blue hover:text-blue-700 transition-colors p-2 hover:bg-gray-50 rounded-full"
              title="Refresh conversations"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      <!-- Conversation List -->
      <ConversationList
        :conversations="store.conversations"
        :active-id="store.activeConversationId"
        :loading="store.loading"
        @select="handleSelectConversation"
      />
    </div>

    <!-- Center: Message Thread -->
    <div class="flex-1 flex flex-col">
      <MessageThread
        v-if="store.activeConversationId"
        :conversation="store.activeConversation"
        :messages="store.activeMessages"
        :loading="store.loading"
        @send="handleSendMessage"
      />
      <div v-else class="flex-1 flex items-center justify-center text-gray-400">
        <div class="text-center">
          <svg class="w-24 h-24 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
          <p class="text-xl">Select a conversation to start messaging</p>
        </div>
      </div>
    </div>

    <!-- Right Sidebar: Details -->
    <div class="w-80 border-l border-instagram-border">
      <ConversationDetails
        v-if="store.activeConversation"
        :conversation="store.activeConversation"
      />
    </div>

    <!-- OAuth Modal -->
    <div
      v-if="showOAuthModal"
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      @click.self="showOAuthModal = false"
    >
      <div class="bg-white rounded-lg p-6 max-w-md w-full mx-4 shadow-xl">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-xl font-bold">Add Instagram Account</h2>
          <button
            @click="showOAuthModal = false"
            class="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <p class="text-gray-600 mb-6">
          Connect your Instagram Business Account to start managing messages.
        </p>

        <!-- Force Reauth Checkbox -->
        <div class="mb-6">
          <label class="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              v-model="forceReauth"
              class="mt-1 w-4 h-4 text-instagram-blue border-gray-300 rounded focus:ring-instagram-blue"
            />
            <div class="flex-1">
              <div class="font-medium text-sm">Force re-authentication</div>
              <div class="text-xs text-gray-500 mt-0.5">
                Require entering Instagram credentials even if already logged in
              </div>
            </div>
          </label>
        </div>

        <!-- OAuth Button -->
        <button
          @click="handleOAuthLogin"
          class="w-full bg-gradient-to-r from-purple-500 via-pink-500 to-orange-500 text-white font-semibold py-3 px-6 rounded-lg hover:opacity-90 transition-opacity flex items-center justify-center gap-2"
        >
          <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
          </svg>
          Continue with Instagram
        </button>

        <p class="text-xs text-gray-400 mt-4 text-center">
          You'll be redirected to Instagram to authorize access
        </p>
      </div>
    </div>

    <!-- SSE Connection Status -->
    <div
      v-if="sseError"
      class="fixed bottom-4 right-4 bg-red-500 text-white px-4 py-2 rounded-lg shadow-lg"
    >
      {{ sseError }}
    </div>
    <div
      v-else-if="sseConnected"
      class="fixed bottom-4 right-4 bg-green-500 text-white px-4 py-2 rounded-lg shadow-lg text-sm"
    >
      ✓ Real-time updates active
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useMessagesStore } from '../stores/messages'
import { useSessionStore } from '../stores/session'
import { useSSE } from '../composables/useSSE'
import { getProxiedImageUrl } from '../composables/useImageProxy'
import ConversationList from '../components/ConversationList.vue'
import MessageThread from '../components/MessageThread.vue'
import ConversationDetails from '../components/ConversationDetails.vue'

const router = useRouter()
const store = useMessagesStore()
const sessionStore = useSessionStore()

// OAuth state
const showOAuthModal = ref(false)
const forceReauth = ref(false)

// SSE connection for real-time updates
const { connected: sseConnected, error: sseError } = useSSE(
  '/api/v1/events',
  handleSSEMessage
)

function handleSSEMessage(data) {
  console.log('SSE message received:', data)

  switch (data.event) {
    case 'new_message':
      // Handle both inbound and outbound messages
      if (data.data.direction === 'inbound') {
        store.addIncomingMessage(data.data)
      } else if (data.data.direction === 'outbound') {
        // For outbound messages from SSE, check if message already exists (optimistic update)
        // If it exists, update it with full data including attachments
        // If not, add it (e.g., message sent from other session/tab)
        const recipientId = data.data.recipient_id  // Customer ID (not business account)

        // Initialize conversation array if needed
        if (!store.messages[recipientId]) {
          store.messages[recipientId] = []
        }

        const existingIndex = store.messages[recipientId].findIndex(m => m.id === data.data.id)

        if (existingIndex >= 0) {
          // Update existing message with SSE data (includes attachments)
          store.messages[recipientId][existingIndex] = {
            ...store.messages[recipientId][existingIndex],
            ...data.data,
            status: data.data.status || 'sent'
          }
        } else {
          // Add new outbound message from SSE (e.g., sent from another tab)
          // Add to recipient's conversation, not sender's
          store.messages[recipientId].push(data.data)
        }
      }
      break
    case 'message_status':
      store.updateMessageStatus(data.data.message_id, data.data.status, data.data.error)
      break
    default:
      console.warn('Unknown SSE event:', data.event)
  }
}

async function handleSelectConversation(senderId) {
  store.setActiveConversation(senderId)

  // Fetch messages if not already loaded
  if (!store.messages[senderId]) {
    await store.fetchMessages(senderId)
  }
}

async function handleSendMessage(formData, onProgress) {
  try {
    await store.sendMessage(formData, onProgress)
  } catch (err) {
    console.error('Failed to send message:', err)
    // Error is already stored in store.error
  }
}

async function refreshConversations() {
  await Promise.all([
    store.fetchCurrentAccount(),
    store.fetchConversations()
  ])
}

function getAccountInitial(username) {
  if (!username) return '?'
  // Remove @ symbol if present
  const cleanName = username.replace('@', '')
  return cleanName[0]?.toUpperCase() || '?'
}

function handleLogout() {
  console.log('[ChatView] Logging out...')
  sessionStore.logout()
  router.push('/login')
}

async function handleOAuthLogin() {
  try {
    const response = await fetch(`${window.location.origin}/oauth/instagram/init`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    })

    if (!response.ok) {
      alert('Failed to start Instagram authentication. Please try again.')
      return
    }

    const data = await response.json()
    let authUrl = data.auth_url

    if (forceReauth.value) {
      authUrl += '&force_reauth=true'
    }

    window.location.href = authUrl
  } catch (err) {
    console.error('OAuth init error:', err)
    alert('Failed to start Instagram authentication. Please try again.')
  }
}

onMounted(async () => {
  const sessionReady = await sessionStore.ensureSession()

  if (!sessionReady) {
    return
  }

  await Promise.all([
    store.fetchCurrentAccount(),
    store.fetchConversations()
  ])
})
</script>
