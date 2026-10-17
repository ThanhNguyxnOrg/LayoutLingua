import { useEffect, useRef, useState } from 'react'
import { IconAlert, IconCheck, IconError, IconX, IconDownload, IconFolder } from './icons'
import { Button, StateNotice } from './ui'
import { apiUrl } from '../services/api'

type Step = 'form' | 'saving' | 'success' | 'error'

export default function ExportDialog({
  onClose,
  needsReview,
  preserved,
  initialDocName = 'Research-Paper.pdf',
  docId,
  totalPages = 1,
}: {
  onClose: () => void
  needsReview: number
  preserved: number[]
  initialDocName?: string
  docId?: string
  totalPages?: number
}) {
  const [step, setStep] = useState<Step>('form')
  const [format, setFormat] = useState<'pdf' | 'md'>('pdf')
  const [layoutMode, setLayoutMode] = useState<'mono' | 'bilingual'>('mono')
  const defaultExportName = initialDocName.replace(/\.pdf$/i, '') + '.vi.pdf'
  const [name, setName] = useState(defaultExportName)
  const [dir, setDir] = useState('~/Desktop')
  const [savedPath, setSavedPath] = useState('')
  const [errorMessage, setErrorMessage] = useState('')
  const [systemFolders, setSystemFolders] = useState<Record<string, string>>({})
  const [pickingFolder, setPickingFolder] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const totalP = Math.max(1, totalPages)
  const fname =
    format === 'md'
      ? name.endsWith('.md')
        ? name
        : `${name.replace(/\.pdf$/i, '')}.md`
      : name.toLowerCase().endsWith('.pdf')
      ? name
      : `${name}.pdf`

  // Fetch real system folder paths (Desktop, Downloads, Documents) from backend
  useEffect(() => {
    let active = true
    fetch(apiUrl('/api/system-folders'))
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!active || !data) return
        setSystemFolders(data)
        if (data.Desktop) {
          setDir(data.Desktop)
        }
      })
      .catch(() => {})
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    ref.current?.querySelector<HTMLElement>('input,button')?.focus()
    const k = (e: KeyboardEvent) => e.key === 'Escape' && step !== 'saving' && onClose()
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [step, onClose])

  const handlePickFolder = async () => {
    setPickingFolder(true)
    try {
      // 1. Try backend native folder picker
      const res = await fetch(apiUrl(`/api/pick-folder?initial=${encodeURIComponent(dir)}`))
      if (res.ok) {
        const data = await res.json()
        if (data.path) {
          setDir(data.path)
          setPickingFolder(false)
          return
        }
      }
    } catch {}

    // 2. Fallback to browser showDirectoryPicker if available
    try {
      if ('showDirectoryPicker' in window) {
        const handle = await (window as any).showDirectoryPicker()
        if (handle?.name) {
          setDir(handle.name)
        }
      }
    } catch {}
    setPickingFolder(false)
  }

  const save = async () => {
    setStep('saving')
    setErrorMessage('')

    if (docId) {
      // 1. Save directly to filesystem via backend engine
      try {
        const saveRes = await fetch(apiUrl('/api/save'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            doc_id: docId,
            filename: fname,
            directory: dir,
            mode: layoutMode,
            format: format,
          }),
        })

        if (saveRes.ok) {
          const saveJson = await saveRes.json()
          const finalPath = saveJson.saved_path || `${dir}/${fname}`
          setSavedPath(finalPath)

          // Secondary: trigger browser download in background so browser download history has it
          fetch(apiUrl(`/api/download?id=${encodeURIComponent(docId)}&mode=${layoutMode}&format=${format}`))
            .then((r) => r.blob())
            .then((blob) => {
              const el = document.createElement('a')
              el.href = URL.createObjectURL(blob)
              el.download = fname
              document.body.appendChild(el)
              el.click()
              document.body.removeChild(el)
            })
            .catch(() => {})

          setStep('success')
          return
        } else {
          const errData = await saveRes.json().catch(() => ({}))
          console.warn('Backend direct save error:', errData)
        }
      } catch (e) {
        console.warn('Backend save failed, trying fallback download:', e)
      }

      // 2. Browser direct download fallback
      try {
        const res = await fetch(
          apiUrl(`/api/download?id=${encodeURIComponent(docId)}&mode=${layoutMode}&format=${format}`)
        )
        if (res.ok) {
          const blob = await res.blob()
          const element = document.createElement('a')
          element.href = URL.createObjectURL(blob)
          element.download = fname
          document.body.appendChild(element)
          element.click()
          document.body.removeChild(element)
          setSavedPath(`${dir}/${fname}`)
          setStep('success')
          return
        }
      } catch (e: any) {
        setErrorMessage(e?.message || 'Download connection failed')
      }
    }

    setStep('error')
  }

  const handleOpenFolder = () => {
    if (!savedPath) return
    fetch(apiUrl('/api/open-folder'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: savedPath }),
    }).catch(() => {})
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 backdrop-blur-2xs p-6 select-none animate-in fade-in duration-150">
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby="exp-h"
        className="w-[540px] rounded-xl border border-line bg-white shadow-2xl overflow-hidden"
      >
        <div className="flex items-center justify-between border-b border-line px-6 py-4 bg-canvas/40">
          <h2 id="exp-h" className="text-[17px] font-bold text-ink">
            {step === 'success' ? 'PDF Exported Successfully' : 'Export Translated PDF'}
          </h2>
          <button
            aria-label="Close"
            onClick={onClose}
            disabled={step === 'saving'}
            className="rounded p-1 text-muted hover:bg-canvas transition-colors cursor-pointer"
          >
            <IconX className="size-4" />
          </button>
        </div>

        {(step === 'form' || step === 'saving') && (
          <div className="space-y-4 px-6 py-5">
            <div className="grid grid-cols-[1fr_180px] gap-3">
              <label className="flex flex-col gap-1.5 text-[12.5px] font-semibold text-ink">
                File name
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="h-9 rounded-md border border-line-strong px-3 font-mono text-[13px] font-normal focus:border-teal focus:ring-1 focus:ring-teal"
                />
              </label>
              <label className="flex flex-col gap-1.5 text-[12.5px] font-semibold text-ink">
                Format
                <select
                  value={format}
                  onChange={(e) => {
                    const f = e.target.value as 'pdf' | 'md'
                    setFormat(f)
                    const base = initialDocName.replace(/\.pdf$/i, '')
                    setName(
                      f === 'md'
                        ? `${base}.translated.md`
                        : layoutMode === 'bilingual'
                        ? `${base}.bilingual.pdf`
                        : `${base}.vi.pdf`
                    )
                  }}
                  className="h-9 rounded-md border border-line-strong bg-white px-2.5 text-[13px] font-normal focus:border-teal focus:ring-1 focus:ring-teal cursor-pointer"
                >
                  <option value="pdf">PDF Document (.pdf)</option>
                  <option value="md">Markdown Notes (.md)</option>
                </select>
              </label>
            </div>

            <div className="grid grid-cols-[1fr_auto] items-end gap-3">
              <label className="flex flex-col gap-1.5 text-[12.5px] font-semibold text-ink">
                Export Layout Mode
                <select
                  value={layoutMode}
                  onChange={(e) => {
                    const m = e.target.value as 'mono' | 'bilingual'
                    setLayoutMode(m)
                    const base = initialDocName.replace(/\.pdf$/i, '')
                    setName(m === 'bilingual' ? `${base}.bilingual.pdf` : `${base}.vi.pdf`)
                  }}
                  className="h-9 rounded-md border border-line-strong bg-white px-2.5 text-[13px] font-normal focus:border-teal focus:ring-1 focus:ring-teal cursor-pointer"
                >
                  <option value="mono">Mono (Translated Pages Only)</option>
                  <option value="bilingual">Bilingual (Interleaved Original + Translated)</option>
                </select>
              </label>

              <div className="flex gap-1.5">
                {systemFolders.Desktop && (
                  <button
                    type="button"
                    onClick={() => setDir(systemFolders.Desktop)}
                    className={`h-9 px-2.5 text-[11.5px] font-semibold rounded-md border transition-colors cursor-pointer ${
                      dir === systemFolders.Desktop
                        ? 'border-teal bg-teal/10 text-teal'
                        : 'border-line-strong hover:bg-canvas text-muted'
                    }`}
                  >
                    🖥️ Desktop
                  </button>
                )}
                {systemFolders.Downloads && (
                  <button
                    type="button"
                    onClick={() => setDir(systemFolders.Downloads)}
                    className={`h-9 px-2.5 text-[11.5px] font-semibold rounded-md border transition-colors cursor-pointer ${
                      dir === systemFolders.Downloads
                        ? 'border-teal bg-teal/10 text-teal'
                        : 'border-line-strong hover:bg-canvas text-muted'
                    }`}
                  >
                    📥 Downloads
                  </button>
                )}
              </div>
            </div>

            {/* Custom Location Path Picker */}
            <div className="flex flex-col gap-1.5 text-[12.5px] font-semibold text-ink">
              <span className="flex items-center justify-between">
                <span>Save destination folder</span>
                <span className="text-[11px] text-muted font-normal">Direct filesystem export</span>
              </span>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={dir}
                  onChange={(e) => setDir(e.target.value)}
                  placeholder="e.g. C:\Users\Admin\Desktop or custom folder"
                  className="h-9 flex-1 rounded-md border border-line-strong px-3 font-mono text-[12.5px] font-normal focus:border-teal focus:ring-1 focus:ring-teal bg-white"
                />
                <Button
                  size="sm"
                  type="button"
                  onClick={handlePickFolder}
                  disabled={pickingFolder}
                  className="h-9 px-3 shrink-0 flex items-center gap-1.5 border-line-strong hover:border-ink cursor-pointer"
                >
                  <IconFolder className="size-3.5" />
                  {pickingFolder ? 'Selecting…' : 'Browse…'}
                </Button>
              </div>
              <span className="text-[11px] text-muted">
                Files will be written directly to this directory on your computer.
              </span>
            </div>

            {layoutMode === 'bilingual' && (
              <div className="rounded-lg border border-teal/40 bg-teal-soft/20 p-3 text-[12.5px] text-teal-ink flex items-center gap-2">
                <span>📖</span>
                <span>
                  <strong>Bilingual Mode Active:</strong> Interleaves original and translated pages (Original 1 →
                  Translated 1 → Original 2 → Translated 2...) for easy comparison.
                </span>
              </div>
            )}

            <div className="rounded-lg border border-line bg-canvas/30 p-3.5">
              <p className="text-[12px] font-bold uppercase tracking-wider text-muted mb-2">
                Document integrity status
              </p>
              <ul className="divide-y divide-line/60 text-[13px]">
                <li className="flex items-center gap-2.5 py-1.5">
                  <IconCheck className="size-4 text-teal" />
                  <span className="flex-1 font-medium text-ink">Pages translated & fitted</span>
                  <span className="font-mono text-muted">
                    {totalP - preserved.length} / {totalP}
                  </span>
                </li>
                <li className="flex items-center gap-2.5 py-1.5">
                  <IconAlert className="size-4 text-amber" />
                  <span className="flex-1 font-medium text-ink">Warnings unreviewed</span>
                  <span className="font-mono text-muted">{needsReview}</span>
                </li>
                <li className="flex items-center gap-2.5 py-1.5">
                  <IconError className="size-4 text-red" />
                  <span className="flex-1 font-medium text-ink">Preserved from source (untranslated)</span>
                  <span className="font-mono text-muted">
                    {preserved.length ? `p. ${preserved.join(', ')}` : '0'}
                  </span>
                </li>
              </ul>
            </div>
          </div>
        )}

        {step === 'success' && (
          <div className="px-6 py-6 space-y-4">
            <StateNotice tone="success" icon={<IconCheck className="size-5" />} title="File exported and saved!">
              <span className="block text-muted text-[12.5px] leading-relaxed">
                Your translated document has been successfully compiled and written to your disk with original vector
                geometry, equations, and typography preserved.
              </span>
            </StateNotice>

            <div className="rounded-lg border border-line bg-canvas/50 p-3 space-y-1">
              <span className="text-[11px] font-bold uppercase text-muted tracking-wider">Saved Location:</span>
              <div className="font-mono text-[12.5px] text-ink break-all select-all font-semibold bg-white p-2.5 rounded border border-line">
                {savedPath || `${dir}/${fname}`}
              </div>
            </div>
          </div>
        )}

        {step === 'error' && (
          <div className="px-6 py-6">
            <StateNotice tone="error" icon={<IconError className="size-5" />} title="The PDF could not be saved">
              Writing to <span className="font-mono text-ink">{dir}</span> failed.{' '}
              {errorMessage ? `Error: ${errorMessage}. ` : ''}Your translation is still open in workspace and nothing was
              lost.
            </StateNotice>
          </div>
        )}

        <div className="flex justify-between items-center border-t border-line bg-canvas/20 px-6 py-4">
          {step === 'success' ? (
            <>
              <Button
                variant="primary"
                size="md"
                onClick={handleOpenFolder}
                className="flex items-center gap-1.5 cursor-pointer"
              >
                <IconFolder className="size-4" />
                Open in File Explorer
              </Button>
              <Button size="md" onClick={onClose} className="cursor-pointer">
                Done
              </Button>
            </>
          ) : step === 'error' ? (
            <>
              <Button size="md" onClick={() => setStep('form')} className="cursor-pointer">
                Change folder path
              </Button>
              <Button variant="primary" size="md" onClick={save} className="cursor-pointer">
                Try again
              </Button>
            </>
          ) : (
            <>
              <Button size="md" onClick={onClose} disabled={step === 'saving'} className="cursor-pointer">
                Cancel
              </Button>
              <Button
                variant="primary"
                size="md"
                disabled={step === 'saving' || !name.trim()}
                onClick={save}
                className="cursor-pointer flex items-center gap-1.5"
              >
                <IconDownload className="size-4" />
                {step === 'saving' ? 'Exporting PDF…' : 'Export PDF'}
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
