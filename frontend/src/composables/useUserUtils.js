/**
 * User utility functions
 * Shared utilities for user display and formatting
 */

/**
 * Get user initials from name
 * @param {string} name - User's display name or username
 * @returns {string} Initials (1-2 characters)
 */
export function getInitials(name) {
  if (!name) return '?'

  // Remove @ symbol if present (for Instagram usernames)
  const cleanName = name.replace('@', '')

  // Split by space to check for full names
  const parts = cleanName.split(' ')

  if (parts.length >= 2) {
    // Use first letter of first two parts for full names
    return (parts[0][0] + parts[1][0]).toUpperCase()
  }

  // Use first two characters for single names/usernames
  return cleanName.substring(0, 2).toUpperCase()
}
