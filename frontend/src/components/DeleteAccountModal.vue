<template>
  <div
    class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 px-4"
    @click.self="$emit('close')"
  >
    <div class="bg-white rounded-lg shadow-2xl max-w-md w-full">
      <!-- Header -->
      <div class="px-6 py-4 border-b border-gray-200">
        <div class="flex items-center justify-between">
          <h2 class="text-xl font-bold text-red-600 flex items-center gap-2">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            Delete Account Permanently?
          </h2>
          <button
            @click="$emit('close')"
            class="text-gray-400 hover:text-gray-600 transition-colors"
            title="Close"
          >
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      <!-- Body -->
      <div class="px-6 py-4">
        <!-- Warning Box -->
        <div class="bg-red-50 border-2 border-red-200 rounded-lg p-4 mb-6">
          <p class="font-semibold text-gray-900 mb-3">This will permanently delete:</p>
          <ul class="space-y-2 text-sm text-gray-700">
            <li class="flex items-start gap-2">
              <svg class="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
              <span><strong>Account:</strong> @{{ account.username }}</span>
            </li>
            <li class="flex items-start gap-2">
              <svg class="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
              <span><strong>All conversation history</strong> with customers</span>
            </li>
            <li class="flex items-start gap-2">
              <svg class="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
              <span><strong>All media files</strong> and attachments</span>
            </li>
            <li class="flex items-start gap-2">
              <svg class="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
              <span><strong>CRM integration data</strong></span>
            </li>
          </ul>
          <div class="mt-4 p-3 bg-red-100 border border-red-300 rounded">
            <p class="text-red-800 font-bold text-sm flex items-center gap-2">
              <svg class="w-5 h-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
              </svg>
              This action cannot be undone!
            </p>
          </div>
        </div>

        <!-- Confirmation Input -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">
            Type the username to confirm: <strong class="text-gray-900">{{ account.username }}</strong>
          </label>
          <input
            v-model="confirmationText"
            type="text"
            :placeholder="`Enter ${account.username}`"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-red-500 outline-none transition"
            @keyup.enter="canDelete && confirmDelete()"
            autofocus
          />
          <p v-if="confirmationText && !canDelete" class="mt-2 text-sm text-red-600">
            Username doesn't match. Please type exactly: {{ account.username }}
          </p>
        </div>
      </div>

      <!-- Footer -->
      <div class="px-6 py-4 bg-gray-50 border-t border-gray-200 rounded-b-lg flex gap-3">
        <button
          @click="$emit('close')"
          class="flex-1 px-4 py-2.5 border border-gray-300 text-gray-700 font-medium rounded-lg hover:bg-gray-100 transition-colors"
        >
          Cancel
        </button>
        <button
          @click="confirmDelete"
          :disabled="!canDelete || deleting"
          class="flex-1 px-4 py-2.5 bg-red-600 text-white font-semibold rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
        >
          <svg
            v-if="deleting"
            class="animate-spin h-5 w-5 text-white"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span>{{ deleting ? 'Deleting...' : 'Delete Permanently' }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  account: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['close', 'confirm'])

const confirmationText = ref('')
const deleting = ref(false)

const canDelete = computed(() => {
  return confirmationText.value.trim() === props.account.username
})

function confirmDelete() {
  if (!canDelete.value || deleting.value) return
  deleting.value = true
  emit('confirm')
}
</script>

<style scoped>
/* Add smooth transitions for modal appearance */
.fixed {
  animation: fadeIn 0.2s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.bg-white {
  animation: slideUp 0.3s ease-out;
}

@keyframes slideUp {
  from {
    transform: translateY(20px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}
</style>
