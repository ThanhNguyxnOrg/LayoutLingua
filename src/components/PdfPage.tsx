import { useState, useEffect } from 'react'
import type { Page } from './data'
import { apiUrl } from '../services/api'

export const PAGE_W = 420
export const PAGE_H = Math.round((PAGE_W * 297) / 210)

interface LayoutBlockMeta {
  id: string
  kind: 'prose' | 'heading' | 'math' | 'toc' | 'table'
  bbox: { x: number; y: number; w: number; h: number }
  pageW: number
  pageH: number
  sourceText: string
  translatedText: string
  fontScale: number
  preserved: boolean
  uri?: string
}

type Props = {
  page: Page
  lang?: 'en' | 'vi'
  type?: 'source' | 'translated'
  width: number
  highlight?: string
  highlightLabel?: string
  highlightTone?: 'warning' | 'info' | 'failure'
  showMarks?: boolean
  docId?: string
  version?: number
  onNavigatePage?: (pageNum: number) => void
}

export default function PdfPage({
  page,
  lang = 'en',
  type,
  width,
  highlight,
  highlightLabel,
  highlightTone = 'warning',
  showMarks = true,
  docId,
  version,
  onNavigatePage,
}: Props) {
  const [imgFailed, setImgFailed] = useState(false)
  const [blocks, setBlocks] = useState<LayoutBlockMeta[]>([])
  const [hoveredBlock, setHoveredBlock] = useState<LayoutBlockMeta | null>(null)

  const c =
    highlightTone === 'info' ? '#3D6A8F' : highlightTone === 'failure' ? '#B64C4C' : '#B97827'
  const scale = width / PAGE_W
  const previewType = type || (lang === 'vi' ? 'translated' : 'source')
  const activeDocId = docId || 'sample_academic'

  useEffect(() => {
    setImgFailed(false)
  }, [page.n, previewType, activeDocId, version])

  useEffect(() => {
    if (imgFailed && previewType === 'translated') {
      const timer = setTimeout(() => {
        setImgFailed(false)
      }, 1800)
      return () => clearTimeout(timer)
    }
  }, [imgFailed, previewType])

  // Fetch block bounding boxes for interactive layout inspection and hyperlinks on full-size pages
  useEffect(() => {
    if (width < 200) {
      setBlocks([])
      return
    }
    let active = true
    fetch(
      apiUrl(
        `/api/page-preview?id=${encodeURIComponent(activeDocId)}&page=${page.n}&format=meta${
          version ? `&v=${version}` : ''
        }`
      )
    )
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (active && data && Array.isArray(data.blocks)) {
          setBlocks(data.blocks)
        }
      })
      .catch(() => {})
    return () => {
      active = false
    }
  }, [activeDocId, page.n, width, version])

  return (
    <div
      style={{ width, height: PAGE_H * scale }}
      className="relative shrink-0 overflow-hidden bg-white shadow-2xs select-none"
    >
      {imgFailed && previewType === 'translated' ? (
        <div className="size-full flex flex-col items-center justify-center gap-1.5 bg-canvas/40 border border-dashed border-line text-center p-1.5">
          <div
            className={`${
              width < 120 ? 'size-3.5' : 'size-6'
            } border-2 border-teal border-t-transparent rounded-full animate-spin`}
          />
          <p
            className={
              width < 120
                ? 'text-[10px] font-medium text-ink'
                : 'text-[13px] font-semibold text-ink'
            }
          >
            {width < 120 ? `P. ${page.n}` : `Translating page ${page.n}...`}
          </p>
          {width >= 120 && (
            <p className="text-[11.5px] text-muted max-w-[220px]">
              Preserving mathematical equations and layout typography
            </p>
          )}
        </div>
      ) : (
        <img
          key={`${activeDocId}-${page.n}-${previewType}-${version || 0}`}
          src={apiUrl(
            `/api/page-preview?id=${encodeURIComponent(activeDocId)}&page=${
              page.n
            }&type=${previewType}${version ? `&v=${version}` : ''}`
          )}
          alt={`Page ${page.n} (${previewType})`}
          className="size-full object-contain"
          onError={() => setImgFailed(true)}
          onLoad={() => setImgFailed(false)}
        />
      )}

      {/* Interactive Bounding-Box Inspector & Hyperlink Overlay */}
      {width >= 200 && blocks.length > 0 && (
        <div className="absolute inset-0 pointer-events-none">
          {blocks.map((blk) => {
            if (!showMarks && !blk.uri) return null
            const leftPct = (blk.bbox.x / (blk.pageW || 595)) * 100
            const topPct = (blk.bbox.y / (blk.pageH || 842)) * 100
            const widthPct = (blk.bbox.w / (blk.pageW || 595)) * 100
            const heightPct = (blk.bbox.h / (blk.pageH || 842)) * 100
            const isHighlighted = showMarks && highlight === blk.id
            const isHovered = showMarks && hoveredBlock?.id === blk.id

            if (blk.uri) {
              const goToMatch = blk.uri.match(/^#page=(\d+)$/i)
              const targetPageNum = goToMatch ? parseInt(goToMatch[1], 10) : null
              return (
                <a
                  key={blk.id}
                  href={blk.uri}
                  target={targetPageNum ? undefined : '_blank'}
                  rel={targetPageNum ? undefined : 'noopener noreferrer'}
                  title={targetPageNum ? `Go to Page ${targetPageNum}` : blk.uri}
                  onClick={(e) => {
                    if (targetPageNum && onNavigatePage) {
                      e.preventDefault()
                      onNavigatePage(targetPageNum)
                    }
                  }}
                  onMouseEnter={() => showMarks && setHoveredBlock(blk)}
                  onMouseLeave={() =>
                    showMarks && setHoveredBlock((prev) => (prev?.id === blk.id ? null : prev))
                  }
                  style={{
                    left: `${leftPct}%`,
                    top: `${topPct}%`,
                    width: `${widthPct}%`,
                    height: `${heightPct}%`,
                  }}
                  className={`absolute pointer-events-auto transition-all cursor-pointer rounded-[2px] z-25 ${
                    isHovered
                      ? 'ring-1.5 ring-blue-600 bg-blue-500/15'
                      : 'hover:ring-1 hover:ring-blue-500/60 hover:bg-blue-500/10'
                  }`}
                />
              )
            }

            return (
              <div
                key={blk.id}
                onMouseEnter={() => setHoveredBlock(blk)}
                onMouseLeave={() => setHoveredBlock((prev) => (prev?.id === blk.id ? null : prev))}
                style={{
                  left: `${leftPct}%`,
                  top: `${topPct}%`,
                  width: `${widthPct}%`,
                  height: `${heightPct}%`,
                }}
                className={`absolute pointer-events-auto transition-all cursor-pointer rounded-[2px] ${
                  isHighlighted
                    ? 'ring-2 ring-amber bg-amber/15 z-20'
                    : isHovered
                    ? blk.preserved
                      ? 'ring-1.5 ring-indigo-500 bg-indigo-500/10 z-20'
                      : 'ring-1.5 ring-teal bg-teal/10 z-20'
                    : 'hover:ring-1 hover:ring-teal/50'
                }`}
              />
            )
          })}
        </div>
      )}

      {showMarks && hoveredBlock && width >= 240 && (
        <div className="absolute bottom-2 left-2 right-2 z-30 rounded-md bg-ink/95 text-white px-3 py-2 text-[11px] shadow-lg pointer-events-none">
          <div className="flex items-center justify-between gap-2 font-mono text-[10px] text-teal-soft">
            <span>
              {hoveredBlock.uri
                ? hoveredBlock.uri.startsWith('#page=')
                  ? `🔗 NAVIGATION LINK PRESERVED · Jump to Page ${hoveredBlock.uri.slice(6)} (${Math.round(
                      hoveredBlock.fontScale * 100
                    )}%)`
                  : `🔗 HYPERLINK PRESERVED · ${hoveredBlock.uri}`
                : hoveredBlock.preserved
                ? '🔒 FROZEN MATH IR (100% VECTOR PRESERVED)'
                : `✓ TRANSLATED ${hoveredBlock.kind.toUpperCase()} · SCALE ${Math.round(
                    hoveredBlock.fontScale * 100
                  )}%`}
            </span>
          </div>
          {!hoveredBlock.preserved && (
            <p className="mt-0.5 truncate text-white/90">
              {previewType === 'source' ? hoveredBlock.sourceText : hoveredBlock.translatedText}
            </p>
          )}
        </div>
      )}

      {highlight && showMarks && highlightLabel && (
        <span
          className="absolute top-2 left-2 px-1.5 py-0.5 font-sans text-[9px] font-bold text-white rounded-xs z-30"
          style={{ background: c }}
        >
          {highlightLabel}
        </span>
      )}
    </div>
  )
}
