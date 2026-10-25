import type { SVGProps } from 'react'

type P = SVGProps<SVGSVGElement>

const base = (p: P) => ({
  viewBox: '0 0 16 16',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.5,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  className: 'size-4',
  ...p,
})

export const IconUpload = (p: P) => (
  <svg {...base(p)}>
    <path d="M8 10.5V2.5M8 2.5L5 5.5M8 2.5L11 5.5M2.5 11.5v1a1 1 0 001 1h9a1 1 0 001-1v-1" />
  </svg>
)

export const IconFile = (p: P) => (
  <svg {...base(p)}>
    <path d="M9.5 2H4.5a1 1 0 00-1 1v10a1 1 0 001 1h7a1 1 0 001-1V5.5L9.5 2z" />
    <path d="M9.5 2v3.5H13" />
  </svg>
)

export const IconLock = (p: P) => (
  <svg {...base(p)}>
    <rect x="3.5" y="7.5" width="9" height="6" rx="1" />
    <path d="M5.5 7.5V5a2.5 2.5 0 015 0v2.5" />
  </svg>
)

export const IconCheck = (p: P) => (
  <svg {...base(p)}>
    <path d="M3.5 8.5l3 3 6-6.5" />
  </svg>
)

export const IconAlert = (p: P) => (
  <svg {...base(p)}>
    <path d="M8 2.5L1.8 13h12.4L8 2.5z" />
    <path d="M8 6.5v3M8 11.5h.01" />
  </svg>
)

export const IconError = (p: P) => (
  <svg {...base(p)}>
    <circle cx="8" cy="8" r="6" />
    <path d="M5.8 5.8l4.4 4.4M10.2 5.8l-4.4 4.4" />
  </svg>
)

export const IconInfo = (p: P) => (
  <svg {...base(p)}>
    <circle cx="8" cy="8" r="6" />
    <path d="M8 7.5v3.5M8 5h.01" />
  </svg>
)

export const IconChevL = (p: P) => (
  <svg {...base(p)}>
    <path d="M9.5 4L5.5 8l4 4" />
  </svg>
)

export const IconChevR = (p: P) => (
  <svg {...base(p)}>
    <path d="M6.5 4l4 4-4 4" />
  </svg>
)

export const IconPlus = (p: P) => (
  <svg {...base(p)}>
    <path d="M8 3.5v9M3.5 8h9" />
  </svg>
)

export const IconMinus = (p: P) => (
  <svg {...base(p)}>
    <path d="M3.5 8h9" />
  </svg>
)

export const IconFit = (p: P) => (
  <svg {...base(p)}>
    <path d="M2.5 6V3.5H5M11 3.5h2.5V6M13.5 10v2.5H11M5 12.5H2.5V10" />
  </svg>
)

export const IconColumns = (p: P) => (
  <svg {...base(p)}>
    <rect x="2" y="3" width="12" height="10" rx="1" />
    <path d="M8 3v10" />
  </svg>
)

export const IconLayers = (p: P) => (
  <svg {...base(p)}>
    <path d="M8 2.5L2 6l6 3.5L14 6 8 2.5zM2 10l6 3.5L14 10" />
  </svg>
)

export const IconPanelR = (p: P) => (
  <svg {...base(p)}>
    <rect x="2" y="3" width="12" height="10" rx="1" />
    <path d="M10.5 3v10" />
  </svg>
)

export const IconSwap = (p: P) => (
  <svg {...base(p)}>
    <path d="M3 6h10l-2.5-2.5M13 10H3l2.5 2.5" />
  </svg>
)

export const IconX = (p: P) => (
  <svg {...base(p)}>
    <path d="M4 4l8 8M12 4l-8 8" />
  </svg>
)

export const IconDownload = (p: P) => (
  <svg {...base(p)}>
    <path d="M8 2.5v8M8 10.5l-3-3M8 10.5l3-3M2.5 12.5h11" />
  </svg>
)

export const IconFolder = (p: P) => (
  <svg {...base(p)}>
    <path d="M2 4.5a1 1 0 011-1h3.2l1.5 1.8H13a1 1 0 011 1v6.2a1 1 0 01-1 1H3a1 1 0 01-1-1V4.5z" />
  </svg>
)

export const IconArrowR = (p: P) => (
  <svg {...base(p)}>
    <path d="M3 8h10M9.5 4.5L13 8l-3.5 3.5" />
  </svg>
)

export const IconHistory = (p: P) => (
  <svg {...base(p)}>
    <circle cx="8" cy="8" r="5.5" />
    <path d="M8 5v3.2l2.2 1.3" />
  </svg>
)

export const IconSettings = (p: P) => (
  <svg {...base(p)}>
    <circle cx="8" cy="8" r="2.2" />
    <path d="M8 2v1.5M8 12.5V14M2 8h1.5M12.5 8H14M3.8 3.8l1.1 1.1M11.1 11.1l1.1 1.1M12.2 3.8l-1.1 1.1M4.9 11.1l-1.1 1.1" />
  </svg>
)

export const IconHelp = (p: P) => (
  <svg {...base(p)}>
    <circle cx="8" cy="8" r="6" />
    <path d="M6.3 6.2a1.8 1.8 0 013.4.6c0 1.2-1.7 1.5-1.7 2.5M8 11.5h.01" />
  </svg>
)

export const IconCopy = (p: P) => (
  <svg {...base(p)}>
    <rect x="5.5" y="5.5" width="8" height="8" rx="1" />
    <path d="M3.5 10.5h-1a1 1 0 01-1-1v-7a1 1 0 011-1h7a1 1 0 011 1v1" />
  </svg>
)

export const IconHeart = (p: P) => (
  <svg {...base(p)}>
    <path d="M8 13.2S2.5 10 2.5 6.2C2.5 4.4 3.9 3 5.6 3c1 0 1.9.5 2.4 1.2C8.5 3.5 9.4 3 10.4 3c1.7 0 3.1 1.4 3.1 3.2 0 3.8-5.5 7-5.5 7z" />
  </svg>
)

export const IconGitHub = (p: P) => (
  <svg viewBox="0 0 16 16" fill="currentColor" className="size-4" {...p}>
    <path
      fillRule="evenodd"
      clipRule="evenodd"
      d="M8 .8a7.2 7.2 0 00-2.28 14.03c.36.07.5-.16.5-.35v-1.22c-2 .43-2.43-.97-2.43-.97-.32-.83-.8-1.05-.8-1.05-.66-.45.05-.44.05-.44.73.05 1.11.75 1.11.75.65 1.11 1.7.79 2.12.6.06-.47.25-.79.46-.97-1.6-.18-3.28-.8-3.28-3.56 0-.79.28-1.43.74-1.94-.07-.18-.32-.91.07-1.9 0 0 .6-.2 1.98.74a6.9 6.9 0 013.6 0c1.37-.93 1.98-.74 1.98-.74.39.99.14 1.72.07 1.9.46.5.74 1.15.74 1.94 0 2.77-1.69 3.38-3.3 3.56.26.22.49.66.49 1.33v1.97c0 .19.13.42.5.35A7.2 7.2 0 008 .8z"
    />
  </svg>
)

export const IconBug = (p: P) => (
  <svg {...base(p)}>
    <path d="M8 5.5a2.5 2.5 0 012.5 2.5v1a2.5 2.5 0 01-5 0V8A2.5 2.5 0 018 5.5z" />
    <path d="M5.5 8.5H2.5M13.5 8.5h-3M5.5 11c-1.2.4-2 1-2.5 2M10.5 11c1.2.4 2 1 2.5 2M5.5 6.2C4.6 5.5 4.2 4.8 4.2 3.8M10.5 6.2c.9-.7 1.3-1.4 1.3-2.4M6.5 5.3V4a1.5 1.5 0 013 0v1.3" />
  </svg>
)
