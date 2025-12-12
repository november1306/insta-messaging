<template>
  <div :class="['flex', isOutbound ? 'justify-end' : 'justify-start']">
    <div class="flex flex-col" :class="isOutbound ? 'items-end' : 'items-start'">
      <div :class="['max-w-md px-4 py-2 rounded-2xl', bubbleClasses]">
        <!-- Media Attachments -->
        <div v-if="hasAttachments" class="space-y-2 mb-2">
          <div v-for="attachment in message.attachments" :key="attachment.id">
            <!-- Images (JPG, PNG, GIF, WebP) -->
            <img
              v-if="attachment.media_type === 'image'"
              :src="getMediaUrl(attachment)"
              :alt="`${attachment.media_type} attachment`"
              class="rounded-lg max-w-full h-auto cursor-pointer hover:opacity-90 transition-opacity"
              loading="lazy"
              @click="openMediaLightbox(getMediaUrl(attachment))"
              @error="handleImageError(attachment)"
            />

            <!-- Videos (MP4, MOV) -->
            <video
              v-else-if="attachment.media_type === 'video'"
              :src="getMediaUrl(attachment)"
              controls
              class="rounded-lg max-w-full h-auto"
              preload="metadata"
            >
              Your browser does not support video playback.
            </video>

            <!-- Audio (MP3, M4A, OGG) -->
            <audio
              v-else-if="attachment.media_type === 'audio'"
              :src="getMediaUrl(attachment)"
              controls
              class="w-full"
              preload="metadata"
            >
              Your browser does not support audio playback.
            </audio>

            <!-- Files (PDF, DOC, etc.) -->
            <button
              v-else-if="attachment.media_type === 'file'"
              @click="downloadFile(attachment)"
              class="flex items-center gap-2 p-3 bg-white bg-opacity-20 rounded-lg hover:bg-opacity-30 transition-colors cursor-pointer w-full text-left"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <span class="text-sm font-medium">{{ getFileName(attachment) }}</span>
            </button>

            <!-- Like/Heart -->
            <div v-else-if="attachment.media_type === 'like_heart'" class="text-4xl">
              ❤️
            </div>

            <!-- Unknown media type fallback -->
            <div v-else class="text-xs opacity-75">
              📎 {{ attachment.media_type }} attachment
            </div>
          </div>
        </div>

        <!-- Text Message -->
        <p v-if="message.text" class="text-sm whitespace-pre-wrap break-words">{{ message.text }}</p>

        <!-- Timestamp and Status -->
        <div :class="['flex items-center gap-1 mt-1 text-xs', timeClasses]">
          <span>{{ formatTime(message.timestamp) }}</span>
          <span v-if="isOutbound && message.status" class="ml-1">
            {{ statusIcon }}
          </span>
        </div>
      </div>
      <!-- Error message for failed sends -->
      <div v-if="message.status === 'failed' && message.error" class="mt-1 px-3 py-1 bg-red-100 text-red-700 text-xs rounded-lg max-w-md">
        ⚠️ {{ message.error }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useAuthenticatedMedia } from '../composables/useAuthenticatedMedia'

const props = defineProps({
  message: {
    type: Object,
    required: true
  }
})

const { fetchAuthenticatedMedia, downloadAuthenticatedFile } = useAuthenticatedMedia()
const mediaBlobUrls = ref(new Map())

const isOutbound = computed(() => props.message.direction === 'outbound')

const hasAttachments = computed(() => {
  return props.message.attachments && props.message.attachments.length > 0
})

// Load authenticated media when component mounts
onMounted(async () => {
  if (hasAttachments.value) {
    for (const attachment of props.message.attachments) {
      if (attachment.media_url_local && attachment.media_type !== 'like_heart') {
        const blobUrl = await fetchAuthenticatedMedia(attachment.media_url_local)
        if (blobUrl) {
          mediaBlobUrls.value.set(attachment.id, blobUrl)
        }
      }
    }
  }
})

// Get blob URL for attachment or fallback to original
function getMediaUrl(attachment) {
  return mediaBlobUrls.value.get(attachment.id) || `/${attachment.media_url_local}`
}

const bubbleClasses = computed(() => {
  // Outbound messages: blue background with white text (right-aligned)
  // Inbound messages: grey background with dark text (left-aligned)
  if (isOutbound.value) {
    return 'bg-instagram-blue text-white'
  }
  return 'bg-gray-100 text-gray-900'
})

const timeClasses = computed(() => {
  if (isOutbound.value) {
    return 'text-blue-100'
  }
  return 'text-gray-500'
})

const statusIcon = computed(() => {
  switch (props.message.status) {
    case 'sent':
      return '✓'
    case 'delivered':
      return '✓✓'
    case 'read':
      return '✓✓'
    case 'failed':
      return '✗'
    default:
      return '○'
  }
})

function formatTime(timestamp) {
  if (!timestamp) return ''

  const date = new Date(timestamp)
  return date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true
  })
}

function getFileName(attachment) {
  // Extract filename from media_url_local (preferred) or media_url (fallback)
  const url = attachment.media_url_local || attachment.media_url
  if (url) {
    const urlParts = url.split('/')
    const filename = urlParts[urlParts.length - 1]
    return filename || 'Download file'
  }
  return 'Download file'
}

function handleImageError(attachment) {
  // Handle image load errors (e.g., file missing, network error)
  console.error(`Failed to load image: ${attachment.media_url_local}`)

  // Fallback: Try to load from Instagram URL if local file is missing
  if (attachment.media_url && attachment.media_url !== attachment.media_url_local) {
    console.info('Attempting to load from Instagram CDN as fallback...')
    // Note: Instagram URLs expire after 7 days, so this may also fail
    // In production, consider showing a placeholder image instead
  }
}

function openMediaLightbox(mediaUrl) {
  // MVP: Open in new tab (future: add lightbox modal)
  window.open(mediaUrl, '_blank', 'noopener,noreferrer')
}

function downloadFile(attachment) {
  // Use authenticated download for file attachments
  if (attachment.media_url_local) {
    const filename = getFileName(attachment)
    downloadAuthenticatedFile(attachment.media_url_local, filename)
  } else {
    console.error('No local file path available for download')
  }
}
</script>
