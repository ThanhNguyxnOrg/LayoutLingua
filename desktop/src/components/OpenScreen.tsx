import { useState, useRef, useEffect } from 'react'
import {
  type HistoryItem,
  getHistory,
  addHistoryItem,
  clearHistory,
} from '../services/history'
import { IconUpload, IconFile, IconLock, IconError, IconArrowR, IconFolder } from './icons'
import { Button, StateNotice, StatusIndicator } from './ui'
import { apiUrl } from '../services/api'

type Err = null | 'unsupported' | 'password' | 'badpw'

export interface SelectedDocument {
  name: string
  size?: number
  pages?: number
  path?: string
  id?: string
  detectedLang?: string
  isScanned?: boolean
  scanWarning?: string
}

export default function OpenScreen({
  onOpen,
}: {
  onOpen: (doc?: SelectedDocument) => void
}) {
  const [err, setErr] = useState<Err>(null)
  const [drag, setDrag] = useState(false)
  const [pw, setPw] = useState('')
  const [list, setList] = useState<HistoryItem[]>([])
  const [file, setFile] = useState('')
  const [loading, setLoading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    setList(getHistory())
  }, [])

  const handleFiles = async (f?: File) => {
    if (!f) return
    setFile(f.name)
    if (!f.name.toLowerCase().endsWith('.pdf')) {
      setErr('unsupported')
      return
    }

    setErr(null)
    setLoading(true)

    let backendDoc: SelectedDocument = {
      name: f.name,
      size: f.size,
      pages: Math.max(1, Math.min(60, Math.round(f.size / 450000))),
      path: undefined,
    }

    try {
      // Upload to LayoutLingua core backend (PyMuPDF engine)
      const res = await fetch(apiUrl('/api/upload'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/pdf',
          'X-Filename': encodeURIComponent(f.name),
        },
        body: f,
      })

      if (res.ok) {
        const data = await res.json()
        backendDoc = {
          name: data.name || f.name,
          size: data.size || f.size,
          pages: data.page_count || backendDoc.pages,
          id: data.id,
          detectedLang: data.detected_lang,
          isScanned: Boolean(data.is_scanned),
          scanWarning: data.scan_warning,
          path: undefined,
        }
      } else {
        const errJson = await res.json().catch(() => ({}))
        console.error('Backend upload error:', errJson)
        alert(`Backend PDF processing error: ${errJson.error || res.statusText}`)
        setErr('unsupported')
        return
      }
    } catch (e) {
      console.error('Backend connection failed:', e)
      alert(
        'Unable to connect to Python Backend Engine at http://127.0.0.1:8765.\nPlease verify that the backend server is running.'
      )
      setErr('unsupported')
      return
    } finally {
      setLoading(false)
    }

    // Persist real document to recent history
    const updated = addHistoryItem({
      id: backendDoc.id || backendDoc.name,
      name: backendDoc.name,
      pages: backendDoc.pages || 1,
      size: backendDoc.size || 0,
      path: backendDoc.path,
      status: 'pending',
      detectedLang: backendDoc.detectedLang,
    })
    setList(updated)
    onOpen(backendDoc)
  }

  const triggerPicker = () => fileInputRef.current?.click()

  return (
    <main className="flex-1 overflow-auto bg-canvas p-10">
      <div className="mx-auto grid max-w-[1240px] grid-cols-[1fr_360px] gap-10">
        <section aria-labelledby="drop-h" className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] font-bold tracking-wider uppercase text-teal">
              Document Preflight
            </span>
            <span className="size-1 rounded-full bg-line-strong" />
            <span className="text-[12px] text-muted">Bilingual PDF Layout Engine</span>
          </div>
          <h1 id="drop-h" className="mt-2 text-[28px] font-bold tracking-tight text-ink">
            Open a PDF to translate
          </h1>
          <p className="mt-2 max-w-[560px] text-[15px] leading-relaxed text-muted">
            LayoutLingua translates text while preserving original page geometry, mathematical equations,
            table grid structures, and navigation links. Anything it cannot preserve safely is reported for human review.
          </p>

          <label
            onDragOver={(e) => {
              e.preventDefault()
              setDrag(true)
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault()
              setDrag(false)
              handleFiles(e.dataTransfer.files[0])
            }}
            className={`mt-8 flex h-[260px] cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed bg-white text-center transition-all shadow-2xs ${
              drag
                ? 'border-teal bg-teal-soft/50 scale-[1.01]'
                : 'border-line-strong hover:border-teal/70 hover:shadow-sm'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              className="sr-only"
              accept="application/pdf,.pdf"
              onChange={(e) => handleFiles(e.target.files?.[0])}
            />
            <span className="flex size-14 items-center justify-center rounded-xl bg-teal-soft text-teal shadow-2xs">
              <IconUpload className="size-7" />
            </span>
            <p className="mt-4 text-[15.5px] font-bold text-ink">
              {loading ? 'Uploading & parsing document...' : 'Drop a PDF here, or click to choose file'}
            </p>
            <p className="mt-1 text-[13px] text-muted">
              PDF 1.4 – 2.0 with selectable text. Scanned pages require OCR preprocessing.
            </p>
          </label>

          <div className="mt-5 flex items-center gap-3">
            <Button variant="primary" onClick={triggerPicker} className="shadow-2xs" disabled={loading}>
              <IconFolder className="size-4" />
              Choose PDF File
            </Button>
            <span className="ml-auto text-[12.5px] text-muted font-mono">
              Fast, high-fidelity local translation
            </span>
          </div>

          {err && (
            <div className="mt-6 rounded-xl border border-line bg-white p-5 shadow-sm animate-in fade-in" role="alert">
              {err === 'unsupported' && (
                <StateNotice
                  tone="error"
                  icon={<IconError className="size-5" />}
                  title={`${file} is not a valid PDF document`}
                  actions={
                    <>
                      <Button size="sm" variant="primary" onClick={triggerPicker}>
                        Choose another file
                      </Button>
                      <Button size="sm" onClick={() => setErr(null)}>
                        Dismiss
                      </Button>
                    </>
                  }
                >
                  LayoutLingua operates strictly on PDF documents to guarantee visual geometry preservation.
                  Please provide a file with a .pdf extension.
                </StateNotice>
              )}
              {(err === 'password' || err === 'badpw') && (
                <StateNotice
                  tone="neutral"
                  icon={<IconLock className="size-5" />}
                  title={`${file} is password-protected`}
                >
                  Enter the document decryption password. The password is only used in memory to parse this file and is never persisted.
                  <form
                    className="mt-3.5 flex items-end gap-2.5"
                    onSubmit={(e) => {
                      e.preventDefault()
                      if (pw.trim().length < 4) {
                        setErr('badpw')
                      } else {
                        setPw('')
                        onOpen({
                          name: file || 'Protected-Document.pdf',
                          size: 1800000,
                          pages: 6,
                          path: undefined,
                        })
                      }
                    }}
                  >
                    <label className="flex flex-col gap-1.5 text-[12.5px] font-semibold text-ink">
                      Document Password
                      <input
                        type="password"
                        value={pw}
                        onChange={(e) => setPw(e.target.value)}
                        autoFocus
                        placeholder="Enter password..."
                        aria-invalid={err === 'badpw'}
                        className={`h-9 w-64 rounded-md border bg-white px-3 text-sm font-normal ${
                          err === 'badpw' ? 'border-red ring-1 ring-red' : 'border-line-strong'
                        }`}
                      />
                    </label>
                    <Button size="md" variant="primary" type="submit">
                      Unlock & Open
                    </Button>
                    <Button size="md" type="button" onClick={() => setErr(null)}>
                      Cancel
                    </Button>
                  </form>
                  {err === 'badpw' ? (
                    <p className="mt-2 text-[12.5px] font-semibold text-red">
                      Password incorrect. Please check credentials and try again.
                    </p>
                  ) : (
                    <p className="mt-2 text-[12px] text-muted">
                      LayoutLingua decrypts documents in memory and never sends passwords or keys over the network.
                    </p>
                  )}
                </StateNotice>
              )}
            </div>
          )}

          <div className="mt-12 border-t border-line pt-8">
            <h2 className="text-[13px] font-bold tracking-wider uppercase text-muted">
              Document Translation Pipeline
            </h2>
            <ol className="mt-4 grid grid-cols-4 gap-6">
              {[
                ['01', 'Open & Parse', 'Visual structure, vectors, and font ink metrics are extracted locally.'],
                ['02', 'Translate', 'Prose and table cells are translated while isolating mathematical formulas.'],
                ['03', 'Typeset & Fit', 'Bilingual text is rendered with adaptive font scaling and line floors.'],
                ['04', 'Review & Export', 'Page transactions and visual integrity metrics are reviewed before export.'],
              ].map(([num, title, desc]) => (
                <li key={title} className="rounded-lg border border-line/60 bg-white p-4 shadow-2xs">
                  <span className="font-mono text-[13px] font-bold text-teal">{num}</span>
                  <p className="mt-1.5 text-[14px] font-bold text-ink">{title}</p>
                  <p className="mt-1 text-[12.5px] leading-relaxed text-muted">{desc}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <aside aria-labelledby="recent-h" className="self-start rounded-xl border border-line bg-white shadow-2xs overflow-hidden">
          <div className="flex items-center justify-between border-b border-line px-5 py-4 bg-canvas/30">
            <h2 id="recent-h" className="text-[15px] font-bold text-ink">
              Recent documents
            </h2>
            {list.length > 0 && (
              <button
                className="text-[12.5px] font-semibold text-muted hover:text-ink transition-colors cursor-pointer"
                onClick={() => {
                  clearHistory()
                  setList([])
                }}
              >
                Clear list
              </button>
            )}
          </div>
          {list.length === 0 ? (
            <div className="px-5 py-12 text-center">
              <IconFile className="mx-auto size-8 text-faint" />
              <p className="mt-3 text-[14px] font-bold text-ink">No recent documents</p>
              <p className="mx-auto mt-1 max-w-[260px] text-[12.5px] leading-relaxed text-muted">
                PDFs you open will be stored here with their latest translation state.
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-line">
              {list.map((r) => (
                <li key={r.id || r.name}>
                  <button
                    onClick={() =>
                      onOpen({
                        id: r.id,
                        name: r.name,
                        pages: r.pages,
                        path: r.path,
                        size: r.size,
                        detectedLang: r.detectedLang,
                      })
                    }
                    className="group flex w-full items-center gap-3.5 px-5 py-3.5 text-left hover:bg-canvas/50 transition-colors cursor-pointer"
                  >
                    <span className="flex h-10 w-8 shrink-0 items-end justify-center rounded-sm border border-line-strong bg-white pb-1 shadow-2xs group-hover:border-teal transition-colors">
                      <span className="h-0.5 w-4 bg-teal/60" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[14px] font-bold text-ink group-hover:text-teal transition-colors">
                        {r.name}
                      </span>
                      <span className="mt-0.5 block text-[12px] text-muted font-mono">
                        {r.pages} pp · {r.time}{r.path && r.path !== '~/Documents' ? ` · ${r.path}` : (r.size ? ` · ${(r.size / (1024 * 1024)).toFixed(1)} MB` : '')}
                      </span>
                    </span>
                    <span className="flex flex-col items-end gap-1">
                      <StatusIndicator state={r.status === 'translated' ? 'done' : r.status === 'review' ? 'review' : r.status === 'failed' ? 'failed' : 'not-started'} />
                      <IconArrowR className="size-4 text-teal opacity-0 group-hover:opacity-100 transition-opacity" />
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <p className="border-t border-line px-5 py-3 text-[12px] text-faint bg-canvas/20">
            Click any document to inspect in dual-view workspace.
          </p>
        </aside>
      </div>
    </main>
  )
}
