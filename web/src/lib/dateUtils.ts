/**
 * Date utility functions for handling UTC dates from backend
 *
 * Backend stores dates in UTC without timezone suffix.
 * These utilities ensure proper conversion to user's local timezone.
 */

/**
 * Parse a UTC date string from the backend and convert to local Date object.
 * Handles both ISO strings with and without 'Z' suffix.
 */
export function parseUTCDate(dateString: string | null | undefined): Date | null {
  if (!dateString) return null

  // If the string doesn't end with Z or timezone offset, treat it as UTC
  let normalized = dateString
  if (!dateString.endsWith('Z') && !dateString.match(/[+-]\d{2}:\d{2}$/)) {
    normalized = dateString + 'Z'
  }

  return new Date(normalized)
}

/**
 * Get relative time string (e.g., "5 mins ago", "2 hours ago")
 * Properly handles UTC dates from backend.
 */
export function getRelativeTime(dateString: string | null | undefined): string {
  const date = parseUTCDate(dateString)
  if (!date) return 'Unknown'

  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / (1000 * 60))
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins} min${diffMins > 1 ? 's' : ''} ago`
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`
  if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`

  // For older dates, show formatted date in user's locale
  return formatLocalDate(date)
}

/**
 * Format a date in user's local timezone with date only.
 */
export function formatLocalDate(date: Date | string | null | undefined): string {
  const d = typeof date === 'string' ? parseUTCDate(date) : date
  if (!d) return 'Unknown'

  return d.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  })
}

/**
 * Format a date in user's local timezone with date and time.
 */
export function formatLocalDateTime(date: Date | string | null | undefined): string {
  const d = typeof date === 'string' ? parseUTCDate(date) : date
  if (!d) return 'Unknown'

  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

/**
 * Format a date in user's local timezone with time only.
 */
export function formatLocalTime(date: Date | string | null | undefined): string {
  const d = typeof date === 'string' ? parseUTCDate(date) : date
  if (!d) return 'Unknown'

  return d.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit'
  })
}

/**
 * Sort array by date field (newest first).
 * Properly handles UTC dates from backend.
 */
export function sortByDateDesc<T>(items: T[], dateField: keyof T): T[] {
  return [...items].sort((a, b) => {
    const dateA = parseUTCDate(a[dateField] as string)
    const dateB = parseUTCDate(b[dateField] as string)
    if (!dateA || !dateB) return 0
    return dateB.getTime() - dateA.getTime()
  })
}
