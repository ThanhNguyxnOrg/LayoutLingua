import { useState } from 'react'
import type { Block, Page } from './data'
import { apiUrl } from '../services/api'

export const PAGE_W = 420
export const PAGE_H = Math.round((PAGE_W * 297) / 210)

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
}

function BlockView({ b, lang, mark }: { b: Block; lang: 'en' | 'vi'; mark?: boolean }) {
  const t = (en: string, vi: string) => (lang === 'en' ? en : vi)
  switch (b.kind) {
    case 'title':
      return (
        <div className="mb-4 text-center">
          <h1 className="font-serif text-[17px] leading-[1.25] font-semibold text-[#111]">{t(b.en, b.vi)}</h1>
          <p className="mt-1.5 font-serif text-[9px] italic text-[#444]">{b.authors}</p>
        </div>
      )
    case 'h':
      return <h2 className="mt-3 mb-1 font-serif text-[11px] font-semibold text-[#111]">{t(b.en, b.vi)}</h2>
    case 'p':
      return <p className="mb-1.5 text-justify font-serif text-[9px] leading-[1.45] text-[#222] hyphens-auto">{t(b.en, b.vi)}</p>
    case 'eq':
      return (
        <div className="my-2 flex items-center font-serif text-[10.5px] text-[#111]">
          <span className="flex-1 text-center italic">{b.tex}</span>
          <span className="text-[9px]">{b.no}</span>
        </div>
      )
    case 'fig':
      return (
        <figure className="my-2">
          <svg viewBox="0 0 300 80" className="w-full border border-[#bbb]" aria-hidden="true">
            {Array.from({ length: 4 }).map((_, k) => (
              <g key={k} transform={`translate(${12 + k * 72} 10)`}>
                <rect width="60" height="60" fill="none" stroke="#999" strokeWidth=".6" />
                {Array.from({ length: 6 }).map((__, r) => (
                  <rect key={r} x={4 + ((r * 7 + k * 3) % 30)} y={4 + r * 9} width={14 + ((r + k) % 3) * 8} height="5" fill="#555" opacity={0.15 + ((r + k) % 4) * 0.18} />
                ))}
              </g>
            ))}
          </svg>
          <figcaption className="mt-1 text-center font-serif text-[8px] text-[#333]">{t(...b.caption)}</figcaption>
        </figure>
      )
    case 'table':
      return (
        <div className={`my-2 ${mark ? 'relative' : ''}`}>
          <p className="mb-1 text-center font-serif text-[8px] text-[#333]">{t(...b.caption)}</p>
          <table className="w-full border-collapse font-serif text-[8.5px] text-[#111]">
            <thead>
              <tr>{b.head.map((h, k) => <th key={k} className="border border-[#555] px-1.5 py-[3px] text-left font-semibold" style={{ width: k === 0 ? '64%' : undefined }}>{t(...h)}</th>)}</tr>
            </thead>
            <tbody>
              {b.rows.map((r, ri) => (
                <tr key={ri}>
                  {r.map((c, ci) => {
                    const overflow = lang === 'vi' && ri === 3 && ci === 0
                    return (
                      <td key={ci} className={`border border-[#555] px-1.5 py-[3px] ${ci === 1 ? 'font-mono text-[8px]' : ''} ${overflow && mark ? 'bg-[#B97827]/15 outline outline-1 outline-[#B97827]' : ''}`}>
                        <span className={overflow ? 'block truncate text-[7px]' : ''}>{t(...c)}</span>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
  }
}

export default function PdfPage({ page, lang = 'en', type, width, highlight, highlightLabel, highlightTone = 'warning', showMarks = true, docId, version }: Props) {
  const [imgFailed, setImgFailed] = useState(false)
  const c = highlightTone === 'info' ? '#3D6A8F' : highlightTone === 'failure' ? '#B64C4C' : '#B97827'
  const scale = width / PAGE_W
  const previewType = type || (lang === 'vi' ? 'translated' : 'source')

  if (docId) {
    return (
      <div style={{ width, height: PAGE_H * scale }} className="relative shrink-0 overflow-hidden bg-white shadow-2xs">
        {imgFailed && previewType === 'translated' ? (
          <div className="size-full flex flex-col items-center justify-center gap-3 bg-canvas/40 border border-dashed border-line text-center p-6">
            <div className="size-6 border-2 border-teal border-t-transparent rounded-full animate-spin" />
            <p className="text-[13px] font-semibold text-ink">Translating page {page.n}...</p>
            <p className="text-[11.5px] text-muted max-w-[220px]">Preserving mathematical equations and layout typography</p>
          </div>
        ) : (
          <img
            key={`${docId}-${page.n}-${previewType}-${version || 0}`}
            src={apiUrl(`/api/page-preview?id=${encodeURIComponent(docId)}&page=${page.n}&type=${previewType}${version ? `&v=${version}` : ''}`)}
            alt={`Page ${page.n} (${lang})`}
            className="size-full object-contain"
            onError={() => setImgFailed(true)}
            onLoad={() => setImgFailed(false)}
          />
        )}
        {highlight && showMarks && highlightLabel && (
          <span className="absolute top-2 left-2 px-1.5 py-0.5 font-sans text-[9px] font-bold text-white rounded-xs" style={{ background: c }}>
            {highlightLabel}
          </span>
        )}
      </div>
    )
  }

  if (!page.blocks || page.blocks.length === 0) {
    return (
      <div style={{ width, height: PAGE_H * scale }} className="relative shrink-0 overflow-hidden bg-white border border-line flex flex-col items-center justify-center p-6 text-center">
        <p className="text-[13px] font-semibold text-ink">Page {page.n}</p>
        <p className="mt-1 text-[11.5px] text-muted">Upload a PDF document to view pages</p>
      </div>
    )
  }

  return (
    <div style={{ width, height: PAGE_H * scale }} className="relative shrink-0 overflow-hidden bg-white">
      <div style={{ width: PAGE_W, height: PAGE_H, transform: `scale(${scale})`, transformOrigin: 'top left' }} className="absolute top-0 left-0 px-[38px] pt-[26px]">
        <div className="mb-4 flex justify-between border-b border-[#ccc] pb-1 font-serif text-[7.5px] text-[#666]">
          <span>{lang === 'en' ? 'Proceedings on Document Computing, Vol. 12' : 'Kỷ yếu Điện toán Tài liệu, Tập 12'}</span>
          <span>{page.n + 140}</span>
        </div>
        {page.blocks.map((b) => (
          <div key={b.id} className="relative" style={highlight === b.id && showMarks ? { outline: `1.5px solid ${c}`, outlineOffset: 3, background: `${c}0D` } : undefined}>
            {highlight === b.id && showMarks && highlightLabel && (
              <span className="absolute -top-[15px] -left-[4px] px-1 font-sans text-[8px] leading-[11px] font-bold text-white" style={{ background: c }}>{highlightLabel}</span>
            )}
            <BlockView b={b} lang={lang} mark={showMarks} />
          </div>
        ))}
        <div className="absolute right-[38px] bottom-[18px] left-[38px] text-center font-serif text-[7.5px] text-[#777]">— {page.n} —</div>
      </div>
    </div>
  )
}
