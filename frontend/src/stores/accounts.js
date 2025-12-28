/**
 * Accounts Store - Manages user's linked Instagram business accounts
 *
 * Handles:
 * - Fetching user's linked accounts
 * - Switching between accounts (set primary)
 * - Initiating OAuth flow to link new accounts
 * - Unlinking accounts
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'
import apiClient from '@/api/client'
import { useSessionStore } from './session'

export const useAccountsStore = defineStore('accounts', () => {
  // State
  const accounts = ref([])
  const selectedAccountId = ref(null)
  const loading = ref(false)
  const error = ref(null)

  // Computed
  const primaryAccount = computed(() => {
    return accounts.value.find(acc => acc.is_primary) || accounts.value[0] || null
  })

  const selectedAccount = computed(() => {
    if (selectedAccountId.value) {
      return accounts.value.find(acc => acc.account_id === selectedAccountId.value) || primaryAccount.value
    }
    return primaryAccount.value
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

      // Set selected account to primary if not already set
      if (!selectedAccountId.value && primaryAccount.value) {
        selectedAccountId.value = primaryAccount.value.account_id
      }

      console.log(`Fetched ${accounts.value.length} linked Instagram accounts`)
    } catch (err) {
      console.error('Failed to fetch accounts:', err)
      error.value = err.response?.data?.detail || 'Failed to load accounts'
      accounts.value = []
    } finally {
      loading.value = false
    }
  }

  async function setPrimaryAccount(accountId) {
    const sessionStore = useSessionStore()

    if (!sessionStore.isAuthenticated) {
      throw new Error('Not authenticated')
    }

    loading.value = true
    error.value = null

    try {
      await apiClient.post(
        `/accounts/${accountId}/set-primary`,
        {},
        {
          headers: {
            Authorization: `Bearer ${sessionStore.token}`
          }
        }
      )

      // Update local state
      accounts.value = accounts.value.map(acc => ({
        ...acc,
        is_primary: acc.account_id === accountId
      }))

      selectedAccountId.value = accountId

      console.log(`Set primary account: ${accountId}`)
    } catch (err) {
      console.error('Failed to set primary account:', err)
      error.value = err.response?.data?.detail || 'Failed to set primary account'
      throw err
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

      // If we unlinked the selected account, select the primary
      if (selectedAccountId.value === accountId) {
        selectedAccountId.value = primaryAccount.value?.account_id || null
      }

      console.log(`Unlinked account: ${accountId}`)
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
      const response = await axios.post(
        '/oauth/instagram/init',
        {},
        {
          headers: {
            Authorization: `Bearer ${sessionStore.token}`
          }
        }
      )

      let authUrl = response.data.auth_url

      // Add force_reauth to the Instagram OAuth URL if requested
      if (forceReauth) {
        authUrl += (authUrl.includes('?') ? '&' : '?') + 'force_reauth=true'
      }

      // Redirect to Instagram OAuth
      window.location.href = authUrl
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
      console.log(`Selected account: @${account.username}`)
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
    primaryAccount,
    selectedAccount,
    hasAccounts,

    // Actions
    fetchAccounts,
    setPrimaryAccount,
    unlinkAccount,
    startOAuthFlow,
    selectAccount,
    $reset
  }
})
