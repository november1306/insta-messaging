<template>
  <div class="border-b border-instagram-border bg-white">
    <!-- Top bar: Master account + SSE status + Logout -->
    <div class="flex items-center justify-between px-6 py-2 border-b border-gray-200 bg-gray-50">
      <div class="flex items-center gap-2">
        <div class="w-6 h-6 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
          <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
          </svg>
        </div>
        <div class="flex items-center gap-1.5">
          <span class="text-sm font-semibold text-gray-900">{{ sessionStore.username }}</span>
          <span class="text-xs text-gray-400">•</span>
          <span class="text-xs text-gray-500">Master Account</span>
          <!-- SSE Status Indicator -->
          <span v-if="sseError" class="text-xs text-red-600" :title="sseError">● Offline</span>
          <span v-else-if="sseConnected" class="text-xs text-green-600" title="Real-time updates active">● Live</span>
        </div>
      </div>
      <button
        @click="handleLogout"
        class="px-3 py-1.5 text-sm text-gray-600 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors flex items-center gap-1.5"
        title="Logout"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
        </svg>
        <span>Logout</span>
      </button>
    </div>

    <!-- Tab strip: Instagram accounts -->
    <div class="px-6 py-0 bg-white">
      <!-- Loading State -->
      <div v-if="accountsStore.loading && accountsStore.accounts.length === 0" class="flex items-center justify-center py-4">
        <div class="animate-spin w-5 h-5 border-2 border-gray-300 border-t-instagram-blue rounded-full"></div>
        <span class="text-sm text-gray-500 ml-2">Loading accounts...</span>
      </div>

      <!-- No Accounts State -->
      <div v-else-if="!accountsStore.hasAccounts" class="flex items-center justify-center py-4">
        <p class="text-sm text-gray-500 mr-3">No Instagram accounts linked</p>
        <button
          @click="openOAuthModal"
          class="px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white text-sm font-medium rounded-lg hover:opacity-90 transition-opacity flex items-center gap-2"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          Add Account
        </button>
      </div>

      <!-- Account Tabs -->
      <div v-else class="flex items-center gap-1 overflow-x-auto custom-scrollbar">
        <button
          v-for="account in accountsStore.accounts"
          :key="account.account_id"
          @click="selectAccount(account)"
          class="flex items-center gap-2 px-4 py-3 transition-all border-b-2 whitespace-nowrap"
          :class="{
            'border-instagram-blue bg-instagram-bg text-instagram-blue': isSelected(account),
            'border-transparent text-gray-600 hover:text-gray-900 hover:bg-gray-50': !isSelected(account)
          }"
        >
          <!-- Profile Picture -->
          <div class="relative flex-shrink-0">
            <img
              v-if="account.profile_picture_url"
              :src="getProxiedImageUrl(account.profile_picture_url)"
              :alt="account.username"
              class="w-8 h-8 rounded-full object-cover"
            />
            <div
              v-else
              class="w-8 h-8 rounded-full bg-gradient-to-br from-purple-400 to-pink-400 flex items-center justify-center"
            >
              <span class="text-white font-semibold text-xs">{{ getInitials(account.username) }}</span>
            </div>
            <!-- Primary Badge -->
            <div
              v-if="account.is_primary"
              class="absolute -top-0.5 -right-0.5 w-3 h-3 bg-green-500 rounded-full border-2 border-white"
              title="Primary account"
            >
              <svg class="w-1.5 h-1.5 text-white absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
              </svg>
            </div>
          </div>

          <!-- Account Username -->
          <span class="text-sm font-semibold truncate max-w-32">@{{ account.username }}</span>
        </button>

        <!-- Add Account Button -->
        <button
          @click="openOAuthModal"
          class="flex items-center gap-1.5 px-3 py-3 text-instagram-blue hover:bg-blue-50 rounded-t-lg transition-colors border-b-2 border-transparent"
          title="Add Instagram account"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          <span class="text-sm font-medium">Add</span>
        </button>
      </div>
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

        <!-- Error Message -->
        <div v-if="oauthError" class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <div class="flex items-start gap-2">
            <svg class="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div class="flex-1">
              <p class="text-sm font-medium text-red-800">{{ oauthError }}</p>
            </div>
            <button
              @click="oauthError = null"
              class="text-red-400 hover:text-red-600 transition-colors"
              title="Dismiss"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

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
          :disabled="accountsStore.loading"
          class="w-full bg-gradient-to-r from-purple-500 via-pink-500 to-orange-500 text-white font-semibold py-3 px-6 rounded-lg hover:opacity-90 transition-opacity flex items-center justify-center gap-2 disabled:opacity-50"
        >
          <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073z"/>
          </svg>
          Continue with Instagram
        </button>

        <p class="text-xs text-gray-400 mt-4 text-center">
          You'll be redirected to Instagram to authorize access
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '../stores/session'
import { useAccountsStore } from '../stores/accounts'
import { getProxiedImageUrl } from '../composables/useImageProxy'
import { getInitials } from '../composables/useUserUtils'

// Props for SSE connection status
defineProps({
  sseConnected: {
    type: Boolean,
    default: false
  },
  sseError: {
    type: String,
    default: null
  }
})

const router = useRouter()
const sessionStore = useSessionStore()
const accountsStore = useAccountsStore()

const showOAuthModal = ref(false)
const forceReauth = ref(false)
const oauthError = ref(null)

onMounted(async () => {
  // Fetch accounts when component mounts
  if (sessionStore.isAuthenticated) {
    await accountsStore.fetchAccounts()
  }
})

function isSelected(account) {
  return accountsStore.selectedAccount?.account_id === account.account_id
}

function selectAccount(account) {
  accountsStore.selectAccount(account.account_id)
}

function openOAuthModal() {
  oauthError.value = null
  forceReauth.value = false
  showOAuthModal.value = true
}

async function handleLogout() {
  await sessionStore.logout()
  router.push('/login')
}

async function handleOAuthLogin() {
  oauthError.value = null // Clear previous errors
  try {
    await accountsStore.startOAuthFlow(forceReauth.value)
    // Success - close modal
    showOAuthModal.value = false
  } catch (err) {
    console.error('OAuth flow error:', err)
    // Set user-friendly error message
    if (err.message?.includes('popup')) {
      oauthError.value = 'Popup was blocked. Please allow popups for this site and try again.'
    } else if (err.message?.includes('network') || err.message?.includes('fetch')) {
      oauthError.value = 'Network error. Please check your connection and try again.'
    } else {
      oauthError.value = err.message || 'Failed to start OAuth flow. Please try again.'
    }
  }
}
</script>

<style scoped>
/* Custom scrollbar for horizontal tabs */
.custom-scrollbar::-webkit-scrollbar {
  height: 4px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 2px;
}

.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #9ca3af;
}
</style>
