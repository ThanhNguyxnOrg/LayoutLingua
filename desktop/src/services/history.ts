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

export function formatDocSize(bytes?: number): string {
  if (!bytes || bytes <= 0) return ''
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(0)} KB`
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const LEGACY_MOCK_IDS = new Set([
  'demo-research-paper',
  'demo-thermal-report',
  'demo-lecture-signals',
])

const LEGACY_MOCK_NAMES = new Set([
  'Research-Paper.pdf',
  'Thermal-Analysis-Report.pdf',
  'Lecture-07-Signals.pdf',
])

export function getHistory(): HistoryItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) {
      return []
    }
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) {
      const cleaned = parsed
        .filter(
          (item) =>
            item &&
            !LEGACY_MOCK_IDS.has(item.id) &&
            !LEGACY_MOCK_NAMES.has(item.name)
        )
        .map((item) => ({
          ...item,
          path: item.path && item.path !== '~/Documents' ? item.path : undefined,
        }))
      if (cleaned.length !== parsed.length) {
        saveHistory(cleaned)
      }
      return cleaned
    }
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

  const cleanPath = item.path && item.path !== '~/Documents' ? item.path : undefined

  const newItem: HistoryItem = {
    id: item.id,
    name: item.name,
    pages: item.pages,
    size: item.size,
    time: timeStr,
    path: cleanPath,
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
  clearPdfFilesCache().catch(() => {})
}

const IDB_NAME = 'layoutlingua_pdf_cache_v1'
const IDB_STORE = 'pdf_blobs'

function openPdfIdb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') {
      reject(new Error('IndexedDB unavailable'))
      return
    }
    const req = indexedDB.open(IDB_NAME, 1)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(IDB_STORE)) {
        db.createObjectStore(IDB_STORE, { keyPath: 'key' })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

export async function savePdfBlobToCache(id: string, name: string, file: Blob): Promise<void> {
  try {
    const buf = await file.arrayBuffer()
    const db = await openPdfIdb()
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(IDB_STORE, 'readwrite')
      const store = tx.objectStore(IDB_STORE)
      const now = Date.now()
      store.put({ key: `id:${id}`, name, bytes: buf, updatedAt: now })
      store.put({ key: `name:${name}`, id, name, bytes: buf, updatedAt: now })
      tx.oncomplete = () => resolve()
      tx.onerror = () => reject(tx.error)
    })
    db.close()
  } catch {
    // Ignore IDB quota or private browsing errors
  }
}

export async function getPdfBlobFromCache(id?: string, name?: string): Promise<ArrayBuffer | null> {
  try {
    const db = await openPdfIdb()
    const lookupKey = (key: string) =>
      new Promise<any>((resolve) => {
        const tx = db.transaction(IDB_STORE, 'readonly')
        const req = tx.objectStore(IDB_STORE).get(key)
        req.onsuccess = () => resolve(req.result)
        req.onerror = () => resolve(null)
      })
    let rec = id ? await lookupKey(`id:${id}`) : null
    if (!rec && name) {
      rec = await lookupKey(`name:${name}`)
    }
    db.close()
    return rec?.bytes instanceof ArrayBuffer ? rec.bytes : null
  } catch {
    return null
  }
}

export async function clearPdfFilesCache(): Promise<void> {
  try {
    const db = await openPdfIdb()
    await new Promise<void>((resolve) => {
      const tx = db.transaction(IDB_STORE, 'readwrite')
      tx.objectStore(IDB_STORE).clear()
      tx.oncomplete = () => resolve()
      tx.onerror = () => resolve()
    })
    db.close()
  } catch {
    // Ignore
  }
}

export async function restoreOrVerifyRecentDoc(
  item: { id?: string; name: string; pages?: number; size?: number; detectedLang?: string },
  apiUrlFn: (path: string) => string
): Promise<{
  ok: boolean
  id?: string
  name?: string
  pages?: number
  size?: number
  detectedLang?: string
}> {
  const docId = item.id || item.name
  try {
    const checkRes = await fetch(
      apiUrlFn(
        `/api/session-status?id=${encodeURIComponent(docId)}&name=${encodeURIComponent(item.name)}`
      )
    )
    if (checkRes.ok) {
      const checkData = await checkRes.json()
      if (checkData.exists) {
        return {
          ok: true,
          id: checkData.id || docId,
          name: checkData.name || item.name,
          pages: checkData.page_count || item.pages,
          size: checkData.size || item.size,
          detectedLang: checkData.detected_lang || item.detectedLang,
        }
      }
    }
  } catch {
    // Continue to IndexedDB recovery
  }

  // Try automatic re-upload from IndexedDB cache
  const cachedBytes = await getPdfBlobFromCache(docId, item.name)
  if (cachedBytes && cachedBytes.byteLength > 100) {
    try {
      const upRes = await fetch(apiUrlFn('/api/upload'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/pdf',
          'X-Filename': encodeURIComponent(item.name),
          'X-Doc-Id': docId,
        },
        body: cachedBytes,
      })
      if (upRes.ok) {
        const upData = await upRes.json()
        return {
          ok: true,
          id: upData.id || docId,
          name: upData.name || item.name,
          pages: upData.page_count || item.pages,
          size: upData.size || item.size,
          detectedLang: upData.detected_lang || item.detectedLang,
        }
      }
    } catch {
      // Fall through
    }
  }

  return { ok: false }
}

