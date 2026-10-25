import { useState, useEffect } from 'react'
import {
  type HistoryItem,
  getHistory,
  removeHistoryItem,
  clearHistory,
  getPdfBlobFromCache,
  restoreOrVerifyRecentDoc,
} from '../services/history'
import { IconFile, IconCheck, IconAlert, IconError, IconArrowR, IconX, IconUpload } from './icons'
import { Button } from './ui'
import { apiUrl } from '../services/api'

export type { HistoryItem }

export default function HistoryScreen({
  onOpenDoc,
  onNavigateToOpen,
}: {
  onOpenDoc: (item: HistoryItem) => void
  onNavigateToOpen?: () => void
}) {
  const [items, setItems] = useState<HistoryItem[]>([])
  const [query, setQuery] = useState('')

  useEffect(() => {
    let active = true
    const rawList = getHistory()
    setItems(rawList)
    ;(async () => {
      for (const item of rawList) {
        const checkRes = await fetch(
          apiUrl(
            `/api/session-status?id=${encodeURIComponent(item.id)}&name=${encodeURIComponent(item.name)}`
          )
        ).catch(() => null)
        const checkData = checkRes && checkRes.ok ? await checkRes.json().catch(() => null) : null
        if (checkData?.exists) continue
        const idbBytes = await getPdfBlobFromCache(item.id, item.name)
        if (!idbBytes && active) {
          const updated = removeHistoryItem(item.id || item.name)
          setItems(updated)
        }
      }
    })()
    return () => {
      active = false
    }
  }, [])

  const handleSelectDoc = async (item: HistoryItem) => {
    const restored = await restoreOrVerifyRecentDoc(item, apiUrl)
    if (restored.ok) {
      onOpenDoc({
        ...item,
        id: restored.id || item.id,
        name: restored.name || item.name,
        pages: restored.pages || item.pages,
        size: restored.size || item.size,
        detectedLang: restored.detectedLang || item.detectedLang,
      })
    } else {
      const updated = removeHistoryItem(item.id || item.name)
      setItems(updated)
      if (onNavigateToOpen) onNavigateToOpen()
    }
  }

  const filtered = items.filter(
    (i) =>
      i.name.toLowerCase().includes(query.toLowerCase()) ||
      (i.path && i.path.toLowerCase().includes(query.toLowerCase()))
  )

  const handleRemove = (idOrName: string) => {
    const updated = removeHistoryItem(idOrName)
    setItems(updated)
  }

  const handleClear = () => {
    clearHistory()
    setItems([])
  }

  return (
    <main className="flex-1 overflow-auto bg-canvas p-10">
      <div className="mx-auto max-w-[960px]">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-[26px] font-bold tracking-tight text-ink">Recent Document History</h1>
            <p className="mt-1 text-[14px] text-muted">
              Previously processed and translated documents. Click any item to re-inspect in workspace.
            </p>
          </div>
          {items.length > 0 && (
            <Button size="sm" onClick={handleClear} className="hover:text-red hover:border-red/40">
              Clear all history
            </Button>
          )}
        </div>

        {items.length > 0 && (
          <div className="mb-6">
            <input
              type="search"
              value={query}
              placeholder="Search recent documents by filename or path..."
              onChange={(e) => setQuery(e.target.value)}
              className="h-10 w-full rounded-lg border border-line-strong bg-white px-4 text-[14px] shadow-2xs focus:border-teal focus:ring-1 focus:ring-teal"
            />
          </div>
        )}

        {filtered.length === 0 ? (
          <div className="rounded-xl border border-line bg-white p-12 text-center shadow-2xs">
            <div className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-canvas text-muted">
              <IconFile className="size-7" />
            </div>
            <h3 className="mt-4 text-[17px] font-bold text-ink">
              {items.length === 0 ? 'No document history yet' : 'No matching documents found'}
            </h3>
            <p className="mx-auto mt-1 max-w-[420px] text-[13.5px] leading-relaxed text-muted">
              {items.length === 0
                ? 'Documents you open and translate will automatically appear here with their latest progress and visual integrity status.'
                : 'Try adjusting your search query to find documents.'}
            </p>
            {onNavigateToOpen && (
              <div className="mt-6">
                <Button variant="primary" onClick={onNavigateToOpen} className="shadow-2xs">
                  <IconUpload className="size-4" />
                  Open a PDF to translate
                </Button>
              </div>
            )}
          </div>
        ) : (
          <div className="rounded-xl border border-line bg-white shadow-2xs divide-y divide-line overflow-hidden">
            {filtered.map((item) => (
              <div
                key={item.id || item.name}
                className="flex items-center justify-between p-4.5 hover:bg-canvas/40 transition-colors group"
              >
                <div
                  className="flex items-center gap-4 min-w-0 flex-1 cursor-pointer"
                  onClick={() => handleSelectDoc(item)}
                >
                  <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-teal-soft text-teal">
                    <IconFile className="size-5" />
                  </div>
                  <div className="min-w-0">
                    <h3 className="text-[14.5px] font-bold text-ink truncate group-hover:text-teal transition-colors">
                      {item.name}
                    </h3>
                    <p className="mt-0.5 text-[12.5px] text-muted font-mono truncate">
                      {item.pages} pages · {item.time}{item.path && item.path !== '~/Documents' ? ` · ${item.path}` : (item.size ? ` · ${(item.size / (1024 * 1024)).toFixed(1)} MB` : '')}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3.5 shrink-0">
                  <span
                    className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[12px] font-bold ${
                      item.status === 'translated'
                        ? 'bg-teal-soft text-teal'
                        : item.status === 'review'
                        ? 'bg-amber-soft text-amber-ink'
                        : item.status === 'pending'
                        ? 'bg-canvas text-muted border border-line'
                        : 'bg-red-soft text-red'
                    }`}
                  >
                    {item.status === 'translated' && <IconCheck className="size-3" />}
                    {item.status === 'review' && <IconAlert className="size-3" />}
                    {item.status === 'failed' && <IconError className="size-3" />}
                    {item.status === 'translated'
                      ? 'Translated'
                      : item.status === 'review'
                      ? 'Needs review'
                      : item.status === 'pending'
                      ? 'Pending'
                      : 'Failed'}
                  </span>

                  <Button
                    size="sm"
                    variant="primary"
                    onClick={() => handleSelectDoc(item)}
                    className="opacity-90 group-hover:opacity-100"
                  >
                    Open <IconArrowR className="size-3.5" />
                  </Button>

                  <button
                    onClick={() => handleRemove(item.id || item.name)}
                    aria-label="Remove item"
                    className="p-1 rounded text-faint hover:text-red hover:bg-red-soft transition-colors cursor-pointer"
                  >
                    <IconX className="size-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  )
}
