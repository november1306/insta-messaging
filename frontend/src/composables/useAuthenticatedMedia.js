/**
 * Composable for loading media files with authentication
 *
 * HTML <img> and <video> tags cannot send Authorization headers,
 * so we fetch media with credentials and convert to blob URLs.
 */
import { ref, onUnmounted } from 'vue'

// Cache blob URLs to avoid refetching
const blobUrlCache = new Map()

export function useAuthenticatedMedia() {
  const blobUrls = ref(new Set())

  /**
   * Fetch media file with authentication and return blob URL
   * @param {string} mediaPath - Relative path like "media/attachments/mid_abc123_0.jpg" or "media/outbound/acc_xxx/file.png"
   * @returns {Promise<string>} - Blob URL for the media
   */
  async function fetchAuthenticatedMedia(mediaPath) {
    // Check cache first
    if (blobUrlCache.has(mediaPath)) {
      return blobUrlCache.get(mediaPath)
    }

    try {
      // Get JWT token from localStorage
      const token = localStorage.getItem('session_token')
      if (!token) {
        console.error('No session token found for authenticated media request')
        return null
      }

      // Determine endpoint based on path type
      const baseUrl = import.meta.env.DEV ? 'http://localhost:8000' : ''
      let fetchUrl

      if (mediaPath.startsWith('media/attachments/')) {
        // Inbound media (new format): Extract attachment ID
        // Path format: "media/attachments/mid_abc123_0.jpg"
        // Extract: "mid_abc123_0"
        const attachmentId = extractAttachmentId(mediaPath)
        if (!attachmentId) {
          console.error(`Invalid attachment path format: ${mediaPath}`)
          return null
        }
        fetchUrl = `${baseUrl}/media/attachments/${attachmentId}`
      } else if (mediaPath.startsWith('media/outbound/')) {
        // Outbound media (old format): Use full path
        // Path format: "media/outbound/acc_xxx/filename.png"
        // Note: Outbound endpoint is public (no auth required), but we send token anyway
        fetchUrl = `${baseUrl}/${mediaPath}`
      } else if (mediaPath.startsWith('media/') && mediaPath.split('/').length >= 4) {
        // OLD nested inbound format (legacy): media/{channel_id}/{sender_id}/{filename}
        // Serve via generic path endpoint with authentication
        fetchUrl = `${baseUrl}/${mediaPath}`
      } else {
        console.error(`Unknown media path format: ${mediaPath}`)
        return null
      }

      // Fetch media with Authorization header
      const response = await fetch(fetchUrl, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      if (!response.ok) {
        console.error(`Failed to fetch media: ${response.status} ${response.statusText}`)
        return null
      }

      // Convert to blob
      const blob = await response.blob()
      const blobUrl = URL.createObjectURL(blob)

      // Cache the blob URL
      blobUrlCache.set(mediaPath, blobUrl)
      blobUrls.value.add(blobUrl)

      return blobUrl
    } catch (error) {
      console.error('Error fetching authenticated media:', error)
      return null
    }
  }

  /**
   * Download file attachment with authentication
   * @param {string} mediaPath - Relative path like "media/attachments/mid_abc123_0.pdf" or "media/outbound/acc_xxx/file.pdf"
   * @param {string} filename - Desired filename for download
   */
  async function downloadAuthenticatedFile(mediaPath, filename) {
    try {
      // Get JWT token from localStorage
      const token = localStorage.getItem('session_token')
      if (!token) {
        console.error('No session token found for authenticated download')
        return
      }

      // Determine endpoint based on path type
      const baseUrl = import.meta.env.DEV ? 'http://localhost:8000' : ''
      let fetchUrl

      if (mediaPath.startsWith('media/attachments/')) {
        // Inbound media (new format): Extract attachment ID
        const attachmentId = extractAttachmentId(mediaPath)
        if (!attachmentId) {
          console.error(`Invalid attachment path format: ${mediaPath}`)
          return
        }
        fetchUrl = `${baseUrl}/media/attachments/${attachmentId}?download=true`
      } else if (mediaPath.startsWith('media/outbound/')) {
        // Outbound media (old format): Use full path
        fetchUrl = `${baseUrl}/${mediaPath}?download=true`
      } else if (mediaPath.startsWith('media/') && mediaPath.split('/').length >= 4) {
        // OLD nested inbound format (legacy): media/{channel_id}/{sender_id}/{filename}
        fetchUrl = `${baseUrl}/${mediaPath}?download=true`
      } else {
        console.error(`Unknown media path format: ${mediaPath}`)
        return
      }

      // Fetch file with Authorization header
      const response = await fetch(fetchUrl, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      if (!response.ok) {
        console.error(`Failed to download file: ${response.status} ${response.statusText}`)
        return
      }

      // Convert to blob
      const blob = await response.blob()

      // Create temporary download link and trigger download
      const blobUrl = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = blobUrl
      link.download = filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)

      // Cleanup blob URL after a short delay
      setTimeout(() => URL.revokeObjectURL(blobUrl), 100)
    } catch (error) {
      console.error('Error downloading authenticated file:', error)
    }
  }

  /**
   * Extract attachment ID from media path
   * @param {string} mediaPath - Path like "media/attachments/mid_abc123_0.jpg"
   * @returns {string|null} - Attachment ID like "mid_abc123_0" or null if invalid
   */
  function extractAttachmentId(mediaPath) {
    // Path format: "media/attachments/{attachment_id}.{ext}"
    // Example: "media/attachments/mid_abc123_0.jpg" -> "mid_abc123_0"
    const match = mediaPath.match(/media\/attachments\/([^/.]+)/)
    return match ? match[1] : null
  }

  /**
   * Cleanup blob URLs when component unmounts
   */
  onUnmounted(() => {
    blobUrls.value.forEach(url => {
      URL.revokeObjectURL(url)
      // Remove from cache
      for (const [key, value] of blobUrlCache.entries()) {
        if (value === url) {
          blobUrlCache.delete(key)
        }
      }
    })
    blobUrls.value.clear()
  })

  return {
    fetchAuthenticatedMedia,
    downloadAuthenticatedFile
  }
}
