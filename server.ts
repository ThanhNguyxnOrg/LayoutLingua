import express from 'express'
import path from 'node:path'
import fs from 'node:fs'
import os from 'node:os'
import crypto from 'node:crypto'
import { fileURLToPath } from 'node:url'
import { createServer as createViteServer } from 'vite'
import { PDFDocument } from 'pdf-lib'
import {
  getMupdf,
  embedFontBundle,
  translateAndTypesetPage,
  redactSourceProsePages,
  translatePdfOutlines,
  optimizePdfBuffer,
  renderPdfPageToPng,
  detectLanguageFromText,
  type PageTranslationResult,
} from './src/engine/pdfTranslator'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

interface SessionData {
  doc_id: string
  filename: string
  size: number
  source_pdf_bytes: Buffer
  translated_pdf_bytes?: Buffer
  active_out_doc?: PDFDocument
  active_out_dirty?: boolean
  page_count: number
  word_count: number
  detected_lang: string
  target_lang: string
  is_scanned: boolean
  scan_warning: string
  is_translating: boolean
  cancel_requested?: boolean
  selected_pages: number[]
  page_dimensions: Array<{ page_number: number; width: number; height: number }>
  page_results: Record<number, PageTranslationResult>
  page_png_cache: Map<string, Buffer>
  progress: {
    stage_index: number
    stage_name: string
    current_page: number
    total_pages: number
    overall_pct: number
    status: 'idle' | 'processing' | 'done' | 'error' | 'rate-limited'
    speed?: number
    eta_seconds?: number
    message?: string
    subtitle?: string
    integrity?: any
  }
  integrity?: any
}

const sessions = new Map<string, SessionData>()
const SESSIONS_CACHE_DIR = path.join(process.cwd(), '.cache', 'sessions')
try {
  fs.mkdirSync(SESSIONS_CACHE_DIR, { recursive: true })
} catch {
  // Ignore mkdir errors
}

function getSessionDir(docId: string): string {
  const safeId = String(docId || 'default').replace(/[^a-zA-Z0-9_-]/g, '_')
  return path.join(SESSIONS_CACHE_DIR, safeId)
}

function persistSessionToDisk(session: SessionData, savePdfBuffers = false): void {
  try {
    if (!session.doc_id || session.doc_id === 'sample_academic') return
    const dir = getSessionDir(session.doc_id)
    fs.mkdirSync(dir, { recursive: true })

    if (savePdfBuffers) {
      fs.writeFileSync(path.join(dir, 'source.pdf'), session.source_pdf_bytes)
    }
    if (session.translated_pdf_bytes) {
      fs.writeFileSync(path.join(dir, 'translated.pdf'), session.translated_pdf_bytes)
    }

    const meta = {
      doc_id: session.doc_id,
      filename: session.filename,
      size: session.size,
      page_count: session.page_count,
      word_count: session.word_count,
      detected_lang: session.detected_lang,
      target_lang: session.target_lang,
      is_scanned: session.is_scanned,
      scan_warning: session.scan_warning,
      selected_pages: session.selected_pages,
      page_dimensions: session.page_dimensions,
      page_results: session.page_results,
      progress: session.progress,
      integrity: session.integrity,
      updated_at: Date.now(),
    }
    fs.writeFileSync(path.join(dir, 'state.json'), JSON.stringify(meta))
  } catch (err) {
    console.warn('Failed to persist session to disk:', err)
  }
}

function tryLoadSessionFromDir(dir: string, overrideDocId?: string): SessionData | null {
  try {
    const sourcePdfPath = path.join(dir, 'source.pdf')
    const statePath = path.join(dir, 'state.json')
    if (!fs.existsSync(sourcePdfPath) || !fs.existsSync(statePath)) return null

    const sourceBytes = fs.readFileSync(sourcePdfPath)
    const state = JSON.parse(fs.readFileSync(statePath, 'utf-8'))
    const translatedPath = path.join(dir, 'translated.pdf')
    const translatedBytes = fs.existsSync(translatedPath)
      ? fs.readFileSync(translatedPath)
      : undefined

    const effectiveId = overrideDocId || state.doc_id
    const session: SessionData = {
      doc_id: effectiveId,
      filename: state.filename || 'Document.pdf',
      size: state.size || sourceBytes.length,
      source_pdf_bytes: sourceBytes,
      translated_pdf_bytes: translatedBytes,
      page_count: state.page_count || 1,
      word_count: state.word_count || 100,
      detected_lang: state.detected_lang || 'en',
      target_lang: state.target_lang || 'vi',
      is_scanned: Boolean(state.is_scanned),
      scan_warning: state.scan_warning || '',
      is_translating: false,
      selected_pages:
        Array.isArray(state.selected_pages) && state.selected_pages.length > 0
          ? state.selected_pages
          : Array.from({ length: state.page_count || 1 }, (_, i) => i + 1),
      page_dimensions: state.page_dimensions || [],
      page_results: state.page_results || {},
      page_png_cache: new Map(),
      progress:
        state.progress && state.progress.status === 'done'
          ? state.progress
          : {
              stage_index: 0,
              stage_name: 'idle',
              current_page: 0,
              total_pages: state.page_count || 1,
              overall_pct: 0,
              status: 'idle',
            },
      integrity: state.integrity,
    }
    sessions.set(effectiveId, session)
    return session
  } catch {
    return null
  }
}

async function createSessionFromPdfBytes(
  docId: string,
  filename: string,
  pdfBytes: Buffer,
  persist = true
): Promise<SessionData> {
  const mupdf = await getMupdf()
  const doc = mupdf.Document.openDocument(pdfBytes, 'application/pdf')
  const pageCount = Math.max(1, doc.countPages())
  const pageDimensions: Array<{ page_number: number; width: number; height: number }> = []
  let totalWords = 0
  let sampleText = ''
  let pagesWithText = 0

  const inspectLimit = Math.min(pageCount, 12)
  for (let i = 0; i < pageCount; i++) {
    const page = doc.loadPage(i)
    const b = page.getBounds()
    const w = Math.round(b[2] - b[0]) || 595
    const h = Math.round(b[3] - b[1]) || 842
    pageDimensions.push({ page_number: i + 1, width: w, height: h })

    if (i < inspectLimit) {
      const txt = page.toStructuredText('preserve-whitespace').asText().trim()
      if (txt.length > 10) pagesWithText++
      const words = txt.split(/\s+/).filter(Boolean).length
      totalWords += words
      if (sampleText.length < 3000) sampleText += ' ' + txt
    }
  }

  if (pageCount > inspectLimit && inspectLimit > 0) {
    totalWords = Math.round((totalWords / inspectLimit) * pageCount)
  }

  const detectedLang = detectLanguageFromText(sampleText)
  const defaultTargetLang = detectedLang === 'vi' ? 'en' : 'vi'
  const isScanned = pagesWithText === 0 && pageCount > 0

  const session: SessionData = {
    doc_id: docId,
    filename,
    size: pdfBytes.length,
    source_pdf_bytes: pdfBytes,
    page_count: pageCount,
    word_count: Math.max(totalWords, pageCount * 45),
    detected_lang: detectedLang,
    target_lang: defaultTargetLang,
    is_scanned: isScanned,
    scan_warning: isScanned
      ? 'This PDF appears to contain scanned images without extractable vector text.'
      : '',
    is_translating: false,
    selected_pages: Array.from({ length: pageCount }, (_, i) => i + 1),
    page_dimensions: pageDimensions,
    page_results: {},
    page_png_cache: new Map(),
    progress: {
      stage_index: 0,
      stage_name: 'idle',
      current_page: 0,
      total_pages: pageCount,
      overall_pct: 0,
      status: 'idle',
    },
  }

  sessions.set(docId, session)
  if (persist) {
    persistSessionToDisk(session, true)
  }
  return session
}

function findPersistedSession(docId: string, filenameHint?: string): SessionData | null {
  const existing = sessions.get(docId)
  if (existing) return existing

  // 1. Direct lookup in .cache/sessions/<docId>
  const direct = tryLoadSessionFromDir(getSessionDir(docId), docId)
  if (direct) return direct

  // 2. Search in-memory or on-disk sessions by matching filename
  if (filenameHint) {
    for (const s of sessions.values()) {
      if (s.filename === filenameHint && s.doc_id !== 'sample_academic') {
        sessions.set(docId, s)
        return s
      }
    }
  }

  try {
    const entries = fs.readdirSync(SESSIONS_CACHE_DIR, { withFileTypes: true })
    for (const entry of entries) {
      if (!entry.isDirectory()) continue
      const candidateDir = path.join(SESSIONS_CACHE_DIR, entry.name)
      const statePath = path.join(candidateDir, 'state.json')
      if (!fs.existsSync(statePath)) continue
      const state = JSON.parse(fs.readFileSync(statePath, 'utf-8'))
      if (state.doc_id === docId || (filenameHint && state.filename === filenameHint)) {
        const loaded = tryLoadSessionFromDir(candidateDir, docId)
        if (loaded) return loaded
      }
    }
  } catch {
    // Ignore directory read errors
  }

  return null
}

async function getOrRecoverSession(docId: string, filenameHint?: string): Promise<SessionData> {
  const found = findPersistedSession(docId, filenameHint)
  if (found) return found

  const emptyDoc = await PDFDocument.create()
  emptyDoc.addPage([595, 842])
  const fallbackBytes = Buffer.from(await emptyDoc.save())
  return await createSessionFromPdfBytes(docId, 'Document.pdf', fallbackBytes, false)
}

async function startServer() {
  const app = express()
  const PORT = Number(process.env.PORT) || 3000

  // Parse raw binary for /api/upload, JSON for all other API routes
  app.use((req, res, next) => {
    if (req.path === '/api/upload' || req.path === '/upload') {
      express.raw({ type: '*/*', limit: '60mb' })(req, res, next)
    } else {
      express.json({ limit: '15mb' })(req, res, next)
    }
  })

  // 1. Health check
  app.get(['/api/health', '/health'], (_req, res) => {
    res.json({
      status: 'ok',
      version: '2.0.0',
      engine: 'LayoutLingua-MuPDF-VectorEngine',
    })
  })

  // 1b. Check whether a recent document session exists on the server (in memory or on disk)
  app.get(['/api/session-status', '/session-status'], (req, res) => {
    const docId = String(req.query.id || '')
    const nameHint = req.query.name ? String(req.query.name) : undefined
    const found = docId ? findPersistedSession(docId, nameHint) : null
    if (found) {
      res.json({
        exists: true,
        id: found.doc_id,
        name: found.filename,
        size: found.size,
        page_count: found.page_count,
        detected_lang: found.detected_lang,
        target_lang: found.target_lang,
        status: found.progress?.status === 'done' ? 'translated' : 'pending',
      })
    } else {
      res.json({ exists: false })
    }
  })

  // 2. Upload PDF document
  app.post(['/api/upload', '/upload'], async (req, res) => {
    try {
      const rawFilename = (req.headers['x-filename'] as string) || 'Uploaded-Document.pdf'
      const filename = decodeURIComponent(rawFilename)
      const requestedId = (req.headers['x-doc-id'] as string) || ''

      const buf = Buffer.isBuffer(req.body) ? req.body : Buffer.from('')
      if (buf.length < 100) {
        res.status(400).json({ error: 'Invalid or empty PDF file' })
        return
      }

      const contentHashId = crypto.createHash('sha256').update(buf).digest('hex').slice(0, 12)
      const docId = requestedId.trim() || contentHashId
      const existing = findPersistedSession(docId, filename)
      if (existing && existing.size === buf.length && existing.page_count > 1) {
        res.json({
          id: existing.doc_id,
          name: existing.filename,
          size: existing.size,
          page_count: existing.page_count,
          word_count: existing.word_count,
          detected_lang: existing.detected_lang,
          is_scanned: existing.is_scanned,
          scan_warning: existing.scan_warning,
          pages: existing.page_dimensions,
        })
        return
      }

      const session = await createSessionFromPdfBytes(docId, filename, buf, true)

      res.json({
        id: session.doc_id,
        name: session.filename,
        size: session.size,
        page_count: session.page_count,
        word_count: session.word_count,
        detected_lang: session.detected_lang,
        is_scanned: session.is_scanned,
        scan_warning: session.scan_warning,
        pages: session.page_dimensions,
      })
    } catch (err: any) {
      res.status(400).json({ error: `Failed to parse PDF document: ${err?.message || err}` })
    }
  })

  // 3. Real MuPDF Page Preview Rendering (PNG + Layout Block Metadata)
  app.get(['/api/page-preview', '/page-preview'], async (req, res) => {
    try {
      const docId = String(req.query.id || 'sample_academic')
      const pageNum = Math.max(1, parseInt(String(req.query.page || '1'), 10) || 1)
      const previewType =
        String(req.query.type || 'source') === 'translated' ? 'translated' : 'source'
      const format = String(req.query.format || 'png').toLowerCase()

      const session = await getOrRecoverSession(docId)
      const clampedPage = Math.min(pageNum, session.page_count)

      // Return layout block metadata JSON for interactive hover overlay
      if (format === 'meta') {
        const pageRes = session.page_results[clampedPage]
        const dim = session.page_dimensions[clampedPage - 1] || {
          width: 595,
          height: 842,
        }
        res.json({
          page: clampedPage,
          pageW: pageRes?.pageW || dim.width,
          pageH: pageRes?.pageH || dim.height,
          blocks: pageRes?.blocks || [],
        })
        return
      }

      if (
        previewType === 'translated' &&
        session.active_out_doc &&
        session.active_out_dirty &&
        session.page_results[clampedPage]
      ) {
        session.translated_pdf_bytes = Buffer.from(await session.active_out_doc.save())
        session.active_out_dirty = false
      }

      const activePdfBytes =
        previewType === 'translated' && session.translated_pdf_bytes
          ? session.translated_pdf_bytes
          : session.source_pdf_bytes

      const cacheKey = `${previewType}_${clampedPage}_${
        previewType === 'translated' ? session.target_lang : 'src'
      }`
      let pngBuf = session.page_png_cache.get(cacheKey)
      if (!pngBuf) {
        pngBuf = await renderPdfPageToPng(activePdfBytes, clampedPage, 150)
        session.page_png_cache.set(cacheKey, pngBuf)
      }

      res.setHeader('Content-Type', 'image/png')
      res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate')
      res.send(pngBuf)
    } catch (err: any) {
      res.status(500).json({ error: `Preview rendering failed: ${err?.message || err}` })
    }
  })

  // 4. Real Layout-Preserving PDF Translation Pipeline
  app.post(['/api/translate', '/translate'], async (req, res) => {
    try {
      const body = req.body || {}
      const docId = String(body.doc_id || 'sample_academic')
      const sourceLang = String(body.source_lang || 'auto')
      const targetLang = String(body.target_lang || 'vi')
      const pageRange = String(body.page_range || 'all')

      const session = await getOrRecoverSession(docId)
      session.target_lang = targetLang

      // Parse page range (supports "1-5", "3", "all")
      let fromP = 1
      let toP = session.page_count
      if (pageRange && pageRange !== 'all') {
        const m = pageRange.match(/^(\d+)(?:\s*-\s*(\d+))?$/)
        if (m) {
          fromP = Math.max(1, Math.min(parseInt(m[1], 10), session.page_count))
          toP = Math.max(fromP, Math.min(m[2] ? parseInt(m[2], 10) : fromP, session.page_count))
        }
      }
      const selectedPages: number[] = []
      for (let p = fromP; p <= toP; p++) selectedPages.push(p)
      session.selected_pages = selectedPages

      if (session.is_translating) {
        res.json({
          status: 'processing',
          doc_id: session.doc_id,
          message: 'Translation already in progress',
        })
        return
      }

      session.is_translating = true
      session.cancel_requested = false
      const totalSelected = selectedPages.length
      session.progress = {
        stage_index: 0,
        stage_name: 'Reading document structure',
        current_page: 0,
        total_pages: totalSelected,
        overall_pct: 4,
        status: 'processing',
        speed: 1.5,
        eta_seconds: Math.max(2, totalSelected * 2),
        message: 'Extracting character quads, isolating math formulas & vector obstacles...',
      }

      res.json({
        status: 'processing',
        doc_id: session.doc_id,
        total_pages: totalSelected,
        message: 'Translation job started',
      })

      // Execute asynchronous page-by-page layout-aware translation
      ;(async () => {
        const startTime = Date.now()
        try {
          const mupdf = await getMupdf()
          const mupdfDoc = mupdf.Document.openDocument(
            session.source_pdf_bytes,
            'application/pdf'
          )

          // PASS 1 (pre-pass): physically redact the source prose glyphs from a private MuPDF
          // copy of the document so the output content stream carries no original text, while
          // the surviving page resources (frozen math forms, decorations) stay self-consistent.
          const resolvedSourceLang = sourceLang === 'auto' ? session.detected_lang : sourceLang
          let outputSourceBytes = session.source_pdf_bytes
          const paintOverPages = new Set<number>(selectedPages.map((p) => p - 1))
          try {
            const redactRes = await redactSourceProsePages(
              session.source_pdf_bytes,
              selectedPages.map((p) => p - 1),
              resolvedSourceLang,
              targetLang
            )
            if (redactRes.bytes) {
              outputSourceBytes = redactRes.bytes
              for (const p of selectedPages) {
                if (!redactRes.failedPages.includes(p - 1)) paintOverPages.delete(p - 1)
              }
            }
          } catch {
            // Fail closed: keep the original bytes and paint over prose during typesetting
          }

          const outDoc = await PDFDocument.load(outputSourceBytes)
          session.active_out_doc = outDoc
          session.active_out_dirty = false
          const fontBundle = await embedFontBundle(outDoc, targetLang)
          const effectiveSourceLang = sourceLang === 'auto' ? session.detected_lang : sourceLang
          const translationOpts = {
            provider: body.provider,
            geminiKey: body.gemini_key,
            geminiModel: body.gemini_model,
            openaiKey: body.openai_key,
            openaiEndpoint: body.openai_endpoint,
            openaiModel: body.openai_model,
            minFontShrink: body.min_font_shrink,
            customGlossary: body.custom_glossary,
          }

          // Translate PDF Document Catalog /Outlines (Bookmark / Table of Contents tree)
          await translatePdfOutlines(outDoc, effectiveSourceLang, targetLang, translationOpts)
          const pageStatuses: Record<number, string> = {}
          const pageBlockCounts: Record<number, number> = {}
          const pageMathCounts: Record<number, number> = {}
          const completedPages: Record<number, boolean> = {}
          const allIssues: PageTranslationResult['issues'] = []
          let totalBlocksTranslated = 0

          // Initialize unselected pages as 'ok'
          for (let p = 1; p <= session.page_count; p++) {
            pageStatuses[p] = 'ok'
            pageBlockCounts[p] = 0
            pageMathCounts[p] = 0
          }
          session.integrity = {
            blocks_translated: 0,
            needs_review: 0,
            preserved_pages: 0,
            page_statuses: { ...pageStatuses },
            page_block_counts: { ...pageBlockCounts },
            page_math_counts: { ...pageMathCounts },
            completed_pages: {},
            issues: [],
          }

          for (let idx = 0; idx < selectedPages.length; idx++) {
            if (session.cancel_requested) {
              const rawBytes = Buffer.from(await outDoc.save())
              session.translated_pdf_bytes = await optimizePdfBuffer(rawBytes)
              session.active_out_doc = undefined
              session.active_out_dirty = false
              session.is_translating = false
              session.progress = {
                ...session.progress,
                status: 'idle',
                message: 'Translation cancelled by user.',
              }
              persistSessionToDisk(session, false)
              return
            }

            const pageNum = selectedPages[idx]
            const pctBefore = Math.max(
              8,
              Math.min(92, Math.round(((idx + 0.25) / totalSelected) * 100))
            )

            session.progress = {
              stage_index: idx === 0 ? 1 : 2,
              stage_name:
                idx === 0 ? 'Detecting tables and formulas' : 'Translating text blocks',
              current_page: idx,
              total_pages: totalSelected,
              overall_pct: pctBefore,
              status: 'processing',
              speed: Number(((idx + 1) / Math.max(0.5, (Date.now() - startTime) / 1000)).toFixed(1)),
              eta_seconds: Math.max(1, Math.ceil((totalSelected - idx) * 1.4)),
              subtitle: `Page ${pageNum} (${idx + 1} of ${totalSelected})`,
              message: `Translating Page ${pageNum} (${sourceLang.toUpperCase()} → ${targetLang.toUpperCase()}) with frozen formula quads...`,
              integrity: session.integrity,
            }

            const pageResult = await translateAndTypesetPage(
              mupdfDoc,
              outDoc,
              fontBundle,
              pageNum - 1,
              effectiveSourceLang,
              targetLang,
              { ...translationOpts, paintOverProse: paintOverPages.has(pageNum - 1) }
            )

            session.page_results[pageNum] = pageResult
            pageStatuses[pageNum] = pageResult.status
            pageBlockCounts[pageNum] = pageResult.blocksTranslated
            pageMathCounts[pageNum] = pageResult.mathBlocksPreserved
            completedPages[pageNum] = true
            totalBlocksTranslated += pageResult.blocksTranslated
            allIssues.push(...pageResult.issues)

            session.active_out_dirty = true
            session.page_png_cache.delete(`translated_${pageNum}_${targetLang}`)

            // Serialize immediately on the first page so the workspace preview updates right away,
            // and defer full font-subsetted optimization until the job completes to avoid 96x font stream duplication
            if (idx === 0) {
              session.translated_pdf_bytes = Buffer.from(await outDoc.save())
              session.active_out_dirty = false
            }

            const liveIntegrity = {
              blocks_translated: totalBlocksTranslated,
              needs_review: allIssues.length,
              preserved_pages: 0,
              page_statuses: { ...pageStatuses },
              page_block_counts: { ...pageBlockCounts },
              page_math_counts: { ...pageMathCounts },
              completed_pages: { ...completedPages },
              issues: [...allIssues],
            }
            session.integrity = liveIntegrity

            const pctAfter = Math.max(
              12,
              Math.min(96, Math.round(((idx + 1) / totalSelected) * 100))
            )
            session.progress = {
              stage_index: 3,
              stage_name: 'Fitting text to layout',
              current_page: idx + 1,
              total_pages: totalSelected,
              overall_pct: pctAfter,
              status: 'processing',
              speed: Number(((idx + 1) / Math.max(0.5, (Date.now() - startTime) / 1000)).toFixed(1)),
              eta_seconds: Math.max(0, Math.ceil((totalSelected - idx - 1) * 1.3)),
              subtitle: `Page ${pageNum} (${idx + 1} of ${totalSelected})`,
              message: `Typeset Page ${pageNum}: ${pageResult.blocksTranslated} prose blocks translated, ${pageResult.mathBlocksPreserved} formula regions preserved.`,
              integrity: liveIntegrity,
            }
          }

          // Finalize PDF: save once, subset embedded TrueType fonts, and deduplicate PDF streams via MuPDF
          const rawFinalBytes = Buffer.from(await outDoc.save())
          session.translated_pdf_bytes = await optimizePdfBuffer(rawFinalBytes)
          session.active_out_doc = undefined
          session.active_out_dirty = false

          const integrityData = {
            blocks_translated: totalBlocksTranslated,
            needs_review: allIssues.length,
            preserved_pages: 0,
            page_statuses: pageStatuses,
            page_block_counts: pageBlockCounts,
            page_math_counts: pageMathCounts,
            completed_pages: completedPages,
            issues: allIssues,
          }

          session.integrity = integrityData
          session.is_translating = false
          session.progress = {
            stage_index: 5,
            stage_name: 'Complete',
            current_page: totalSelected,
            total_pages: totalSelected,
            overall_pct: 100,
            status: 'done',
            speed: Number((totalSelected / Math.max(0.5, (Date.now() - startTime) / 1000)).toFixed(1)),
            eta_seconds: 0,
            message: `Translation complete! ${totalBlocksTranslated} blocks translated across ${totalSelected} page(s).`,
            integrity: integrityData,
          }
          persistSessionToDisk(session, false)
        } catch (err: any) {
          console.error('Translation job error:', err)
          session.is_translating = false
          session.progress = {
            stage_index: 0,
            stage_name: 'Error',
            current_page: 0,
            total_pages: totalSelected,
            overall_pct: 0,
            status: 'error',
            message: `Translation error: ${err?.message || String(err)}`,
          }
        }
      })()
    } catch (err: any) {
      res.status(500).json({ error: `Failed to start translation: ${err?.message || err}` })
    }
  })

  // 4b. Cancel active translation job
  app.post(['/api/cancel', '/cancel'], async (req, res) => {
    const docId = String(req.body?.doc_id || req.query.id || 'sample_academic')
    const session = sessions.get(docId)
    if (session) {
      session.cancel_requested = true
      session.is_translating = false
    }
    res.json({ status: 'cancelled' })
  })

  // 5. Translation progress polling
  app.get(['/api/progress', '/progress'], async (req, res) => {
    const docId = String(req.query.id || 'sample_academic')
    const session = await getOrRecoverSession(docId)
    res.json({
      ...session.progress,
      integrity: session.integrity,
    })
  })

  // 6. Download translated PDF (monolingual or side-by-side bilingual) or Markdown
  app.get(['/api/download', '/download'], async (req, res) => {
    try {
      const docId = String(req.query.id || 'sample_academic')
      const format = String(req.query.format || 'pdf').toLowerCase()
      const mode = String(req.query.mode || 'mono').toLowerCase()
      const session = await getOrRecoverSession(docId)
      const baseStem = session.filename.replace(/\.pdf$/i, '')

      if (format === 'md' || format === 'markdown') {
        const mdLines: string[] = [
          `# ${baseStem} (${session.detected_lang.toUpperCase()} → ${session.target_lang.toUpperCase()})`,
          '',
          `> Generated by LayoutLingua v2.0 — Sub-Line Formula Pinning & Adaptive Vector Typesetting`,
          '',
        ]
        const pages = Object.keys(session.page_results)
          .map(Number)
          .sort((a, b) => a - b)

        if (pages.length === 0) {
          mdLines.push('_No pages have been translated in this session yet._')
        } else {
          for (const p of pages) {
            const pr = session.page_results[p]
            mdLines.push(`## Page ${p}`)
            mdLines.push('')
            for (const blk of pr.blocks) {
              if (blk.preserved) continue
              if (blk.kind === 'heading') {
                mdLines.push(`### ${blk.translatedText}`)
              } else {
                mdLines.push(blk.translatedText)
              }
              mdLines.push('')
            }
          }
        }

        const cleanName = `${baseStem}.${session.target_lang}.md`
        res.setHeader('Content-Type', 'text/markdown; charset=utf-8')
        res.setHeader('Content-Disposition', `attachment; filename="${cleanName}"`)
        res.send(mdLines.join('\n'))
        return
      }

      const scope = String(req.query.scope || 'all').toLowerCase()
      const translatedBytes = session.translated_pdf_bytes || session.source_pdf_bytes
      const selectedSet = new Set(session.selected_pages)

      // If bilingual mode requested, build an interleaved PDF (Source Page followed by Translated Page)
      if (mode === 'bilingual' && session.translated_pdf_bytes) {
        const srcDoc = await PDFDocument.load(session.source_pdf_bytes)
        const trDoc = await PDFDocument.load(session.translated_pdf_bytes)
        const biDoc = await PDFDocument.create()

        for (let i = 0; i < session.page_count; i++) {
          if (scope !== 'translated_only' || selectedSet.size === 0 || selectedSet.has(i + 1)) {
            const [sPage] = await biDoc.copyPages(srcDoc, [i])
            const [tPage] = await biDoc.copyPages(trDoc, [i])
            biDoc.addPage(sPage)
            biDoc.addPage(tPage)
          }
        }
        const biBytes = Buffer.from(await biDoc.save())
        const cleanName = `${baseStem}.${session.target_lang}.bilingual.pdf`
        res.setHeader('Content-Type', 'application/pdf')
        res.setHeader('Content-Disposition', `attachment; filename="${cleanName}"`)
        res.send(biBytes)
        return
      }

      if (
        scope === 'translated_only' &&
        session.translated_pdf_bytes &&
        selectedSet.size > 0 &&
        selectedSet.size < session.page_count
      ) {
        const trDoc = await PDFDocument.load(session.translated_pdf_bytes)
        const subDoc = await PDFDocument.create()
        const indices = session.selected_pages
          .map((p) => p - 1)
          .filter((idx) => idx >= 0 && idx < session.page_count)
        const copied = await subDoc.copyPages(trDoc, indices)
        copied.forEach((p) => subDoc.addPage(p))
        const subBytes = Buffer.from(await subDoc.save())
        const cleanName = `${baseStem}.${session.target_lang || 'vi'}.pdf`
        res.setHeader('Content-Type', 'application/pdf')
        res.setHeader('Content-Disposition', `attachment; filename="${cleanName}"`)
        res.send(subBytes)
        return
      }

      const cleanName = `${baseStem}.${session.target_lang || 'vi'}.pdf`
      res.setHeader('Content-Type', 'application/pdf')
      res.setHeader('Content-Disposition', `attachment; filename="${cleanName}"`)
      res.send(translatedBytes)
    } catch (err: any) {
      res.status(500).json({ error: `Failed to export document: ${err?.message || err}` })
    }
  })

  const resolveUserDirectory = (rawDir: string): string => {
    const home = os.homedir()
    const trimmed = (rawDir || '~/Downloads').trim()
    let expanded = trimmed
    if (trimmed === '~' || trimmed.startsWith('~/') || trimmed.startsWith('~\\')) {
      expanded = path.join(home, trimmed.slice(1))
    }
    // Support Windows OneDrive folder redirection (e.g. ~/Desktop -> ~/OneDrive/Desktop)
    if (!fs.existsSync(expanded)) {
      const baseName = path.basename(expanded)
      const oneDriveCandidate = path.join(home, 'OneDrive', baseName)
      if (fs.existsSync(oneDriveCandidate)) {
        return oneDriveCandidate
      }
    }
    return expanded
  }

  // 7. Save file to disk
  app.post(['/api/save', '/save', '/api/save-file'], async (req, res) => {
    try {
      const body = req.body || {}
      const docId = String(body.doc_id || 'sample_academic')
      const session = await getOrRecoverSession(docId)
      const filename = String(
        body.filename || `${session.filename.replace(/\.pdf$/i, '')}.${session.target_lang}.pdf`
      ).replace(/[\r\n/\\:*?"<>|]/g, '_')
      const rawDir = String(body.directory || '~/Downloads')
      const resolvedDir = resolveUserDirectory(rawDir)
      const content = session.translated_pdf_bytes || session.source_pdf_bytes

      let finalOutPath = ''
      try {
        fs.mkdirSync(resolvedDir, { recursive: true })
        finalOutPath = path.join(resolvedDir, filename)
        fs.writeFileSync(finalOutPath, content)
      } catch {
        const fallbackDir = path.join(os.tmpdir(), 'layoutlingua-exports')
        fs.mkdirSync(fallbackDir, { recursive: true })
        finalOutPath = path.join(fallbackDir, filename)
        fs.writeFileSync(finalOutPath, content)
      }

      res.json({
        status: 'ok',
        saved_path: finalOutPath,
        directory: path.dirname(finalOutPath),
        filename,
        bytes: content.length,
      })
    } catch (err: any) {
      res.status(500).json({ error: `Save failed: ${err?.message || err}` })
    }
  })

  // 8. System folders & folder picker
  app.get(['/api/system-folders', '/system-folders'], (_req, res) => {
    res.json({
      Desktop: resolveUserDirectory('~/Desktop'),
      Downloads: resolveUserDirectory('~/Downloads'),
      Documents: resolveUserDirectory('~/Documents'),
    })
  })

  app.get(['/api/pick-folder', '/pick-folder'], (req, res) => {
    const initial = String(req.query.initial || '~/Downloads')
    res.json({ path: resolveUserDirectory(initial) })
  })

  app.post(['/api/open-folder', '/open-folder'], (_req, res) => {
    res.json({ status: 'ok' })
  })

  // 9. Discover OpenAI-compatible models
  app.get(['/api/models', '/api/fetch-models'], async (req, res) => {
    const baseUrl = String(req.query.base_url || 'https://api.openai.com/v1').replace(/\/$/, '')
    const apiKey = String(req.query.api_key || '').trim()

    try {
      const headers: Record<string, string> = { 'User-Agent': 'LayoutLingua/2.0' }
      if (apiKey) headers['Authorization'] = `Bearer ${apiKey}`
      const resp = await fetch(`${baseUrl}/models`, {
        headers,
        signal: AbortSignal.timeout(3500),
      })
      if (resp.ok) {
        const data: any = await resp.json()
        const models = Array.isArray(data?.data)
          ? data.data.map((m: any) => m?.id).filter(Boolean)
          : []
        if (models.length > 0) {
          res.json({ models, status: 'ok' })
          return
        }
      }
    } catch {}

    res.json({
      models: ['gpt-4o-mini', 'gpt-4o', 'deepseek-chat', 'llama3.2', 'qwen2.5:7b'],
      status: 'ok',
    })
  })

  // Serve frontend via Vite middleware in dev or static dist in production
  const distPath = path.join(__dirname, 'dist')
  if (process.env.NODE_ENV === 'production' && fs.existsSync(distPath)) {
    app.use(express.static(distPath))
    app.get('*all', (_req, res) => {
      res.sendFile(path.join(distPath, 'index.html'))
    })
  } else {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    })
    app.use(vite.middlewares)
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`[LayoutLingua] Real MuPDF Vector Engine listening on http://0.0.0.0:${PORT}`)
  })
}

startServer()
