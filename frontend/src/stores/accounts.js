/**
 * Accounts Store - Manages user's linked Instagram business accounts
 *
 * Handles:
 * - Fetching user's linked accounts
 * - Switching between accounts (session-only, not persisted)
 * - Initiating OAuth flow to link new accounts
 * - Unlinking accounts
 *
 * Note: "Focused account" is simply the selectedAccountId - it's not persisted
 * to the database. On page refresh, the first account becomes the default.
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'
import apiClient from '../api/client'
import { useSessionStore } from './session'

export const useAccountsStore = defineStore('accounts', () => {
  // State
  const accounts = ref([])
  const selectedAccountId = ref(null)
  const loading = ref(false)
  const error = ref(null)

  // Computed
  const selectedAccount = computed(() => {
    if (selectedAccountId.value) {
      // Try to find the selected account, fall back to first account if not found
      return accounts.value.find(acc => acc.account_id === selectedAccountId.value) || accounts.value[0] || null
    }
    // Default to first account (the "focused" account is session-only)
    return accounts.value[0] || null
  })

  const hasAccounts = computed(() => accounts.value.length > 0)

  // Actions
  async function fetchAccounts() {
    const sessionStore = useSessionStore()

    if (!sessionStore.isAuthenticated) {
      console.warn('Cannot fetch accounts: not authenticated')
      return
    }

    loading.value = true
    error.value = null

    try {
      const response = await apiClient.get('/accounts/me', {
        headers: {
          Authorization: `Bearer ${sessionStore.token}`
        }
      })

      accounts.value = response.data.accounts || []

      // Set selected account to first account if not already set
      if (!selectedAccountId.value && accounts.value.length > 0) {
        selectedAccountId.value = accounts.value[0].account_id
      }

    } catch (err) {
      console.error('Failed to fetch accounts:', err)
      error.value = err.response?.data?.detail || 'Failed to load accounts'
      accounts.value = []
    } finally {
      loading.value = false
    }
  }

  async function unlinkAccount(accountId) {
    const sessionStore = useSessionStore()

    if (!sessionStore.isAuthenticated) {
      throw new Error('Not authenticated')
    }

    loading.value = true
    error.value = null

    try {
      await apiClient.delete(`/accounts/${accountId}`, {
        headers: {
          Authorization: `Bearer ${sessionStore.token}`
        }
      })

      // Remove from local state
      accounts.value = accounts.value.filter(acc => acc.account_id !== accountId)

      // If we unlinked the selected account, select the first remaining account
      if (selectedAccountId.value === accountId) {
        selectedAccountId.value = accounts.value[0]?.account_id || null
      }

    } catch (err) {
      console.error('Failed to unlink account:', err)
      error.value = err.response?.data?.detail || 'Failed to unlink account'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function startOAuthFlow(forceReauth = false) {
    const sessionStore = useSessionStore()

    if (!sessionStore.isAuthenticated) {
      throw new Error('Not authenticated')
    }

    loading.value = true
    error.value = null

    try {
      // Initialize OAuth flow (OAuth endpoints are at /oauth, not /api/v1)
      // Send frontend_origin so production OAuth callback redirects back here
      const response = await axios.post(
        '/oauth/instagram/init',
        {
          frontend_origin: window.location.origin,
          force_reauth: forceReauth
        },
        {
          headers: {
            Authorization: `Bearer ${sessionStore.token}`
          }
        }
      )

      // Redirect to Instagram OAuth (force_reauth already included in auth_url by backend)
      window.location.href = response.data.auth_url
    } catch (err) {
      console.error('Failed to start OAuth flow:', err)
      error.value = err.response?.data?.detail || 'Failed to start OAuth flow'
      loading.value = false
      throw err
    }
  }

  function selectAccount(accountId) {
    const account = accounts.value.find(acc => acc.account_id === accountId)
    if (account) {
      selectedAccountId.value = accountId
    }
  }

  function $reset() {
    accounts.value = []
    selectedAccountId.value = null
    loading.value = false
    error.value = null
  }

  return {
    // State
    accounts,
    selectedAccountId,
    loading,
    error,

    // Computed
    selectedAccount,
    hasAccounts,

    // Actions
    fetchAccounts,
    unlinkAccount,
    startOAuthFlow,
    selectAccount,
    $reset
  }
})
