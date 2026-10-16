export interface HistoryItem {
  id: string
  name: string
  pages: number
  size: number
  time: string
  path?: string
  status: 'translated' | 'review' | 'failed' | 'pending'
  detectedLang?: string
  targetLang?: string
}

const STORAGE_KEY = 'layoutlingua_recent_history_v1'

function formatRelativeTime(date: Date): string {
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / (1000 * 60))
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export function getHistory(): HistoryItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) return parsed
    return []
  } catch {
    return []
  }
}

export function saveHistory(items: HistoryItem[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, 50)))
  } catch (e) {
    console.warn('Failed to save history to localStorage:', e)
  }
}

export function addHistoryItem(item: {
  id: string
  name: string
  pages: number
  size: number
  path?: string
  status?: 'translated' | 'review' | 'failed' | 'pending'
  detectedLang?: string
  targetLang?: string
}): HistoryItem[] {
  const current = getHistory()
  const now = new Date()
  const timeStr = formatRelativeTime(now)

  // Deduplicate by id or name
  const filtered = current.filter((i) => i.id !== item.id && i.name !== item.name)

  const newItem: HistoryItem = {
    id: item.id,
    name: item.name,
    pages: item.pages,
    size: item.size,
    time: timeStr,
    path: item.path || '~/Documents',
    status: item.status || 'pending',
    detectedLang: item.detectedLang || 'en',
    targetLang: item.targetLang || 'vi',
  }

  const updated = [newItem, ...filtered]
  saveHistory(updated)
  return updated
}

export function updateHistoryStatus(
  idOrName: string,
  status: 'translated' | 'review' | 'failed'
): void {
  const current = getHistory()
  const updated = current.map((item) => {
    if (item.id === idOrName || item.name === idOrName) {
      return { ...item, status }
    }
    return item
  })
  saveHistory(updated)
}

export function removeHistoryItem(idOrName: string): HistoryItem[] {
  const current = getHistory()
  const updated = current.filter((item) => item.id !== idOrName && item.name !== idOrName)
  saveHistory(updated)
  return updated
}

export function clearHistory(): void {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch (e) {
    console.warn('Failed to clear history:', e)
  }
}
