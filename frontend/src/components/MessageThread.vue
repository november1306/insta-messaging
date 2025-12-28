<template>
  <div class="flex flex-col h-full">
    <!-- Thread Header -->
    <div class="h-16 border-b border-instagram-border flex items-center px-6">
      <div class="flex items-center gap-3">
        <img
          v-if="conversation?.profile_picture_url"
          :src="getProxiedImageUrl(conversation.profile_picture_url)"
          :alt="conversation.sender_name"
          class="w-10 h-10 rounded-full object-cover"
        />
        <div
          v-else
          class="w-10 h-10 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-white font-semibold"
        >
          {{ getInitials(conversation?.sender_name) }}
        </div>
        <div>
          <h2 class="font-semibold text-gray-900">
            {{ conversation?.sender_name }}
          </h2>
          <p class="text-xs text-gray-500">Active now</p>
        </div>
      </div>
    </div>

    <!-- Messages -->
    <div ref="messagesContainer" class="flex-1 overflow-y-auto custom-scrollbar p-6 space-y-4">
      <!-- Loading State -->
      <div v-if="loading && !messages.length" class="text-center text-gray-500 py-8">
        <svg class="animate-spin h-8 w-8 mx-auto" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <p class="mt-2">Loading messages...</p>
      </div>

      <!-- Empty State -->
      <div v-else-if="!messages.length" class="text-center text-gray-500 py-8">
        <p>No messages yet</p>
      </div>

      <!-- Message List -->
      <div v-else>
        <MessageBubble
          v-for="message in messages"
          :key="message.id"
          :message="message"
        />
      </div>
    </div>

    <!-- Input Area -->
    <div class="border-t border-instagram-border p-4">
      <form @submit.prevent="handleSend" class="flex items-center gap-3">
        <!-- Hidden file input -->
        <input
          ref="fileInput"
          type="file"
          accept="image/jpeg,image/png,video/mp4,video/ogg,video/avi,video/quicktime,video/webm,audio/aac,audio/m4a,audio/wav"
          @change="handleFileSelect"
          style="display: none"
        />

        <!-- Attach button -->
        <button
          type="button"
          @click="$refs.fileInput.click()"
          :disabled="sending"
          class="p-2 text-gray-600 hover:text-instagram-blue transition-colors disabled:opacity-50"
          title="Attach file"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6">
            <path stroke-linecap="round" stroke-linejoin="round" d="M18.375 12.739l-7.693 7.693a4.5 4.5 0 01-6.364-6.364l10.94-10.94A3 3 0 1119.5 7.372L8.552 18.32m.009-.01l-.01.01m5.699-9.941l-7.81 7.81a1.5 1.5 0 002.112 2.13" />
          </svg>
        </button>

        <input
          v-model="messageText"
          type="text"
          placeholder="Type a message..."
          class="flex-1 px-4 py-2 border border-instagram-border rounded-full focus:outline-none focus:border-instagram-blue"
          :disabled="sending"
        />
        <button
          type="submit"
          :disabled="(!messageText.trim() && !selectedFile) || sending"
          class="px-6 py-2 bg-instagram-blue text-white rounded-full font-semibold hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {{ sending ? 'Sending...' : 'Send' }}
        </button>
      </form>

      <!-- File preview -->
      <div v-if="selectedFile" class="mt-3 flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
        <img
          v-if="filePreview && selectedFile.type.startsWith('image/')"
          :src="filePreview"
          class="h-16 w-16 rounded object-cover"
          alt="Preview"
        />
        <div v-else class="h-16 w-16 rounded bg-gray-200 flex items-center justify-center">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-8 h-8 text-gray-400">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
          </svg>
        </div>
        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium text-gray-900 truncate">{{ selectedFile.name }}</p>
          <p class="text-xs text-gray-500">{{ formatFileSize(selectedFile.size) }}</p>
        </div>
        <button
          @click="removeFile"
          type="button"
          class="p-1 text-red-500 hover:text-red-700 transition-colors"
          title="Remove file"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- Upload progress -->
      <div v-if="uploadProgress > 0 && uploadProgress < 100" class="mt-3">
        <div class="flex items-center justify-between text-xs text-gray-600 mb-1">
          <span>Uploading...</span>
          <span>{{ uploadProgress }}%</span>
        </div>
        <div class="w-full bg-gray-200 rounded-full h-2">
          <div
            class="bg-instagram-blue h-2 rounded-full transition-all duration-300"
            :style="{ width: uploadProgress + '%' }"
          ></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import MessageBubble from './MessageBubble.vue'
import { getInitials } from '../composables/useUserUtils'
import { getProxiedImageUrl } from '../composables/useImageProxy'
import { useAccountsStore } from '../stores/accounts'

const accountsStore = useAccountsStore()

const props = defineProps({
  conversation: {
    type: Object,
    default: null
  },
  messages: {
    type: Array,
    required: true
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['send'])

const messageText = ref('')
const sending = ref(false)
const messagesContainer = ref(null)
const fileInput = ref(null)
const selectedFile = ref(null)
const filePreview = ref(null)
const uploadProgress = ref(0)

function handleFileSelect(event) {
  const file = event.target.files[0]
  if (!file) return

  // Validate file size
  const maxSizes = {
    'image': 8 * 1024 * 1024,    // 8MB
    'video': 25 * 1024 * 1024,   // 25MB
    'audio': 25 * 1024 * 1024    // 25MB
  }

  const fileType = file.type.split('/')[0]
  const maxSize = maxSizes[fileType]

  if (!maxSize) {
    alert('Unsupported file type')
    event.target.value = ''
    return
  }

  if (file.size > maxSize) {
    alert(`File too large. Max size for ${fileType}: ${formatFileSize(maxSize)}`)
    event.target.value = ''
    return
  }

  selectedFile.value = file

  // Create preview for images
  if (file.type.startsWith('image/')) {
    const reader = new FileReader()
    reader.onload = (e) => {
      filePreview.value = e.target.result
    }
    reader.readAsDataURL(file)
  } else {
    filePreview.value = null
  }
}

function removeFile() {
  selectedFile.value = null
  filePreview.value = null
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

function formatFileSize(bytes) {
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`
}

async function handleSend() {
  if ((!messageText.value.trim() && !selectedFile.value) || sending.value) return

  sending.value = true
  uploadProgress.value = 0

  try {
    // Create FormData
    const formData = new FormData()
    formData.append('recipient_id', props.conversation.sender_id)
    // Use account_id from conversation if available, otherwise use selected account from store
    const accountId = props.conversation.account_id || accountsStore.selectedAccount?.account_id
    if (!accountId) {
      throw new Error('No account selected. Please select an Instagram account.')
    }
    formData.append('account_id', accountId)
    formData.append('idempotency_key', `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`)

    if (messageText.value.trim()) {
      formData.append('message', messageText.value.trim())
    }

    if (selectedFile.value) {
      formData.append('file', selectedFile.value)
    }

    // Send with progress callback
    await emit('send', formData, (progress) => {
      uploadProgress.value = progress
    })

    // Clear state on success
    messageText.value = ''
    removeFile()
    uploadProgress.value = 0
  } catch (err) {
    console.error('Failed to send message:', err)
    alert('Failed to send message. Please try again.')
  } finally {
    sending.value = false
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

// Auto-scroll when new messages arrive
watch(() => props.messages.length, () => {
  scrollToBottom()
})

// Scroll to bottom when conversation changes
watch(() => props.conversation?.sender_id, () => {
  scrollToBottom()
})
</script>
