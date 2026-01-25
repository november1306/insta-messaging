<template>
  <div class="h-full flex flex-col bg-gray-50 border-r border-gray-200">
    <!-- Master Account Header -->
    <div class="p-4 bg-white border-b border-gray-200">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-2">
          <div class="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
            <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </div>
          <div class="flex-1 min-w-0">
            <div class="text-sm font-semibold text-gray-900 truncate">{{ sessionStore.username }}</div>
            <div class="flex items-center gap-1.5">
              <span class="text-xs text-gray-500">Master Account</span>
              <!-- SSE Status Indicator -->
              <span v-if="sseError" class="text-xs text-red-600" :title="sseError">● Offline</span>
              <span v-else-if="sseConnected" class="text-xs text-green-600" title="Real-time updates active">● Live</span>
            </div>
          </div>
        </div>
        <button
          @click="handleLogout"
          class="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
          title="Logout"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Instagram Accounts Header -->
    <div class="px-4 py-3 bg-white border-b border-gray-200 flex items-center justify-between">
      <h2 class="text-sm font-semibold text-gray-700">Instagram Accounts</h2>
      <button
        @click="showOAuthModal = true"
        class="p-1.5 text-instagram-blue hover:bg-blue-50 rounded-lg transition-colors"
        title="Add Instagram account"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
      </button>
    </div>

    <!-- Instagram Accounts List -->
    <div class="flex-1 overflow-y-auto">
      <!-- Loading State -->
      <div v-if="accountsStore.loading && accountsStore.accounts.length === 0" class="p-4 text-center">
        <div class="animate-spin w-6 h-6 border-2 border-gray-300 border-t-instagram-blue rounded-full mx-auto"></div>
        <p class="text-sm text-gray-500 mt-2">Loading accounts...</p>
      </div>

      <!-- No Accounts State -->
      <div v-else-if="!accountsStore.hasAccounts" class="p-4 text-center">
        <div class="w-16 h-16 mx-auto mb-3 rounded-full bg-gray-100 flex items-center justify-center">
          <svg class="w-8 h-8 text-gray-400" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073z"/>
          </svg>
        </div>
        <p class="text-sm text-gray-600 font-medium">No accounts linked</p>
        <p class="text-xs text-gray-500 mt-1">Connect an Instagram Business Account to get started</p>
        <button
          @click="showOAuthModal = true"
          class="mt-4 px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white text-sm font-medium rounded-lg hover:opacity-90 transition-opacity"
        >
          Connect Instagram
        </button>
      </div>

      <!-- Accounts List -->
      <div v-else class="py-2">
        <button
          v-for="account in accountsStore.accounts"
          :key="account.account_id"
          @click="selectAccount(account)"
          class="w-full px-4 py-3 hover:bg-white transition-colors border-l-4 flex items-center gap-3"
          :class="{
            'bg-white border-instagram-blue': isSelected(account),
            'border-transparent': !isSelected(account)
          }"
        >
          <!-- Profile Picture -->
          <div class="relative flex-shrink-0">
            <img
              v-if="account.profile_picture_url"
              :src="getProxiedImageUrl(account.profile_picture_url)"
              :alt="account.username"
              class="w-10 h-10 rounded-full object-cover"
              @error="account.profile_picture_url = null"
            />
            <div
              v-else
              class="w-10 h-10 rounded-full bg-gradient-to-br from-purple-400 to-pink-400 flex items-center justify-center"
            >
              <span class="text-white font-semibold text-sm">{{ getInitials(account.username) }}</span>
            </div>
          </div>

          <!-- Account Info -->
          <div class="flex-1 min-w-0 text-left">
            <div class="flex items-center gap-2">
              <span class="text-sm font-semibold text-gray-900 truncate">@{{ account.username }}</span>
            </div>
            <div class="text-xs text-gray-500 truncate">{{ account.role || 'owner' }}</div>
          </div>

          <!-- Selected Indicator -->
          <div v-if="isSelected(account)" class="flex-shrink-0">
            <svg class="w-5 h-5 text-instagram-blue" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
            </svg>
          </div>
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

        <!-- Force Reauth Checkbox -->
        <div class="mb-6">
          <label class="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              v-model="forceReauth"
              class="mt-1 w-4 h-4 text-instagram-blue border-gray-300 rounded focus:ring-instagram-blue"
            />
            <div class="flex-1">
              <div class="font-medium text-sm">Force re-authentication (Recommended)</div>
              <div class="text-xs text-gray-500 mt-0.5">
                Prevents OAuth caching issues when linking previously authorized accounts
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
            <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
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
const forceReauth = ref(true)  // Default to true to prevent OAuth caching issues

onMounted(async () => {
  // Fetch accounts when component mounts
  if (sessionStore.isAuthenticated) {
    await accountsStore.fetchAccounts()
  }
})

function getInitials(username) {
  if (!username) return '?'
  return username.substring(0, 2).toUpperCase()
}

function isSelected(account) {
  return accountsStore.selectedAccount?.account_id === account.account_id
}

function selectAccount(account) {
  accountsStore.selectAccount(account.account_id)
}

async function handleLogout() {
  await sessionStore.logout()
  router.push('/login')
}

async function handleOAuthLogin() {
  try {
    await accountsStore.startOAuthFlow(forceReauth.value)
  } catch (err) {
    console.error('OAuth flow error:', err)
  }
}
</script>

<style scoped>
/* Custom scrollbar for accounts list */
.overflow-y-auto::-webkit-scrollbar {
  width: 6px;
}

.overflow-y-auto::-webkit-scrollbar-track {
  background: transparent;
}

.overflow-y-auto::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 3px;
}

.overflow-y-auto::-webkit-scrollbar-thumb:hover {
  background: #9ca3af;
}
</style>
