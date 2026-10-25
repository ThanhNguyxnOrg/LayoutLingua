import fs from 'node:fs'
import path from 'node:path'
import {
  PDFDict,
  PDFDocument,
  PDFHexString,
  PDFName,
  PDFNumber,
  PDFOperator,
  PDFOperatorNames,
  PDFString,
  rgb,
  type PDFFont,
  type PDFPage,
} from 'pdf-lib'
import fontkit from '@pdf-lib/fontkit'
import { franc } from 'franc-min'

let mupdfCache: any = null
export async function getMupdf(): Promise<any> {
  if (!mupdfCache) {
    const dynamicImport = new Function('specifier', 'return import(specifier)')
    mupdfCache = await dynamicImport('mupdf')
  }
  return mupdfCache
}

export interface BBox {
  x: number
  y: number
  w: number
  h: number
}

export interface LayoutBlockMeta {
  id: string
  kind: 'prose' | 'heading' | 'math' | 'toc' | 'table'
  bbox: BBox // Normalized to 0..1000 or PDF points; we store PDF points + pageW/pageH
  pageW: number
  pageH: number
  sourceText: string
  translatedText: string
  fontScale: number
  preserved: boolean
  uri?: string
}

export interface PageTranslationResult {
  pageNumber: number
  pageW: number
  pageH: number
  blocksTranslated: number
  mathBlocksPreserved: number
  scaledBlocksCount: number
  status: 'ok' | 'warn' | 'fallback'
  blocks: LayoutBlockMeta[]
  issues: Array<{
    id: string
    severity: 'warning' | 'error'
    page: number
    code: string
    title: string
    detail: string
    region: string
    next?: string
    action?: string
  }>
}

interface RawChar {
  c: string
  ox: number
  oy: number
  x0: number
  y0: number
  x1: number
  y1: number
  font: string
  bold: boolean
  italic: boolean
  serif: boolean
  mono: boolean
  size: number
  color: [number, number, number]
}

interface WordToken {
  text: string
  x0: number
  y0: number
  x1: number
  y1: number
  ox: number
  oy: number
  size: number
  font: string
  bold: boolean
  italic: boolean
  serif: boolean
  mono: boolean
  color: [number, number, number]
  isMath: boolean
  hasSymbolFont: boolean
  hasVniFont: boolean
  hasAdjSubSup: boolean
  isHyperlink?: boolean
}

interface ProseSpan {
  text: string
  x0: number
  y0: number
  x1: number
  y1: number
  oy: number
  size: number
  bold: boolean
  italic: boolean
  serif: boolean
  mono: boolean
  color: [number, number, number]
  bgColor: [number, number, number]
  leftClearanceX: number
  rightClearanceX: number
  isToc: boolean
  tocTitle?: string
  tocPageNum?: string
}

export interface ProseGroup {
  id: string
  kind: 'prose' | 'heading' | 'toc'
  spans: ProseSpan[]
  x0: number
  y0: number
  x1: number
  y1: number
  leftClearanceX: number
  rightClearanceX: number
  sourceText: string
  translatedText?: string
  size: number
  bold: boolean
  italic: boolean
  serif: boolean
  mono: boolean
  color: [number, number, number]
  bgColor: [number, number, number]
  uri?: string
}

// Symbol Private Use Area (PUA \uF020..\uF0FF) to Unicode mapping
const SYMBOL_PUA_MAP: Record<number, string> = {
  0xf020: ' ',
  0xf022: '∀',
  0xf024: '∃',
  0xf027: '∋',
  0xf028: '(',
  0xf029: ')',
  0xf02a: '*',
  0xf02b: '+',
  0xf02c: ',',
  0xf02d: '−',
  0xf02e: '.',
  0xf02f: '/',
  0xf030: '0',
  0xf031: '1',
  0xf032: '2',
  0xf033: '3',
  0xf034: '4',
  0xf035: '5',
  0xf036: '6',
  0xf037: '7',
  0xf038: '8',
  0xf039: '9',
  0xf03a: ':',
  0xf03b: ';',
  0xf03c: '<',
  0xf03d: '=',
  0xf03e: '>',
  0xf044: 'Δ',
  0xf046: 'Φ',
  0xf047: 'Γ',
  0xf04c: 'Λ',
  0xf050: 'Π',
  0xf051: 'Θ',
  0xf053: 'Σ',
  0xf057: 'Ω',
  0xf058: 'Ξ',
  0xf059: 'Ψ',
  0xf05b: '[',
  0xf05d: ']',
  0xf05e: '⊥',
  0xf061: 'α',
  0xf062: 'β',
  0xf063: 'χ',
  0xf064: 'δ',
  0xf065: 'ε',
  0xf066: 'φ',
  0xf067: 'γ',
  0xf068: 'η',
  0xf069: 'ι',
  0xf06a: 'φ',
  0xf06b: 'κ',
  0xf06c: 'λ',
  0xf06d: 'μ',
  0xf06e: 'ν',
  0xf06f: '°',
  0xf070: 'π',
  0xf071: 'θ',
  0xf072: 'ρ',
  0xf073: 'σ',
  0xf074: 'τ',
  0xf075: 'υ',
  0xf077: 'ω',
  0xf078: 'ξ',
  0xf079: 'ψ',
  0xf07a: 'ζ',
  0xf07b: '{',
  0xf07c: '|',
  0xf07d: '}',
  0xf07e: '~',
  0xf0a3: '≤',
  0xf0a5: '∞',
  0xf0ab: '↔',
  0xf0ac: '←',
  0xf0ad: '↑',
  0xf0ae: '→',
  0xf0af: '↓',
  0xf0b0: '°',
  0xf0b1: '±',
  0xf0b2: '″',
  0xf0b3: '≥',
  0xf0b4: '×',
  0xf0b5: '∝',
  0xf0b6: '∂',
  0xf0b7: '•',
  0xf0b8: '÷',
  0xf0b9: '≠',
  0xf0ba: '≡',
  0xf0bb: '≈',
  0xf0bc: '…',
  0xf0c4: '⊗',
  0xf0c5: '⊕',
  0xf0c6: '∅',
  0xf0c7: '∩',
  0xf0c8: '∪',
  0xf0c9: '⊃',
  0xf0ca: '⊇',
  0xf0cb: '⊄',
  0xf0cc: '⊂',
  0xf0cd: '⊆',
  0xf0ce: '∈',
  0xf0cf: '∉',
  0xf0d0: '∠',
  0xf0d1: '∇',
  0xf0d5: '∏',
  0xf0d6: '√',
  0xf0d7: '⋅',
  0xf0db: '⇔',
  0xf0dc: '⇐',
  0xf0de: '⇒',
  0xf0e5: '∑',
  0xf0e6: '⎛',
  0xf0e7: '⎜',
  0xf0e8: '⎝',
  0xf0e9: '⎡',
  0xf0ea: '⎢',
  0xf0eb: '⎣',
  0xf0ec: '⎧',
  0xf0ed: '⎨',
  0xf0ee: '⎩',
  0xf0ef: '⎪',
  0xf0f2: '∫',
  0xf0f6: '⎞',
  0xf0f7: '⎟',
  0xf0f8: '⎠',
  0xf0f9: '⎤',
  0xf0fa: '⎥',
  0xf0fb: '⎦',
  0xf0fc: '⎫',
  0xf0fd: '⎬',
  0xf0fe: '⎭',
}

export function decodeSymbolPua(str: string): string {
  let out = ''
  for (let i = 0; i < str.length; i++) {
    const code = str.charCodeAt(i)
    if (code >= 0xf000 && code <= 0xf0ff) {
      out += SYMBOL_PUA_MAP[code] ?? ''
    } else {
      out += str[i]
    }
  }
  return out
}

/**
 * Decodes legacy VNI-Times / VNI-Win encoded Vietnamese strings into Unicode NFC.
 */
export function decodeVniToUnicode(str: string): string {
  // Fix split accent spaces produced by PDF kerning in VNI-Times (e.g. "vo ânghieäm" -> "voâ nghieäm", "ño ù" -> "ñoù")
  let s = str
    .replace(/([oO]) ([âÂ])([a-zA-Z])/g, '$1$2 $3')
    .replace(/([a-zA-ZôöÔÖ]) ([ùúûõïäëâêÙÚÛÕÏÄËÂÊ])/g, '$1$2')

  // Important: Replace single-byte VNI horn vowels (\u00F4 = ơ, \u00F6 = ư) BEFORE converting "oâ" -> "ô"
  const vniMap: Array<[string, string]> = [
    ['ôù', 'ớ'],
    ['ÔÙ', 'Ớ'],
    ['ôø', 'ờ'],
    ['ÔØ', 'Ờ'],
    ['ôû', 'ở'],
    ['ÔÛ', 'Ở'],
    ['ôõ', 'ỡ'],
    ['ÔÕ', 'Ỡ'],
    ['ôï', 'ợ'],
    ['ÔÏ', 'Ợ'],
    ['ô', 'ơ'],
    ['Ô', 'Ơ'],
    ['öù', 'ứ'],
    ['ÖÙ', 'Ứ'],
    ['öø', 'ừ'],
    ['ÖØ', 'Ừ'],
    ['öû', 'ử'],
    ['ÖÛ', 'Ử'],
    ['öõ', 'ữ'],
    ['ÖÕ', 'Ữ'],
    ['öï', 'ự'],
    ['ÖÏ', 'Ự'],
    ['ö', 'ư'],
    ['Ö', 'Ư'],
    ['oá', 'ố'],
    ['OÁ', 'Ố'],
    ['oà', 'ồ'],
    ['OÀ', 'Ồ'],
    ['oå', 'ổ'],
    ['OÅ', 'Ổ'],
    ['oã', 'ỗ'],
    ['OÃ', 'Ỗ'],
    ['oä', 'ộ'],
    ['OÄ', 'Ộ'],
    ['oâ', 'ô'],
    ['OÂ', 'Ô'],
    ['aá', 'ấ'],
    ['AÁ', 'Ấ'],
    ['aà', 'ầ'],
    ['AÀ', 'Ầ'],
    ['aå', 'ẩ'],
    ['AÅ', 'Ẩ'],
    ['aã', 'ẫ'],
    ['AÃ', 'Ẫ'],
    ['aä', 'ậ'],
    ['AÄ', 'Ậ'],
    ['aâ', 'â'],
    ['AÂ', 'Â'],
    ['aé', 'ắ'],
    ['AÉ', 'Ắ'],
    ['aè', 'ằ'],
    ['AÈ', 'Ằ'],
    ['aú', 'ẳ'],
    ['AÚ', 'Ẳ'],
    ['aõ', 'ẵ'],
    ['AÕ', 'Ẵ'],
    ['aë', 'ặ'],
    ['AË', 'Ặ'],
    ['aê', 'ă'],
    ['AÊ', 'Ă'],
    ['aù', 'á'],
    ['AÙ', 'Á'],
    ['aø', 'à'],
    ['AØ', 'À'],
    ['aû', 'ả'],
    ['AÛ', 'Ả'],
    ['aï', 'ạ'],
    ['AÏ', 'Ạ'],
    ['eá', 'ế'],
    ['EÁ', 'Ế'],
    ['eà', 'ề'],
    ['EÀ', 'Ề'],
    ['eå', 'ể'],
    ['EÅ', 'Ể'],
    ['eã', 'ễ'],
    ['EÃ', 'Ễ'],
    ['eä', 'ệ'],
    ['EÄ', 'Ệ'],
    ['eâ', 'ê'],
    ['EÂ', 'Ê'],
    ['eù', 'é'],
    ['EÙ', 'É'],
    ['eø', 'è'],
    ['EØ', 'È'],
    ['eû', 'ẻ'],
    ['EÛ', 'Ẻ'],
    ['eõ', 'ẽ'],
    ['EÕ', 'Ẽ'],
    ['eï', 'ẹ'],
    ['EÏ', 'Ẹ'],
    ['où', 'ó'],
    ['OÙ', 'Ó'],
    ['oø', 'ò'],
    ['OØ', 'Ò'],
    ['oû', 'ỏ'],
    ['OÛ', 'Ỏ'],
    ['oõ', 'õ'],
    ['OÕ', 'Õ'],
    ['oï', 'ọ'],
    ['OÏ', 'Ọ'],
    ['uù', 'ú'],
    ['UÙ', 'Ú'],
    ['uø', 'ù'],
    ['UØ', 'Ù'],
    ['uû', 'ủ'],
    ['UÛ', 'Ủ'],
    ['uõ', 'ũ'],
    ['UÕ', 'Ũ'],
    ['uï', 'ụ'],
    ['UÏ', 'Ụ'],
    ['yù', 'ý'],
    ['YÙ', 'Ý'],
    ['yø', 'ỳ'],
    ['YØ', 'Ỳ'],
    ['yû', 'ỷ'],
    ['YÛ', 'Ỷ'],
    ['yõ', 'ỹ'],
    ['YÕ', 'Ỹ'],
    ['yï', 'ỵ'],
    ['YÏ', 'Ỵ'],
    ['iù', 'í'],
    ['IÙ', 'Í'],
    ['iø', 'ì'],
    ['IØ', 'Ì'],
    ['iû', 'ỉ'],
    ['IÛ', 'Ỉ'],
    ['iõ', 'ĩ'],
    ['IÕ', 'Ĩ'],
    ['iï', 'ị'],
    ['IÏ', 'Ị'],
    ['ñ', 'đ'],
    ['Ñ', 'Đ'],
  ]
  for (const [k, v] of vniMap) {
    s = s.split(k).join(v)
  }
  return s.normalize('NFC')
}

const MATH_FUNCTION_NAMES = new Set([
  'sin',
  'cos',
  'tan',
  'cot',
  'cotan',
  'cottan',
  'sec',
  'csc',
  'cosec',
  'cossec',
  'arcsin',
  'arccos',
  'arctan',
  'arccot',
  'arccottan',
  'sinh',
  'cosh',
  'tanh',
  'coth',
  'lg',
  'ln',
  'log',
  'lim',
  'max',
  'min',
  'sup',
  'inf',
  'det',
  'dim',
  'ker',
  'deg',
  'gcd',
  'lcm',
  'mod',
  'exp',
  'arg',
  'softmax',
  'const',
  'dx',
  'dy',
  'dz',
  'dt',
  'du',
  'dv',
  'dw',
])

const EXPLICIT_MATH_SYMBOL_RE = /[=<>≠≤≥±∓×÷∑∏∫√∞∂∇∈∉⊂⊃⊆⊇∪∩∀∃⇒⇔→←↔≡≈∝]/

const VOWEL_PATTERN =
  /[aeiouyàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹäöüßéèêëàâùûîïôœçáéíóúñãõåæøąęóıİіїєґаеёиоуыэюяαεηιουω\p{Lo}]/iu

// Dynamically compiled pattern for fused ISO math operators + arguments/differentials (e.g. sinx, cosxdx, aln, ABcos)
const MATH_FUNC_FUSED_RE = new RegExp(
  `^(?:[0-9]*[a-zA-Z]{0,2}(?:${Array.from(MATH_FUNCTION_NAMES).join('|')})(?:[0-9]+|[a-zA-Z]{1,2}|d[a-zA-Z])*)+$`,
  'i'
)

// Multi-script natural language regex (CJK, Cyrillic, Latin Extended diacritics, Arabic, Hebrew)
const MULTILINGUAL_SCRIPT_RE =
  /[\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u024F\u1E00-\u1EFF\u0400-\u04FF\u2E80-\u9FFF\uF900-\uFAFF\u3040-\u30FF\uAC00-\uD7AF\u0590-\u06FF]/u

/**
 * Determines whether a single word token is a mathematical expression/symbol rather than prose.
 * Language-agnostic implementation aligned with ThanhNguyxnOrg/LayoutLingua (parser.py & isolator.py).
 */
function isMathWordToken(
  rawText: string,
  hasSymbolFont: boolean,
  hasVniFont: boolean,
  hasAdjacentSubSup: boolean,
  isItalic = false,
  isMono = false
): boolean {
  const trimmed = rawText.trim()
  if (!trimmed) return true

  // Single-character monospaced glyph (e.g. Courier New bullet/symbol glyph) is a non-prose symbol
  if (isMono && trimmed.length === 1) {
    return true
  }

  // If it has VNI font and decodes to diacritics without explicit math operators, it is prose
  if (hasVniFont && MULTILINGUAL_SCRIPT_RE.test(trimmed) && !EXPLICIT_MATH_SYMBOL_RE.test(trimmed)) {
    return false
  }

  // Any word containing non-ASCII natural language script characters (CJK, Cyrillic, Latin diacritics) without explicit math operators is natural prose
  // (Must be checked before hasAdjacentSubSup so natural words like "nếu" standing next to lim_{x->a} are never misclassified as subscripted math variables)
  if (MULTILINGUAL_SCRIPT_RE.test(trimmed) && !EXPLICIT_MATH_SYMBOL_RE.test(trimmed)) {
    return false
  }

  // If an ASCII/Symbol token has an adjacent subscript/superscript or vector arrow (like a^x, log_a, P_n., M_0, x_1, \vec{A}), it is 100% math!
  if (hasAdjacentSubSup) {
    return true
  }

  // Allow numbered list prefixes ("1.", "2.", "I.", "a)"), bracketed citations ("[1]", "[2]"), and author initials ("I.", "L.") to stay with prose
  if (/^(?:\d{1,2}\.|[IVX]{1,4}\.|[a-d]\)|\[\d+\]|\p{Lu}\.)$/iu.test(trimmed)) {
    return false
  }

  // Capitalized proper nouns / natural words >= 4 chars in any cased Unicode script (e.g. "Newton", "Théorème", "Lösung", "Теорема") are prose, not math variables
  const cleanWord = trimmed.replace(/^[,.;:()[\]{}"'’«»—–-]+|[,.;:()[\]{}"'’«»—–-]+$/g, '')
  if (/^\p{Lu}\p{Ll}{3,}$/u.test(cleanWord) && !MATH_FUNCTION_NAMES.has(cleanWord.toLowerCase())) {
    return false
  }

  // If it contains explicit math operators (=, <, >, ≠, ≤, ≥, ±, ∑, ∫, etc.)
  if (EXPLICIT_MATH_SYMBOL_RE.test(trimmed)) {
    return true
  }

  // Inline plus/minus expressions like "a+b", "a-b", "x-x0", "2k+1" (excluding natural hyphenated words in any language like "demi-cercle", "по-другому", "non-linear")
  if (
    /[+-]/.test(trimmed) &&
    !/^\p{L}{2,}(?:-\p{L}{2,})+$/u.test(trimmed) &&
    !/^A-Z$/i.test(trimmed) &&
    !/^\d{4}-\d{4}$/.test(trimmed)
  ) {
    return true
  }

  // Prime derivatives like f', y', y'', Cu', aa', bb', ab', ba', dd', f''(x) or function notation f(x), g(x), P(x)
  if (
    (/^[A-Za-z0-9()]+['’′″]+[A-Za-z0-9(),;.]*$/.test(trimmed) && !/^\p{Lu}\p{Ll}{2,}['’]s$/iu.test(trimmed)) ||
    /^[A-Za-z]{1,3}\([A-Za-z0-9,.;:\s+'’′+-]*\)[,.;:]?$/.test(trimmed)
  ) {
    return true
  }

  // Dot-product or geometric point notation like A.C, B.C, IA.IB, O.O'
  if (/^[A-Z]{1,2}\.[A-Z]{1,2}[,;.]?$/.test(trimmed)) {
    return true
  }

  // Every glyph in Symbol / MT Extra / TeX Math font is mathematical/symbol (matching PDFMathTranslate vflag)
  if (hasSymbolFont) {
    return true
  }

  const core = cleanWord
  if (!core) return true

  // Standalone single ASCII letter (a, b, c, x, y, z, f, A, B, C, X, Y, Z, etc.)
  // Marked as candidate; contextual pass keeps 1D single letters in prose when adjacent to prose words
  if (/^[a-zA-Z]$/.test(core)) {
    return true
  }

  // Known ISO math function names, algebraic differential forms (<vars>d<var>), or fused operator expressions
  const coreNoCommaDigits = core.replace(/[,0-9']/g, '')
  const coreLower = core.toLowerCase()
  const coreNoDigitsLower = coreNoCommaDigits.toLowerCase()
  if (
    MATH_FUNCTION_NAMES.has(coreLower) ||
    MATH_FUNCTION_NAMES.has(coreNoDigitsLower) ||
    MATH_FUNC_FUSED_RE.test(coreNoCommaDigits) ||
    /^(?:[0-9]*[a-zA-Z]{1,3})(?:d[a-zA-Z])+$/i.test(coreNoCommaDigits)
  ) {
    return true
  }

  // Factorial, indexed variables, or numeric coefficients like n!, x_1, n1, n2, a1, x0, 0,01795rn
  if (/^(?:[A-Za-z]\d+|[A-Za-z]_[A-Za-z0-9]+|[A-Za-z]!|\d+[0-9.,]*[A-Za-z]+|[0-9.,/+-]+|\.{2,}|…+)$/.test(core)) {
    return true
  }

  // 2-to-4 letter uppercase geometric/vector vertex clusters (AB, BA, AC, BC, OM, ABC, XYZ)
  // Recovered in ALL-CAPS headings by the contextual pass
  if (/^[A-Z]{2,4}$/.test(core)) {
    return true
  }

  // Mixed-case math identifiers like mA, nB, xOM, Xi, Yj, Zk, Cu, Cr, Sh, Rh, Rr
  if (/^(?:[a-z][A-Z]{1,3}|[A-Z][a-z])$/.test(core)) {
    return true
  }

  // Consonant-only lowercase algebraic tokens without vowels (e.g. kl, mn, pq, bc, bd, cd, pr, rl, ph, hr, xy)
  if (/^[a-z]{2,4}$/.test(core) && !VOWEL_PATTERN.test(core)) {
    return true
  }

  // Typographic math rule (matching PDFMathTranslate vflag & LayoutLingua FormulaIsolator):
  // In ISO 80000-2 / TeX / MathType, 2-to-3 letter ASCII variable products (ab, ax, bx, bi, pa, py, uv, uvw)
  // are typeset in Italic font, whereas upright 2-to-3 letter words with vowels in any language are natural prose.
  if (isItalic && /^[a-z]{2,3}$/.test(core)) {
    return true
  }

  return false
}

/**
 * Checks whether a sequence of prose words actually contains translatable natural language text
 * across any Unicode script (language-agnostic, matching _extract_prose_tokens in parser.py).
 */
function isTranslatableProseText(text: string): boolean {
  const t = text.trim()
  if (!t || t.length <= 1) return false

  // Remove section prefixes like "1.", "a)", "I.", "(α)", "· 78"
  const stripped = t
    .replace(/^(?:[IVXLC]+\.|\d+\.|[a-zA-Z]\)|\([αβγδε1-9a-z]\))\s*/i, '')
    .replace(/[·•.]+\s*\d+\s*$/g, '')
    .trim()
  if (!stripped) return false

  if (MULTILINGUAL_SCRIPT_RE.test(stripped)) return true

  const words = stripped
    .split(/\s+/)
    .map((w) => w.replace(/^[^\p{L}]+|[^\p{L}]+$/gu, ''))
    .filter(
      (w) =>
        w.length >= 2 &&
        VOWEL_PATTERN.test(w) &&
        !MATH_FUNCTION_NAMES.has(w.toLowerCase()) &&
        !isMathWordToken(w, false, false, false, false, false)
    )

  return words.length >= 1
}

/**
 * Samples the local background RGB color (0..1) around a bounding box from a MuPDF 1x RGB Pixmap.
 */
function sampleBackgroundRGB(
  samples: Uint8Array | Buffer,
  pixW: number,
  pixH: number,
  nComp: number,
  x0: number,
  y0: number,
  x1: number,
  y1: number
): [number, number, number] {
  const pts: Array<[number, number]> = [
    [x0 - 3, (y0 + y1) / 2],
    [x1 + 3, (y0 + y1) / 2],
    [(x0 + x1) / 2, y0 - 3],
    [(x0 + x1) / 2, y1 + 3],
    [x0 + 2, y0 - 3],
    [x1 - 2, y0 - 3],
    [x0 + 2, y1 + 3],
    [x1 - 2, y1 + 3],
    [x0 - 4, y0 - 2],
    [x1 + 4, y0 - 2],
    [x0 - 4, y1 + 2],
    [x1 + 4, y1 + 2],
  ]

  const colors: Array<[number, number, number]> = []
  let nearWhiteCount = 0
  for (const [px, py] of pts) {
    const ix = Math.max(0, Math.min(pixW - 1, Math.round(px)))
    const iy = Math.max(0, Math.min(pixH - 1, Math.round(py)))
    const idx = (iy * pixW + ix) * nComp
    const r = samples[idx] / 255
    const g = samples[idx + 1] / 255
    const b = samples[idx + 2] / 255
    if (r > 0.94 && g > 0.94 && b > 0.94) nearWhiteCount++
    colors.push([r, g, b])
  }

  // If at least 25% of perimeter samples are pure white paper, snap to [1, 1, 1] so glyph anti-aliasing never produces a gray rectangle
  if (nearWhiteCount >= Math.ceil(pts.length * 0.25)) {
    return [1, 1, 1]
  }

  // Otherwise pick the 80th-percentile brightest RGB component-wise to ignore dark ink strokes
  const rs = colors.map((c) => c[0]).sort((a, b) => a - b)
  const gs = colors.map((c) => c[1]).sort((a, b) => a - b)
  const bs = colors.map((c) => c[2]).sort((a, b) => a - b)
  const hi = Math.min(colors.length - 1, Math.floor(colors.length * 0.8))
  return [rs[hi], gs[hi], bs[hi]]
}

function boxesOverlap(a: BBox, b: BBox, pad = 0): boolean {
  return (
    a.x - pad < b.x + b.w &&
    a.x + a.w + pad > b.x &&
    a.y - pad < b.y + b.h &&
    a.y + a.h + pad > b.y
  )
}

// Formula & Glossary Shielding inside Prose Spans (matches existing ⟦M0⟧ tokens first so they are never double-wrapped!)
const INLINE_MATH_SHIELD_REGEX =
  /(⟦M\d+⟧|\$[^$]+\$|\\[a-zA-Z]+(?:\{[^}]*\})+|[|]?[A-Za-z0-9_'’′()]+\s*[=<>≠≤≥±]+\s*[A-Za-z0-9_'’′!.…+\-*/^()]+|\b[fghFGH]\([a-zA-Z0-9,\s+-]+\)|[([]\s*[a-zA-Z0-9+-]+\s*[;,]\s*[a-zA-Z0-9+-]+\s*[)\]]|\b[A-Za-z]['’′]+|\b(?:[A-Za-z]|\d+)°|[α-ωΑ-Ω]|\b(?:[A-Za-z]\d+|[A-Za-z]_[A-Za-z0-9]+(?:\^[A-Za-z0-9]+)?|[A-Za-z]!)\b|\[\d+(?:,\s*\d+)*\])/g

// Multilingual Academic Glossary Manager (ported from ThanhNguyxnOrg/LayoutLingua/layoutlingua/translation/glossary.py)
// Loads JSON glossaries from src/engine/glossaries/academic_math_en_{lang}.json with bidirectional & English-pivot support.
const GLOSSARY_CACHE = new Map<string, Record<string, string>>()
const GLOSSARY_LANG_MAP: Record<string, string> = {
  vietnamese: 'vi',
  vi: 'vi',
  chinese: 'zh',
  'chinese-simplified': 'zh',
  zh: 'zh',
  'zh-cn': 'zh',
  'zh-hans': 'zh',
  'chinese-traditional': 'zh-tw',
  'zh-tw': 'zh-tw',
  'zh-hant': 'zh-tw',
  japanese: 'ja',
  ja: 'ja',
  korean: 'ko',
  ko: 'ko',
  german: 'de',
  de: 'de',
  french: 'fr',
  fr: 'fr',
  spanish: 'es',
  es: 'es',
  english: 'en',
  en: 'en',
  russian: 'ru',
  ru: 'ru',
  italian: 'it',
  it: 'it',
  portuguese: 'pt',
  pt: 'pt',
  indonesian: 'id',
  id: 'id',
  dutch: 'nl',
  nl: 'nl',
  polish: 'pl',
  pl: 'pl',
  turkish: 'tr',
  tr: 'tr',
  ukrainian: 'uk',
  uk: 'uk',
}

function loadBuiltinGlossary(sourceLang = 'en', targetLang = 'vi'): Record<string, string> {
  const sCode = GLOSSARY_LANG_MAP[(sourceLang || 'en').toLowerCase().trim()] || sourceLang.toLowerCase().trim()
  const tCode = GLOSSARY_LANG_MAP[(targetLang || 'vi').toLowerCase().trim()] || targetLang.toLowerCase().trim()
  if (sCode === tCode) return {}

  const cacheKey = `${sCode}_${tCode}`
  if (GLOSSARY_CACHE.has(cacheKey)) {
    return GLOSSARY_CACHE.get(cacheKey)!
  }

  const glossaryDir = path.join(process.cwd(), 'src', 'engine', 'glossaries')
  const terms: Record<string, string> = {}

  const parseJsonTerms = (filePath: string): Record<string, string> => {
    try {
      if (!fs.existsSync(filePath)) return {}
      const raw = JSON.parse(fs.readFileSync(filePath, 'utf-8'))
      const dict = raw?.terms && typeof raw.terms === 'object' ? raw.terms : raw
      const out: Record<string, string> = {}
      if (dict && typeof dict === 'object' && !Array.isArray(dict)) {
        for (const [k, v] of Object.entries(dict)) {
          if (String(k).trim() && String(v).trim()) {
            out[String(k).trim()] = String(v).trim()
          }
        }
      }
      return out
    } catch {
      return {}
    }
  }

  if (sCode === 'en') {
    Object.assign(terms, parseJsonTerms(path.join(glossaryDir, `academic_math_en_${tCode}.json`)))
  } else if (tCode === 'en') {
    const inv = parseJsonTerms(path.join(glossaryDir, `academic_math_en_${sCode}.json`))
    for (const [k, v] of Object.entries(inv)) {
      if (v && k && !(v in terms)) {
        terms[v] = k
      }
    }
  } else {
    // Pivot via English: (sCode -> en) + (en -> tCode)
    const sToEn = loadBuiltinGlossary(sCode, 'en')
    const enToT = loadBuiltinGlossary('en', tCode)
    const enToTLower = new Map<string, string>()
    for (const [k, v] of Object.entries(enToT)) {
      enToTLower.set(k.toLowerCase(), v)
    }
    for (const [sTerm, enTerm] of Object.entries(sToEn)) {
      const targetVal = enToT[enTerm] || enToTLower.get(enTerm.toLowerCase())
      if (targetVal) {
        terms[sTerm] = targetVal
      }
    }
  }

  GLOSSARY_CACHE.set(cacheKey, terms)
  return terms
}

export function applyMultilingualGlossary(
  sourceText: string,
  translatedText: string,
  sourceLang = 'en',
  targetLang = 'vi',
  customGlossary?: string
): string {
  if (!translatedText) return translatedText
  const builtin = loadBuiltinGlossary(sourceLang, targetLang)
  const effective: Record<string, string> = { ...builtin }

  if (customGlossary && customGlossary.trim()) {
    for (const line of customGlossary.split(/\r?\n/)) {
      const trimmed = line.trim()
      if (!trimmed || trimmed.startsWith('#')) continue
      const parts = trimmed.split(/\s*(?:=|->|:)\s*/)
      if (parts.length >= 2 && parts[0].trim() && parts[1].trim()) {
        effective[parts[0].trim()] = parts[1].trim()
      }
    }
  }

  const entries = Object.entries(effective).sort((a, b) => b[0].length - a[0].length)
  if (entries.length === 0) return translatedText

  let result = translatedText
  const srcLower = sourceText.toLowerCase()

  for (const [sTerm, tTerm] of entries) {
    if (sTerm.length < 2) continue
    const sLow = sTerm.toLowerCase()
    if (!srcLower.includes(sLow) && !result.toLowerCase().includes(sLow)) continue
    if (result.toLowerCase().includes(tTerm.toLowerCase())) continue

    const escaped = sTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const isCjk = /[\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af]/.test(sTerm)
    const pat = isCjk
      ? new RegExp(escaped, 'gi')
      : new RegExp(`(?<![\\p{L}\\p{N}_])${escaped}(?![\\p{L}\\p{N}_])`, 'giu')

    if (pat.test(result)) {
      result = result.replace(pat, (m) =>
        m[0] === m[0].toUpperCase() && m[0] !== m[0].toLowerCase()
          ? tTerm.charAt(0).toUpperCase() + tTerm.slice(1)
          : tTerm
      )
    }
  }
  return result
}

function isAllCapsHeadingText(str: string): boolean {
  const trimmed = str.trim()
  if (trimmed.length < 4) return false
  if (trimmed !== trimmed.toUpperCase() || trimmed === trimmed.toLowerCase()) return false
  const letters = trimmed.match(/\p{L}/gu) || []
  return letters.length >= 4
}

function recaseAllCapsForNmt(str: string): string {
  // Normalize ALL-CAPS headings to sentence case (preserving Roman numerals and section prefixes)
  // so subword BPE tokenizers in NMT engines never truncate uppercase endings (e.g. "BINOMIA").
  let firstWordSeen = false
  return str.replace(/\p{L}+/gu, (word) => {
    if (/^(?:[IVXLCDM]+)$/i.test(word) && !firstWordSeen) {
      return word
    }
    const lower = word.toLowerCase()
    if (!firstWordSeen) {
      firstWordSeen = true
      return lower.charAt(0).toUpperCase() + lower.slice(1)
    }
    return lower
  })
}

const FRANC_ISO3_TO_LANG: Record<string, string> = {
  eng: 'en',
  vie: 'vi',
  cmn: 'zh-CN',
  jpn: 'ja',
  kor: 'ko',
  fra: 'fr',
  deu: 'de',
  spa: 'es',
  rus: 'ru',
  ita: 'it',
  por: 'pt',
  ind: 'id',
  zlm: 'id',
  nld: 'nl',
  pol: 'pl',
  tur: 'tr',
  ukr: 'uk',
}

const FRANC_ALLOWED_ISO3 = Object.keys(FRANC_ISO3_TO_LANG)

/**
 * Detects the natural language code of a sample text across all 17 supported languages.
 * Combines Unicode script range checks with statistical character trigram analysis (`franc-min`).
 */
export function detectLanguageFromText(sampleText: string): string {
  const s = (sampleText || '').slice(0, 4000)
  if (!s.trim()) return 'en'

  // 1. Exclusive Vietnamese characters (ă, đ, ơ, ư, and tone hooks/dots/tildes above/below circumflex/breve) or VNI encoding
  if (
    /[ăđơưĂĐƠƯảạằắẳẵặầấẩẫậẻẽẹềếểễệỉĩịỏọồốổỗộờớởỡợủũụừứửữựỷỹỵẢẠẰẮẲẴẶẦẤẨẪẬẺẼẸỀẾỂỄỆỈĨỊỎỌỒỐỔỖỘỜỚỞỠỢỦŨỤỪỨỬỮỰỶỸỴ]/.test(
      s
    ) ||
    /[A-Za-z][ÆæØøŒœŸÿ©®™µ¶]/.test(s)
  ) {
    return 'vi'
  }
  // 2. Japanese Hiragana / Katakana
  if (/[\u3040-\u30ff]/.test(s)) return 'ja'
  // 3. Korean Hangul
  if (/[\uac00-\ud7af]/.test(s)) return 'ko'
  // 4. Chinese (Traditional vs Simplified)
  if (/[\u4e00-\u9fff]/.test(s)) {
    return /[\u7E41\u9AD4\u570B\u5B78\u6578\u984C\u8AD6\u8207\u70BA\u9019\u5011\u500B\u6703\u767C\u5BE6\u5C0D\u958B\u95DC\u9EDE\u7DDA\u5713\u908A\u5C0E\u7D1A\u8907]/.test(
      s
    )
      ? 'zh-TW'
      : 'zh-CN'
  }
  // 5. Cyrillic (Ukrainian vs Russian)
  if (/[\u0400-\u04ff]/.test(s)) {
    return /[іїєґІЇЄҐ]/.test(s) ? 'uk' : 'ru'
  }
  // 6. Polish exclusive characters
  if (/[ąćęłńśźżĄĆĘŁŃŚŹŻ]/.test(s)) return 'pl'
  // 7. Turkish exclusive characters
  if (/[ğışĞİŞ]/.test(s)) return 'tr'

  // 8. Statistical trigram n-gram language detection via franc-min across supported languages
  const iso3 = franc(s, { only: FRANC_ALLOWED_ISO3, minLength: 10 })
  if (iso3 && iso3 !== 'und' && FRANC_ISO3_TO_LANG[iso3]) {
    return FRANC_ISO3_TO_LANG[iso3]
  }

  // Fallback on distinctive Latin orthography for very short strings (<10 chars)
  if (/[äöüßÄÖÜ]/.test(s)) return 'de'
  if (/[ñ¿¡]/.test(s)) return 'es'
  if (/[ãõÃÕ]/.test(s)) return 'pt'
  return 'en'
}

export function isAlreadyInTargetLanguage(
  text: string,
  sourceLang: string,
  targetLang: string
): boolean {
  const tl = normalizeLangCode(targetLang, 'en')
  const sl = normalizeLangCode(sourceLang, 'auto')
  if (sl === tl) return true
  const trimmed = text.trim()
  if (!trimmed) return true

  const words = trimmed.split(/\s+/).filter(Boolean)
  if (words.length < 6 && !CJK_CHAR_RE.test(trimmed)) return false
  if (tl === 'en' && MULTILINGUAL_SCRIPT_RE.test(trimmed)) return false

  const iso3 = franc(trimmed, { only: FRANC_ALLOWED_ISO3, minLength: 20 })
  if (!iso3 || iso3 === 'und') return false
  const detected = normalizeLangCode(FRANC_ISO3_TO_LANG[iso3] || '', '')
  return Boolean(detected && detected === tl)
}

export function shieldFormulas(
  text: string,
  targetLang = 'en',
  customGlossary?: string,
  sourceLang = 'auto'
): { masked: string; tokens: Record<string, string> } {
  const tokens: Record<string, string> = {}
  let idx = 0

  let working = text

  // 1. Shield user custom glossary terms if explicitly provided by user
  if (customGlossary && customGlossary.trim()) {
    const lines = customGlossary.split(/\r?\n/)
    for (const line of lines) {
      const parts = line.split(/\s*(?:=|->|:)\s*/)
      if (parts.length >= 2 && parts[0].trim() && parts[1].trim()) {
        const src = parts[0].trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
        const rep = parts[1].trim()
        working = working.replace(new RegExp(src, 'gi'), () => {
          const key = `⟦M${idx++}⟧`
          tokens[key] = rep
          return key
        })
      }
    }
  }

  // 2. Shield exact standalone headings, table labels, or TOC titles from the built-in multilingual academic glossary
  // (Full sentences are translated with complete NMT context so grammar and articles remain natural)
  const builtin = loadBuiltinGlossary(sourceLang, targetLang)
  const builtinEntries = Object.entries(builtin).sort((a, b) => b[0].length - a[0].length)
  if (builtinEntries.length > 0) {
    const strippedHeading = working
      .replace(/^(?:[IVXLCDM]+\.|\d+\.|[A-Za-z]\.|[a-z]\))\s*/i, '')
      .replace(/[:.]\s*$/, '')
      .trim()
      .toLowerCase()

    for (const [sTerm, tTerm] of builtinEntries) {
      const sTrim = sTerm.trim()
      const isExactHeading = strippedHeading.length >= 2 && strippedHeading === sTrim.toLowerCase()
      if (!isExactHeading) continue

      const escaped = sTrim.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      const isCjkTerm = CJK_CHAR_RE.test(sTrim)
      const pat = isCjkTerm
        ? new RegExp(`(?<!⟦)${escaped}(?!⟧)`, 'giu')
        : new RegExp(`(?<![\\p{L}\\p{N}_⟦])${escaped}(?![\\p{L}\\p{N}_⟧])`, 'giu')
      if (pat.test(working)) {
        working = working.replace(pat, (m) => {
          const key = `⟦M${idx++}⟧`
          if (m === m.toUpperCase() && m !== m.toLowerCase()) {
            tokens[key] = tTerm.toUpperCase()
          } else if (m[0] === m[0].toUpperCase() && m[0] !== m[0].toLowerCase()) {
            tokens[key] = tTerm.charAt(0).toUpperCase() + tTerm.slice(1)
          } else {
            tokens[key] = tTerm.toLowerCase()
          }
          return key
        })
      }
    }
  }

  // 3. Shield inline mathematical formulas & variables (never natural language words!)
  const masked = working.replace(INLINE_MATH_SHIELD_REGEX, (match) => {
    if (/^⟦M\d+⟧$/.test(match)) return match
    const key = `⟦M${idx++}⟧`
    tokens[key] = match
    return key
  })
  return { masked, tokens }
}

export function restoreFormulas(translated: string, tokens: Record<string, string>): string {
  let repaired = translated
    .replace(/⟦\s*M\s*[-_]?\s*(\d+)\s*⟧/gi, '⟦M$1⟧')
    .replace(/\[\s*M\s*[-_]?\s*(\d+)\s*\]/gi, '⟦M$1⟧')
    .replace(/【\s*M\s*[-_]?\s*(\d+)\s*】/gi, '⟦M$1⟧')

  for (const [key, val] of Object.entries(tokens)) {
    repaired = repaired.split(key).join(val)
  }
  return repaired
}

const LANG_CODE_NORMALIZE_MAP: Record<string, string> = {
  english: 'en',
  en: 'en',
  vietnamese: 'vi',
  vi: 'vi',
  'chinese (simplified)': 'zh-CN',
  zh: 'zh-CN',
  'zh-cn': 'zh-CN',
  'chinese (traditional)': 'zh-TW',
  'zh-tw': 'zh-TW',
  japanese: 'ja',
  ja: 'ja',
  korean: 'ko',
  ko: 'ko',
  french: 'fr',
  fr: 'fr',
  german: 'de',
  de: 'de',
  spanish: 'es',
  es: 'es',
  russian: 'ru',
  ru: 'ru',
  italian: 'it',
  it: 'it',
  portuguese: 'pt',
  pt: 'pt',
  indonesian: 'id',
  id: 'id',
  dutch: 'nl',
  nl: 'nl',
  polish: 'pl',
  pl: 'pl',
  turkish: 'tr',
  tr: 'tr',
  ukrainian: 'uk',
  uk: 'uk',
}

export function normalizeLangCode(lang: string, fallback = 'en'): string {
  if (!lang) return fallback
  const key = lang.trim().toLowerCase()
  if (key === 'auto') return 'auto'
  return LANG_CODE_NORMALIZE_MAP[key] || lang.trim()
}

const translationCache = new Map<string, string>()

const GOOGLE_AT_MIRRORS = [
  'https://translate.google.com/translate_a/single?client=at&dt=t',
  'https://translate.google.com.vn/translate_a/single?client=at&dt=t',
  'https://translate.google.de/translate_a/single?client=at&dt=t',
  'https://translate.google.co.jp/translate_a/single?client=at&dt=t',
]

async function translateViaGoogleMirror(query: string, sl: string, tl: string): Promise<string | null> {
  const body = new URLSearchParams({ sl, tl, q: query }).toString()
  for (const endpoint of GOOGLE_AT_MIRRORS) {
    try {
      const resp = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
          'User-Agent': 'AndroidTranslate/6.29.0.05.421280910 (Linux; U; Android 11; Pixel 5)',
        },
        body,
        signal: AbortSignal.timeout(5500),
      })
      if (resp.ok) {
        const data: any = await resp.json()
        if (Array.isArray(data?.[0])) {
          const text = data[0].map((part: any) => part?.[0] || '').join('')
          if (text.trim()) return text
        }
      }
    } catch {
      // Try next mirror
    }
  }
  try {
    const url = `https://translate.googleapis.com/translate_a/single?client=gtx&sl=${encodeURIComponent(
      sl
    )}&tl=${encodeURIComponent(tl)}&dt=t&q=${encodeURIComponent(query)}`
    const resp = await fetch(url, { signal: AbortSignal.timeout(5000) })
    if (resp.ok) {
      const data: any = await resp.json()
      if (Array.isArray(data?.[0])) {
        const text = data[0].map((part: any) => part?.[0] || '').join('')
        if (text.trim()) return text
      }
    }
  } catch {
    // Fallback handled by caller
  }
  return null
}

/**
 * Translates an array of strings in a single fast batch with formula shielding.
 */
export async function translateBatchWithFormulaShield(
  texts: string[],
  sourceLang: string,
  targetLang: string,
  options?: {
    provider?: string
    geminiKey?: string
    geminiModel?: string
    openaiKey?: string
    openaiEndpoint?: string
    openaiModel?: string
    customGlossary?: string
  }
): Promise<string[]> {
  if (texts.length === 0) return []

  const tl = normalizeLangCode(targetLang, 'en')
  const rawSl = normalizeLangCode(sourceLang, 'auto')
  const sl = rawSl === tl ? 'auto' : rawSl
  const glossarySl = sl === 'auto' ? detectLanguageFromText(texts.join(' ')) : sl

  const allCapsFlags = texts.map((t) => isAllCapsHeadingText(t))
  // Detach leading structural Roman numeral or hierarchical section numbering (e.g. "I. ", "VI. ", "1.2. ")
  // so NMT translates the heading/bookmark body cleanly without misinterpreting "I." or "V." as pronouns/abbreviations
  const STRUCTURAL_PREFIX_RE =
    /^(\s*(?:(?:I{1,3}|IV|VI{0,3}|IX|X{1,3}|XI{1,3}|XIV|XVI{0,3}|XIX|XX)\.|\d+(?:\.\d+)*\.|[a-d]\))\s+)(.+)$/su
  const detachedPrefixes: string[] = new Array(texts.length).fill('')
  const strippedInputs = texts.map((t, idx) => {
    const m = t.match(STRUCTURAL_PREFIX_RE)
    if (m && /\p{L}{2,}/u.test(m[2])) {
      detachedPrefixes[idx] = m[1]
      return m[2]
    }
    return t
  })

  const preparedTexts = strippedInputs.map((t, idx) =>
    allCapsFlags[idx] ? recaseAllCapsForNmt(t) : t
  )
  const shieldedItems = preparedTexts.map((t) =>
    shieldFormulas(t, tl, options?.customGlossary, glossarySl)
  )

  // Check if all masked strings are already pure tokens or already in target language
  const results: string[] = new Array(texts.length).fill('')
  const pendingIndices: number[] = []

  for (let i = 0; i < shieldedItems.length; i++) {
    if (isAlreadyInTargetLanguage(strippedInputs[i], glossarySl, tl)) {
      results[i] = strippedInputs[i]
      continue
    }
    const maskedTrim = shieldedItems[i].masked.trim()
    const cacheKey = `${sl}|${tl}|${maskedTrim}`
    if (/^(?:[\dIVXLCDM]+\.\s*|[a-zA-Z][.)]\s*)?⟦M\d+⟧[.!:;,]?$/i.test(maskedTrim)) {
      results[i] = restoreFormulas(maskedTrim, shieldedItems[i].tokens)
    } else if (translationCache.has(cacheKey)) {
      results[i] = restoreFormulas(translationCache.get(cacheKey)!, shieldedItems[i].tokens)
    } else {
      pendingIndices.push(i)
    }
  }

  const finalizeResults = () =>
    results.map((tr, idx) => {
      const glossed = applyMultilingualGlossary(
        strippedInputs[idx],
        tr,
        glossarySl,
        tl,
        options?.customGlossary
      )
      const cased = allCapsFlags[idx] ? glossed.toUpperCase() : glossed
      return detachedPrefixes[idx] ? `${detachedPrefixes[idx]}${cased}` : cased
    })

  if (pendingIndices.length === 0) {
    return finalizeResults()
  }

  const geminiKey = options?.geminiKey || process.env.GEMINI_API_KEY || ''

  async function translateIndicesWithGemini(indices: number[]): Promise<boolean> {
    if (!geminiKey || indices.length === 0) return false
    try {
      const modelId = options?.geminiModel || 'gemini-2.5-flash'
      const payload = indices.map((idx) => shieldedItems[idx].masked)
      const resp = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(
          modelId
        )}:generateContent?key=${encodeURIComponent(geminiKey)}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            contents: [
              {
                role: 'user',
                parts: [
                  {
                    text: `Translate each item in the following JSON array into language "${tl}". Preserve all tokens like ⟦M0⟧, ⟦M1⟧ exactly as written. Return ONLY a valid JSON array of strings with the exact same length (${payload.length}).\n\n${JSON.stringify(
                      payload
                    )}`,
                  },
                ],
              },
            ],
            generationConfig: { temperature: 0.1 },
          }),
          signal: AbortSignal.timeout(10000),
        }
      )
      if (resp.ok) {
        const data: any = await resp.json()
        const rawText = data?.candidates?.[0]?.content?.parts?.[0]?.text || ''
        const jsonMatch = rawText.match(/\[[\s\S]*\]/)
        if (jsonMatch) {
          const parsed = JSON.parse(jsonMatch[0])
          if (Array.isArray(parsed) && parsed.length === indices.length) {
            for (let k = 0; k < indices.length; k++) {
              const origIdx = indices[k]
              const trStr = String(parsed[k]).trim()
              const cacheKey = `${sl}|${tl}|${shieldedItems[origIdx].masked.trim()}`
              translationCache.set(cacheKey, trStr)
              results[origIdx] = restoreFormulas(trStr, shieldedItems[origIdx].tokens)
            }
            return true
          }
        }
      }
    } catch {
      // Fallback below
    }
    return false
  }

  // 1. Try Gemini API if explicitly selected
  if (options?.provider === 'gemini' && geminiKey) {
    if (await translateIndicesWithGemini(pendingIndices)) {
      return finalizeResults()
    }
  }

  // 2. Try OpenAI / Ollama if explicitly configured with key or local endpoint
  if (options?.provider === 'openai' && (options.openaiKey || options.openaiEndpoint)) {
    try {
      const base = (options.openaiEndpoint || 'https://api.openai.com/v1').replace(/\/$/, '')
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (options.openaiKey) headers['Authorization'] = `Bearer ${options.openaiKey}`
      const payload = pendingIndices.map((idx) => shieldedItems[idx].masked)
      const resp = await fetch(`${base}/chat/completions`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          model: options.openaiModel || 'gpt-4o-mini',
          temperature: 0.1,
          messages: [
            {
              role: 'system',
              content: `Translate each item in the JSON array into ${tl}. Preserve all tokens like ⟦M0⟧, ⟦M1⟧ exactly as written. Return ONLY a valid JSON array of strings of the exact same length.`,
            },
            {
              role: 'user',
              content: JSON.stringify(payload),
            },
          ],
        }),
        signal: AbortSignal.timeout(8000),
      })
      if (resp.ok) {
        const data: any = await resp.json()
        const rawContent = data?.choices?.[0]?.message?.content || ''
        const jsonMatch = rawContent.match(/\[[\s\S]*\]/)
        if (jsonMatch) {
          const parsed = JSON.parse(jsonMatch[0])
          if (Array.isArray(parsed) && parsed.length === pendingIndices.length) {
            for (let k = 0; k < pendingIndices.length; k++) {
              const origIdx = pendingIndices[k]
              const trStr = String(parsed[k]).trim()
              const cacheKey = `${sl}|${tl}|${shieldedItems[origIdx].masked.trim()}`
              translationCache.set(cacheKey, trStr)
              results[origIdx] = restoreFormulas(trStr, shieldedItems[origIdx].tokens)
            }
            return finalizeResults()
          }
        }
      }
    } catch {
      // Fallback to multi-mirror Google endpoint below
    }
  }

  // 3. Multi-mirror POST/GET Google Translate with automatic Gemini fallback on rate-limit
  const BATCH_CHAR_LIMIT = 2400
  let pPos = 0

  while (pPos < pendingIndices.length) {
    let pEnd = pPos
    let charCount = 0
    while (
      pEnd < pendingIndices.length &&
      (charCount + shieldedItems[pendingIndices[pEnd]].masked.length < BATCH_CHAR_LIMIT || pEnd === pPos)
    ) {
      charCount += shieldedItems[pendingIndices[pEnd]].masked.length + 12
      pEnd++
    }

    const batchIndices = pendingIndices.slice(pPos, pEnd)
    const query = batchIndices.map((idx) => shieldedItems[idx].masked.replace(/\n/g, ' ')).join('\n')

    let batchSuccess = false
    const fullTranslated = await translateViaGoogleMirror(query, sl, tl)
    if (fullTranslated) {
      const splitLines = fullTranslated.split('\n').map((s: string) => s.trim())
      if (splitLines.length === batchIndices.length) {
        for (let k = 0; k < batchIndices.length; k++) {
          const origIdx = batchIndices[k]
          const cacheKey = `${sl}|${tl}|${shieldedItems[origIdx].masked.trim()}`
          translationCache.set(cacheKey, splitLines[k])
          results[origIdx] = restoreFormulas(splitLines[k], shieldedItems[origIdx].tokens)
        }
        batchSuccess = true
      }
    }

    if (!batchSuccess) {
      // Try Gemini fallback first before firing individual requests
      const geminiOk = await translateIndicesWithGemini(batchIndices)
      if (!geminiOk) {
        for (const origIdx of batchIndices) {
          const item = shieldedItems[origIdx]
          const singleTr = await translateViaGoogleMirror(item.masked.replace(/\n/g, ' '), sl, tl)
          if (singleTr) {
            const cleanTr = singleTr.trim()
            const cacheKey = `${sl}|${tl}|${item.masked.trim()}`
            translationCache.set(cacheKey, cleanTr)
            results[origIdx] = restoreFormulas(cleanTr, item.tokens)
          } else {
            results[origIdx] = restoreFormulas(item.masked, item.tokens)
          }
        }
      }
    }

    pPos = pEnd
  }

  return finalizeResults()
}

/**
 * Extracts layout-aware ProseGroups and MathObstacles from a single MuPDF page.
 */
export function analyzePdfPageLayout(
  mupdf: any,
  mupdfDoc: any,
  pageIndex: number
): {
  pageW: number
  pageH: number
  proseGroups: ProseGroup[]
  mathObstacles: Array<{ bbox: BBox; text: string }>
  linkObstacles: Array<{ bbox: BBox; text: string; uri: string }>
} {
  const page = mupdfDoc.loadPage(pageIndex)
  const bounds = page.getBounds()
  const pageW = bounds[2] - bounds[0]
  const pageH = bounds[3] - bounds[1]

  const nativeLinks: Array<{ bbox: BBox; uri: string; isExternal: boolean }> = []
  try {
    const rawLinks = page.getLinks?.() || []
    for (const lnk of rawLinks) {
      const lb = lnk.getBounds?.()
      const rawUri = String(lnk.getURI?.() || '').trim()
      if (!Array.isArray(lb) || lb.length < 4 || !rawUri) continue
      const bbox: BBox = {
        x: lb[0],
        y: lb[1],
        w: Math.max(4, lb[2] - lb[0]),
        h: Math.max(4, lb[3] - lb[1]),
      }
      if (/^https?:\/\/|^mailto:/i.test(rawUri)) {
        nativeLinks.push({ bbox, uri: rawUri, isExternal: true })
      } else {
        // Internal document navigation link (GoTo page destination)
        let targetPage = -1
        const pageMatch = rawUri.match(/^#(?:page=)?(\d+)\b/i)
        if (pageMatch) {
          targetPage = parseInt(pageMatch[1], 10)
        } else {
          try {
            const resolvedIdx = mupdfDoc.resolveLink?.(rawUri)
            if (typeof resolvedIdx === 'number' && resolvedIdx >= 0) {
              targetPage = resolvedIdx + 1
            }
          } catch {
            // Ignore unresolvable named destination
          }
        }
        if (targetPage >= 1) {
          nativeLinks.push({ bbox, uri: `#page=${targetPage}`, isExternal: false })
        }
      }
    }
  } catch {
    // Ignore link extraction errors on malformed PDFs
  }

  const pix = page.toPixmap(mupdf.Matrix.identity, mupdf.ColorSpace.DeviceRGB, false, true)
  const pixW = pix.getWidth()
  const pixH = pix.getHeight()
  const nComp = pix.getNumberOfComponents()
  const pixSamples = pix.getPixels()

  const rawChars: RawChar[] = []
  page.toStructuredText('preserve-whitespace').walk({
    onChar(c: string, origin: number[], font: any, size: number, quad: number[], color: number[]) {
      const x0 = Math.min(quad[0], quad[2], quad[4], quad[6])
      const x1 = Math.max(quad[0], quad[2], quad[4], quad[6])
      const y0 = Math.min(quad[1], quad[3], quad[5], quad[7])
      const y1 = Math.max(quad[1], quad[3], quad[5], quad[7])
      const fontName = String(font.getName() || '')
      let rgbColor: [number, number, number] = [0, 0, 0]
      if (Array.isArray(color)) {
        if (color.length === 1) rgbColor = [color[0], color[0], color[0]]
        else if (color.length >= 3) rgbColor = [color[0], color[1], color[2]]
      }
      rawChars.push({
        c,
        ox: origin[0],
        oy: origin[1],
        x0,
        y0,
        x1,
        y1,
        font: fontName,
        bold: Boolean(font.isBold?.() || /bold/i.test(fontName)),
        italic: Boolean(font.isItalic?.() || /italic|oblique/i.test(fontName)),
        serif: Boolean(font.isSerif?.() || /times|cambria|georgia|serif|vni/i.test(fontName)),
        mono: Boolean(font.isMono?.() || /courier|mono|consolas/i.test(fontName)),
        size,
        color: rgbColor,
      })
    },
  })

  // Normalize superscript degree symbols (MT Extra 0xf06f, Symbol 0xf0b0, or '°'/'º' at size < 8.5)
  // onto the baseline of their preceding character so inline degree tokens like "60°" and "n°" stay 1D.
  for (const ch of rawChars) {
    if (ch.size >= 8.5 || ch.font.includes('VNI')) continue
    const code = ch.c.charCodeAt(0)
    const isDegreeGlyph =
      (/mt extra/i.test(ch.font) && code === 0xf06f) ||
      code === 0xf0b0 ||
      ch.c === '°' ||
      ch.c === 'º'
    if (!isDegreeGlyph) continue

    const prevMain = rawChars.find(
      (mc) =>
        mc.size >= 8.5 &&
        mc.c.trim() !== '' &&
        mc.oy - ch.oy >= 1.2 &&
        mc.oy - ch.oy <= mc.size * 0.95 &&
        ch.x0 >= mc.x0 - 1 &&
        ch.x0 - mc.x1 <= 4.5
    )
    if (prevMain) {
      ch.c = '°'
      ch.font = prevMain.font
      ch.oy = prevMain.oy
      ch.size = prevMain.size
      ch.y0 = Math.min(ch.y0, prevMain.y0)
      ch.y1 = Math.max(ch.y1, prevMain.y1)
    }
  }

  // Separate remaining sub/superscript chars (size < 8.5 and not VNI) as immediate math obstacles
  const subSupChars = rawChars.filter((ch) => ch.c.trim() !== '' && ch.size < 8.5 && !ch.font.includes('VNI'))
  const mainChars = rawChars.filter((ch) => !(ch.size < 8.5 && !ch.font.includes('VNI')))

  const mathObstacles: Array<{ bbox: BBox; text: string }> = []
  const linkObstacles: Array<{ bbox: BBox; text: string; uri: string }> = []
  let lastBoldProperName = ''

  for (const sc of subSupChars) {
    mathObstacles.push({
      bbox: { x: sc.x0, y: sc.y0, w: Math.max(2, sc.x1 - sc.x0), h: Math.max(4, sc.y1 - sc.y0) },
      text: sc.c,
    })
  }

  // Group mainChars into baseline rows
  const baselineRows: Array<{ oy: number; size: number; chars: RawChar[] }> = []
  for (const ch of mainChars) {
    let row = baselineRows.find(
      (r) => Math.abs(r.oy - ch.oy) <= 2.2 && Math.abs(r.size - ch.size) <= 2.8
    )
    if (!row) {
      row = { oy: ch.oy, size: ch.size, chars: [] }
      baselineRows.push(row)
    }
    row.chars.push(ch)
  }
  baselineRows.sort((a, b) => a.oy - b.oy)

  const proseSpans: ProseSpan[] = []

  const decodeCharSeqToText = (chars: RawChar[]): string => {
    let out = ''
    let idx = 0
    while (idx < chars.length) {
      const isVni = chars[idx].font.includes('VNI')
      const start = idx
      while (idx < chars.length && chars[idx].font.includes('VNI') === isVni) {
        idx++
      }
      const rawSeg = decodeSymbolPua(
        chars
          .slice(start, idx)
          .map((c) => c.c)
          .join('')
      )
      out += isVni ? decodeVniToUnicode(rawSeg) : rawSeg
    }
    return out
  }

  for (const row of baselineRows) {
    row.chars.sort((a, b) => a.x0 - b.x0)

    const dedupChars: RawChar[] = []
    for (const ch of row.chars) {
      const prev = dedupChars[dedupChars.length - 1]
      if (prev && prev.c === ch.c && Math.abs(prev.x0 - ch.x0) < 0.8) continue
      dedupChars.push(ch)
    }

    while (dedupChars.length > 0 && !dedupChars[0].c.trim()) dedupChars.shift()
    while (dedupChars.length > 0 && !dedupChars[dedupChars.length - 1].c.trim()) dedupChars.pop()
    if (dedupChars.length === 0) continue

    // 1. Check for TOC leader dots pattern across the entire baseline row first
    const fullRowStr = decodeCharSeqToText(dedupChars).trim()
    const rowTocMatch = fullRowStr.match(/^(.*?)\s*((?:\.\s*){4,})\s*(\d+|[ivxlcdm]+)\s*$/i)
    if (rowTocMatch && isTranslatableProseText(rowTocMatch[1])) {
      const x0 = Math.min(...dedupChars.map((c) => c.x0))
      const y0 = Math.min(...dedupChars.map((c) => c.y0))
      const x1 = Math.max(...dedupChars.map((c) => c.x1))
      const y1 = Math.max(...dedupChars.map((c) => c.y1))
      const first = dedupChars[0]
      proseSpans.push({
        text: fullRowStr,
        x0,
        y0,
        x1,
        y1,
        oy: first.oy,
        size: first.size,
        bold: first.bold,
        italic: first.italic,
        serif: first.serif,
        mono: first.mono,
        color: first.color,
        bgColor: sampleBackgroundRGB(pixSamples, pixW, pixH, nComp, x0, y0, x1, y1),
        leftClearanceX: x0,
        rightClearanceX: x1,
        isToc: true,
        tocTitle: rowTocMatch[1].trim(),
        tocPageNum: rowTocMatch[3].trim(),
      })
      continue
    }

    // 2. Split into horizontal column runs only on genuine column gaps (do NOT split on inline font switches)
    const hRuns: RawChar[][] = []
    let curRun: RawChar[] = []
    for (const ch of dedupChars) {
      if (curRun.length > 0) {
        const prev = curRun[curRun.length - 1]
        const gap = ch.x0 - prev.x1
        if (gap > Math.max(14, prev.size * 1.4)) {
          hRuns.push(curRun)
          curRun = []
        }
      }
      curRun.push(ch)
    }
    if (curRun.length > 0) hRuns.push(curRun)

    for (const rawRun of hRuns) {
      while (rawRun.length > 0 && !rawRun[0].c.trim()) rawRun.shift()
      while (rawRun.length > 0 && !rawRun[rawRun.length - 1].c.trim()) rawRun.pop()
      if (rawRun.length === 0) continue

      const normRunStr = decodeCharSeqToText(rawRun).trim()
      const tocMatch = normRunStr.match(/^(.*?)\s*((?:\.\s*){4,})\s*(\d+|[ivxlcdm]+)\s*$/i)
      if (tocMatch && isTranslatableProseText(tocMatch[1])) {
        const x0 = Math.min(...rawRun.map((c) => c.x0))
        const y0 = Math.min(...rawRun.map((c) => c.y0))
        const x1 = Math.max(...rawRun.map((c) => c.x1))
        const y1 = Math.max(...rawRun.map((c) => c.y1))
        const first = rawRun[0]
        proseSpans.push({
          text: normRunStr,
          x0,
          y0,
          x1,
          y1,
          oy: first.oy,
          size: first.size,
          bold: first.bold,
          italic: first.italic,
          serif: first.serif,
          mono: first.mono,
          color: first.color,
          bgColor: sampleBackgroundRGB(pixSamples, pixW, pixH, nComp, x0, y0, x1, y1),
          leftClearanceX: x0,
          rightClearanceX: x1,
          isToc: true,
          tocTitle: tocMatch[1].trim(),
          tocPageNum: tocMatch[3].trim(),
        })
        continue
      }

      // Normalize split VNI kerning spaces at the character level before word tokenization
      const run: RawChar[] = []
      for (let cIdx = 0; cIdx < rawRun.length; cIdx++) {
        const cur = rawRun[cIdx]
        if (
          !cur.c.trim() &&
          run.length > 0 &&
          cIdx + 1 < rawRun.length &&
          run[run.length - 1].font.includes('VNI') &&
          rawRun[cIdx + 1].font.includes('VNI')
        ) {
          const prevC = run[run.length - 1].c
          const nextChar = rawRun[cIdx + 1]
          const nextC = nextChar.c
          // Case 1: "vo ânghieäm" -> attach 'â' to 'o', then keep the space
          if (
            /^[oO]$/.test(prevC) &&
            /^[âÂ]$/.test(nextC) &&
            cIdx + 2 < rawRun.length &&
            /^[a-zA-Z]$/.test(rawRun[cIdx + 2].c)
          ) {
            run.push(nextChar)
            run.push(cur)
            cIdx++
            continue
          }
          // Case 2: split VNI tone mark after space (e.g. "ño ù" or "chö ûsoá")
          if (/^[a-zA-ZôöÔÖ]$/.test(prevC) && /^[ùúûõïäëâêÙÚÛÕÏÄËÂÊ]$/.test(nextC)) {
            run.push(nextChar)
            if (cIdx + 2 < rawRun.length && rawRun[cIdx + 2].c.trim()) {
              run.push(cur)
            }
            cIdx++
            continue
          }
        }
        run.push(cur)
      }

      // Tokenize run into words separated by whitespace, Symbol/non-Symbol boundary, or hyperlink color switch
      const wordTokens: WordToken[] = []
      let wChars: RawChar[] = []

      const flushWord = () => {
        if (wChars.length === 0) return
        const hasSym = wChars.some((c) => /symbol|mt extra|math|cmmi|cmsy/i.test(c.font))
        const hasVni = wChars.some((c) => c.font.includes('VNI'))
        const isItal = wChars.some((c) => c.italic)
        const txt = decodeCharSeqToText(wChars)

        const wx0 = Math.min(...wChars.map((c) => c.x0))
        const wy0 = Math.min(...wChars.map((c) => c.y0))
        const wx1 = Math.max(...wChars.map((c) => c.x1))
        const wy1 = Math.max(...wChars.map((c) => c.y1))

        const isNaturalScriptWord =
          MULTILINGUAL_SCRIPT_RE.test(txt) && !EXPLICIT_MATH_SYMBOL_RE.test(txt)

        // Check if any subscript/superscript char or vector arrow (MT Extra / Symbol) is horizontally & vertically adjacent to this word
        // (Natural script words with diacritics/CJK/Cyrillic are never subscripted math variables)
        const hasAdjSubSup =
          !isNaturalScriptWord &&
          (subSupChars.some(
            (sc) =>
              sc.x0 >= wx0 - 3 &&
              sc.x1 <= wx1 + 9 &&
              sc.y0 >= wy0 - 8 &&
              sc.y1 <= wy1 + 10
          ) ||
            rawChars.some(
              (rc) =>
                /mt extra|symbol/i.test(rc.font) &&
                rc.x0 >= wx0 - 3 &&
                rc.x1 <= wx1 + 4 &&
                rc.y0 >= wy0 - 9 &&
                rc.y1 <= wy1 + 4 &&
                Math.abs(rc.oy - wChars[0].oy) >= 1.5
            ))

        const first = wChars[0]
        const wBox: BBox = { x: wx0, y: wy0, w: wx1 - wx0, h: wy1 - wy0 }
        const overlapsExternalLink = nativeLinks.some(
          (nl) => nl.isExternal && boxesOverlap(wBox, nl.bbox, 1)
        )
        const isBlueHyperlinkColor =
          !isNaturalScriptWord &&
          first.color[2] >= 0.75 &&
          first.color[0] <= 0.2 &&
          first.color[1] <= 0.25
        const isHyperlink = overlapsExternalLink || isBlueHyperlinkColor

        wordTokens.push({
          text: txt,
          x0: wx0,
          y0: wy0,
          x1: wx1,
          y1: wy1,
          ox: first.ox,
          oy: first.oy,
          size: first.size,
          font: first.font,
          bold: wChars.some((c) => c.bold),
          italic: isItal,
          serif: first.serif,
          mono: first.mono,
          color: first.color,
          hasSymbolFont: hasSym,
          hasVniFont: hasVni,
          hasAdjSubSup,
          isHyperlink,
          isMath:
            isHyperlink || isMathWordToken(txt, hasSym, hasVni, hasAdjSubSup, isItal, first.mono),
        })
        wChars = []
      }

      for (const ch of run) {
        if (!ch.c.trim()) {
          flushWord()
        } else {
          if (wChars.length > 0) {
            const prev = wChars[wChars.length - 1]
            const prevSym = /symbol|mt extra/i.test(prev.font)
            const curSym = /symbol|mt extra/i.test(ch.font)
            const colorDiff = Math.hypot(
              ch.color[0] - prev.color[0],
              ch.color[1] - prev.color[1],
              ch.color[2] - prev.color[2]
            )
            const prevCjk = CJK_CHAR_RE.test(prev.c)
            const curCjk = CJK_CHAR_RE.test(ch.c)
            const digitToProseFont =
              /[0-9)]/.test(prev.c) &&
              prev.font !== ch.font &&
              !curSym &&
              /\p{L}/u.test(ch.c)
            if (
              prevSym !== curSym ||
              prevCjk !== curCjk ||
              colorDiff > 0.35 ||
              digitToProseFont ||
              ch.x0 - prev.x1 > Math.max(3.5, prev.size * 0.35)
            ) {
              flushWord()
            }
          }
          wChars.push(ch)
        }
      }
      flushWord()

      if (wordTokens.length === 0) continue

      // Track leading bold capitalized proper name in footnotes/entries (for resolving flattened citation links)
      const leadingBoldWords: string[] = []
      for (let wi = 0; wi < Math.min(wordTokens.length, 6); wi++) {
        const wt = wordTokens[wi]
        const rawW = wt.text.trim()
        if (wt.bold && !wt.isHyperlink && /^\p{Lu}[\p{L}.,'-]*$/u.test(rawW)) {
          leadingBoldWords.push(rawW.replace(/[,.;:]+$/g, '').trim())
        } else if (leadingBoldWords.length > 0 && !wt.bold) {
          break
        }
      }
      if (leadingBoldWords.length >= 2) {
        lastBoldProperName = leadingBoldWords.join(' ')
      }

      const proseTokens = wordTokens.filter((w) => !w.isMath)
      const proseWordCount = proseTokens.length
      const lineIsMostlyItalic =
        proseTokens.length >= 2 &&
        proseTokens.filter((w) => w.italic).length >= proseTokens.length * 0.6
      const hasUpperProseWord = wordTokens.some(
        (w) =>
          !w.isMath &&
          w.text === w.text.toUpperCase() &&
          w.text !== w.text.toLowerCase() &&
          (MULTILINGUAL_SCRIPT_RE.test(w.text) || /\p{Lu}{4,}/u.test(w.text))
      )

      const hasNonGreekSymbol = (t: WordToken): boolean =>
        t.hasSymbolFont && !/^[(),.;:[\]]*(?:[α-ωΑ-Ω]|[°'’′])[(),.;:[\]]*$/.test(t.text.trim())

      // Language-agnostic contextual pass: recover ALL-CAPS heading words, inline numbers, and 1D variables/symbols inside prose sentences
      if (proseWordCount >= 1) {
        for (let i = 0; i < wordTokens.length; i++) {
          const wt = wordTokens[i]
          if (wt.isHyperlink) continue
          const cleanTxt = wt.text.replace(/^[,.;:()[\]{}]+|[,.;:()[\]{}]+$/g, '').trim()

          // Standalone punctuation like "(" or ")" between prose words or 1D Greek letters
          if (wt.isMath && !wt.hasAdjSubSup && !cleanTxt && /^[(),.;:[\]]+$/.test(wt.text.trim())) {
            const prevOk =
              i > 0 &&
              (!wordTokens[i - 1].isMath ||
                (!wordTokens[i - 1].hasAdjSubSup && !hasNonGreekSymbol(wordTokens[i - 1])))
            const nextOk =
              i < wordTokens.length - 1 &&
              (!wordTokens[i + 1].isMath ||
                (!wordTokens[i + 1].hasAdjSubSup && !hasNonGreekSymbol(wordTokens[i + 1])))
            if (prevOk && nextOk) {
              wt.isMath = false
              continue
            }
          }

          // 1. ALL-CAPS heading words or 1D uppercase acronyms/vertices (e.g. "FRS", "AI", "OI", "ABC") inside prose without 2D sub/superscripts
          if (
            wt.isMath &&
            !wt.hasAdjSubSup &&
            !wt.hasSymbolFont &&
            /^[A-Z]{2,5}$/.test(cleanTxt)
          ) {
            const prevProse = i > 0 && !wordTokens[i - 1].isMath
            const nextProse = i < wordTokens.length - 1 && !wordTokens[i + 1].isMath
            const adj2DMath =
              (i > 0 &&
                wordTokens[i - 1].isMath &&
                (wordTokens[i - 1].hasAdjSubSup ||
                  hasNonGreekSymbol(wordTokens[i - 1]) ||
                  EXPLICIT_MATH_SYMBOL_RE.test(wordTokens[i - 1].text))) ||
              (i < wordTokens.length - 1 &&
                wordTokens[i + 1].isMath &&
                (wordTokens[i + 1].hasAdjSubSup ||
                  hasNonGreekSymbol(wordTokens[i + 1]) ||
                  EXPLICIT_MATH_SYMBOL_RE.test(wordTokens[i + 1].text)))
            if (hasUpperProseWord || (!adj2DMath && (prevProse || nextProse) && proseWordCount >= 2)) {
              wt.isMath = false
              continue
            }
          }

          // 2. Upright lowercase words sharing spelling with math function names, OR 2-to-3 letter words in an all-italic prose line (where italic is the paragraph style, not a math style switch)
          if (
            wt.isMath &&
            !wt.hasAdjSubSup &&
            !wt.hasSymbolFont &&
            ((!wt.italic && /^[a-z]{3,5}$/.test(cleanTxt)) ||
              (lineIsMostlyItalic &&
                /^[a-z]{2,3}$/.test(cleanTxt) &&
                VOWEL_PATTERN.test(cleanTxt) &&
                !MATH_FUNCTION_NAMES.has(cleanTxt.toLowerCase())))
          ) {
            const prevProse = i > 0 && !wordTokens[i - 1].isMath
            const nextProse =
              i < wordTokens.length - 1 &&
              !wordTokens[i + 1].isMath &&
              wordTokens[i + 1].text.replace(/[^\p{L}]/gu, '').length >= 2
            if ((prevProse && nextProse) || (lineIsMostlyItalic && (prevProse || nextProse))) {
              wt.isMath = false
              continue
            }
          }

          // 3. Pure numbers, degree angles (60°), section numbers, percentages, or citations bounded by prose words
          if (
            wt.isMath &&
            !wt.hasAdjSubSup &&
            /^(?:\d+(?:[.,/-]\d+)*[°%:,.;)]?|\[\d+\])$/.test(cleanTxt)
          ) {
            const prevProse = i > 0 && !wordTokens[i - 1].isMath
            const nextProse = i < wordTokens.length - 1 && !wordTokens[i + 1].isMath
            const prevIs2DMath =
              i > 0 &&
              wordTokens[i - 1].isMath &&
              (wordTokens[i - 1].hasAdjSubSup ||
                hasNonGreekSymbol(wordTokens[i - 1]) ||
                EXPLICIT_MATH_SYMBOL_RE.test(wordTokens[i - 1].text))
            const nextIs2DMath =
              i < wordTokens.length - 1 &&
              wordTokens[i + 1].isMath &&
              (wordTokens[i + 1].hasAdjSubSup ||
                hasNonGreekSymbol(wordTokens[i + 1]) ||
                EXPLICIT_MATH_SYMBOL_RE.test(wordTokens[i + 1].text))
            if ((prevProse || nextProse) && !prevIs2DMath && !nextIs2DMath) {
              wt.isMath = false
              continue
            }
          }

          const is1DInlineToken = (t: WordToken): boolean => {
            const c = t.text.replace(/^[,.;:()[\]{}]+|[,.;:()[\]{}]+$/g, '').trim()
            return (
              !t.hasAdjSubSup &&
              !hasNonGreekSymbol(t) &&
              !/[″≤≥≠±∓×÷∑∏∫√∞∂∇∈∉⊂⊃⊆⊇∪∩∀∃⇔⇒→←↔]/.test(t.text) &&
              /^[a-zA-Z0-9=<>+\-*/^(),.;:[\]'’′°]+$/.test(t.text.trim()) &&
              !MATH_FUNCTION_NAMES.has(c.toLowerCase()) &&
              !/^[A-Z]{2,4}$/.test(c)
            )
          }

          // 4. Multi-character 1D expressions or short 1D inline equation/interval sequences inside a prose sentence
          // (e.g. "4=04; 8=08", "1!=1", "y=f(x)", "y = f(x)", "x = a", "(a; b)", "[a; b]", "a=d'")
          // Evaluated BEFORE single-letter variable recovery so spaced equations like "y = f(x)" are matched as a complete unit!
          if (proseWordCount >= 2 && wt.isMath && is1DInlineToken(wt)) {
            const prevProse = i > 0 && !wordTokens[i - 1].isMath
            let seqEnd = i
            while (
              seqEnd + 1 < wordTokens.length &&
              seqEnd - i < 2 &&
              is1DInlineToken(wordTokens[seqEnd + 1]) &&
              (wordTokens[seqEnd + 1].isMath ||
                /^[A-Za-z]{1,3}\([A-Za-z0-9,.;:\s+'’′+-]*\)[,.;:]?$/.test(
                  wordTokens[seqEnd + 1].text.trim()
                ))
            ) {
              seqEnd++
            }
            const combined1D = wordTokens
              .slice(i, seqEnd + 1)
              .map((w) => w.text.trim())
              .join(' ')
            const is1DEquationOrInterval =
              /^(?:[a-zA-Z0-9_'’′()]+\s*=\s*[a-zA-Z0-9_'’′!()+-]+|[fghFGH]\([a-zA-Z0-9,\s+-]+\)|[([]\s*[a-zA-Z0-9+-]+\s*[;,]\s*[a-zA-Z0-9+-]+\s*[)\]][,.;:]?)$/.test(
                combined1D
              )
            const isStandaloneEqBetween1D =
              cleanTxt === '=' &&
              prevProse &&
              i > 0 &&
              is1DInlineToken(wordTokens[i - 1]) &&
              i + 1 < wordTokens.length &&
              is1DInlineToken(wordTokens[i + 1])
            const nextAfterSeqProse =
              seqEnd + 1 < wordTokens.length && !wordTokens[seqEnd + 1].isMath
            const adjSymMath =
              (i > 0 &&
                wordTokens[i - 1].isMath &&
                (hasNonGreekSymbol(wordTokens[i - 1]) || wordTokens[i - 1].hasAdjSubSup)) ||
              (seqEnd + 1 < wordTokens.length &&
                wordTokens[seqEnd + 1].isMath &&
                (hasNonGreekSymbol(wordTokens[seqEnd + 1]) ||
                  wordTokens[seqEnd + 1].hasAdjSubSup ||
                  EXPLICIT_MATH_SYMBOL_RE.test(wordTokens[seqEnd + 1].text)))

            if (
              !adjSymMath &&
              (isStandaloneEqBetween1D ||
                (seqEnd === i &&
                  !/^[a-zA-Z]$/.test(cleanTxt) &&
                  !/[=<>+-]$/.test(cleanTxt) &&
                  !/^[a-z]{2,3}$/.test(cleanTxt) &&
                  ((prevProse && (nextAfterSeqProse || proseWordCount >= 2)) ||
                    (i === 0 && nextAfterSeqProse && proseWordCount >= 3))) ||
                (is1DEquationOrInterval &&
                  ((prevProse && (nextAfterSeqProse || proseWordCount >= 3)) ||
                    (i === 0 && nextAfterSeqProse && proseWordCount >= 3))))
            ) {
              for (let mIdx = i; mIdx <= seqEnd; mIdx++) {
                wordTokens[mIdx].isMath = false
              }
              i = seqEnd
              continue
            }
          }

          // 5. Single-letter 1D ASCII tokens (a, b, c, d, n, r, R, S, etc.), primed/degree 1D variables (d', n°), or 1D Greek letters (α, β, γ) without 2D sub/superscripts
          if (/^(?:[a-zA-Z]['’′°]?|[α-ωΑ-Ω])$/.test(cleanTxt)) {
            if (wt.hasAdjSubSup) continue
            const isGreekOrPrime = /^[α-ωΑ-Ω]$/.test(cleanTxt) || /['’′°]$/.test(cleanTxt)
            if (hasNonGreekSymbol(wt)) continue

            const prevProse =
              i > 0 &&
              !wordTokens[i - 1].isMath &&
              (isGreekOrPrime || wt.serif === wordTokens[i - 1].serif)
            const nextProse =
              i < wordTokens.length - 1 &&
              !wordTokens[i + 1].isMath &&
              (isGreekOrPrime || wt.serif === wordTokens[i + 1].serif)
            const adjSymMath =
              (i > 0 &&
                wordTokens[i - 1].isMath &&
                (hasNonGreekSymbol(wordTokens[i - 1]) ||
                  wordTokens[i - 1].hasAdjSubSup ||
                  EXPLICIT_MATH_SYMBOL_RE.test(wordTokens[i - 1].text))) ||
              (i < wordTokens.length - 1 &&
                wordTokens[i + 1].isMath &&
                (hasNonGreekSymbol(wordTokens[i + 1]) ||
                  wordTokens[i + 1].hasAdjSubSup ||
                  EXPLICIT_MATH_SYMBOL_RE.test(wordTokens[i + 1].text)))
            const startsParentheticalBeforeProse =
              wt.text.trim().startsWith('(') && nextProse
            if (startsParentheticalBeforeProse) {
              wt.isMath = false
              continue
            }
            if (adjSymMath) continue

            // Check if part of a 1D variable/Greek list before a prose clause (e.g. "a, b, c ..." or "α, β, γ là các góc...")
            let is1DVarListBeforeProse = false
            let kIdx = i + 1
            while (
              kIdx < wordTokens.length &&
              /^[(),.;:\s]*(?:[a-zA-Z]['’′°]?|[α-ωΑ-Ω])[(),.;:\s]*$/.test(
                wordTokens[kIdx].text.trim()
              ) &&
              !wordTokens[kIdx].hasAdjSubSup &&
              !hasNonGreekSymbol(wordTokens[kIdx])
            ) {
              kIdx++
            }
            if (kIdx < wordTokens.length && !wordTokens[kIdx].isMath && proseWordCount >= 1) {
              is1DVarListBeforeProse = true
            }

            if (
              is1DVarListBeforeProse ||
              prevProse ||
              (i === 0 && nextProse && (!wt.italic || isGreekOrPrime))
            ) {
              wt.isMath = false
            }
            continue
          }
        }
      }

      // Now partition wordTokens into ProseSpans vs MathObstacles / LinkObstacles
      let idx = 0
      while (idx < wordTokens.length) {
        if (wordTokens[idx].isMath) {
          const mStart = idx
          while (idx < wordTokens.length && wordTokens[idx].isMath) idx++
          const mSlice = wordTokens.slice(mStart, idx)
          const mx0 = Math.min(...mSlice.map((w) => w.x0))
          const my0 = Math.min(...mSlice.map((w) => w.y0))
          const mx1 = Math.max(...mSlice.map((w) => w.x1))
          const my1 = Math.max(...mSlice.map((w) => w.y1))
          const mText = mSlice.map((w) => w.text).join(' ')
          const mBox: BBox = { x: mx0, y: my0, w: mx1 - mx0, h: my1 - my0 }
          mathObstacles.push({
            bbox: mBox,
            text: mText,
          })

          if (mSlice.some((w) => w.isHyperlink)) {
            const matchedNative = nativeLinks.find((nl) => boxesOverlap(mBox, nl.bbox, 2))
            let resolvedUri = matchedNative?.uri || ''
            if (!resolvedUri && /^https?:\/\//i.test(mText.trim())) {
              resolvedUri = mText.trim()
            } else if (!resolvedUri && lastBoldProperName) {
              resolvedUri = `https://en.wikipedia.org/wiki/Special:Search?search=${encodeURIComponent(
                lastBoldProperName
              )}`
            }
            if (resolvedUri) {
              linkObstacles.push({
                bbox: mBox,
                text: mText,
                uri: resolvedUri,
              })
            }
          }
        } else {
          const pStart = idx
          while (idx < wordTokens.length && !wordTokens[idx].isMath) idx++
          const pSlice = wordTokens.slice(pStart, idx)
          const pText = pSlice.map((w) => w.text).join(' ').trim()
          const px0 = Math.min(...pSlice.map((w) => w.x0))
          const py0 = Math.min(...pSlice.map((w) => w.y0))
          const px1 = Math.max(...pSlice.map((w) => w.x1))
          const py1 = Math.max(...pSlice.map((w) => w.y1))

          if (isTranslatableProseText(pText)) {
            const first = pSlice[0]
            const boldCharCount = pSlice.reduce((acc, w) => acc + (w.bold ? w.text.length : 0), 0)
            const totalCharCount = Math.max(
              1,
              pSlice.reduce((acc, w) => acc + w.text.length, 0)
            )
            const isMajorityBold = boldCharCount > totalCharCount * 0.55

            proseSpans.push({
              text: pText,
              x0: px0,
              y0: py0,
              x1: px1,
              y1: py1,
              oy: first.oy,
              size: first.size,
              bold: isMajorityBold,
              italic: pSlice.every((w) => w.italic),
              serif: first.serif,
              mono: first.mono,
              color: first.color,
              bgColor: sampleBackgroundRGB(pixSamples, pixW, pixH, nComp, px0, py0, px1, py1),
              leftClearanceX: px0,
              rightClearanceX: pageW - Math.min(42, pageW * 0.06),
              isToc: false,
            })
          } else {
            mathObstacles.push({
              bbox: { x: px0, y: py0, w: px1 - px0, h: py1 - py0 },
              text: pText,
            })
          }
        }
      }
    }
  }

  // Compute exact horizontal left & right margin clearances for each proseSpan
  const marginPad = Math.min(42, Math.max(22, pageW * 0.058))
  const bodyLeftCandidates = proseSpans
    .filter((s) => !s.isToc && s.x1 - s.x0 > pageW * 0.18)
    .map((s) => s.x0)
    .sort((a, b) => a - b)
  const bodyLeftMarginX = bodyLeftCandidates.length > 0 ? bodyLeftCandidates[0] : marginPad

  for (let i = 0; i < proseSpans.length; i++) {
    const sp = proseSpans[i]
    if (sp.isToc) {
      sp.leftClearanceX = sp.x0
      sp.rightClearanceX = sp.x1
      continue
    }
    let maxRight = Math.max(sp.x1, pageW - marginPad)
    // Never shift a line that starts at the left body margin into the empty left page margin
    let minLeft =
      sp.x0 <= bodyLeftMarginX + 14
        ? sp.x0
        : Math.min(sp.x0, Math.max(bodyLeftMarginX, sp.x0 - 36))

    // 1. Check math obstacles on the same vertical band
    for (const mo of mathObstacles) {
      const oyOverlap = Math.min(sp.y1, mo.bbox.y + mo.bbox.h) - Math.max(sp.y0, mo.bbox.y)
      if (oyOverlap > 1.2) {
        if (mo.bbox.x >= sp.x0 + 2 && mo.bbox.x + mo.bbox.w > sp.x1 - 2) {
          maxRight = Math.min(maxRight, Math.max(sp.x1, mo.bbox.x - 0.8))
        }
        if (mo.bbox.x + mo.bbox.w <= sp.x0 + 2) {
          minLeft = Math.max(minLeft, Math.min(sp.x0, mo.bbox.x + mo.bbox.w + 0.8))
        }
      }
    }
    // 2. Check other proseSpans on the same vertical band
    for (let j = 0; j < proseSpans.length; j++) {
      if (i === j) continue
      const other = proseSpans[j]
      const oyOverlap = Math.min(sp.y1, other.y1) - Math.max(sp.y0, other.y0)
      if (oyOverlap > 1.2) {
        if (other.x0 >= sp.x0 + 2 && other.x1 > sp.x1 - 2) {
          maxRight = Math.min(maxRight, Math.max(sp.x1, other.x0 - 2.5))
        }
        if (other.x1 <= sp.x0 + 2) {
          minLeft = Math.max(minLeft, Math.min(sp.x0, other.x1 + 2.5))
        }
      }
    }
    // 3. Scan rendered page pixmap to the right of sp.x1 and left of sp.x0 to detect geometric diagrams, figures, curly braces, or table borders
    const scanStartX = Math.min(pixW - 1, Math.max(0, Math.ceil(sp.x1 + 5)))
    const scanEndX = Math.min(pixW - 1, Math.floor(maxRight))
    const scanY0 = Math.max(0, Math.floor(sp.y0 + 1))
    const scanY1 = Math.min(pixH - 1, Math.ceil(sp.y1 - 1))
    if (scanEndX > scanStartX && scanY1 >= scanY0) {
      for (let px = scanStartX; px <= scanEndX; px += 2) {
        let hitInk = false
        for (let py = scanY0; py <= scanY1; py += 2) {
          const pIdx = (py * pixW + px) * nComp
          const rDiff = Math.abs(pixSamples[pIdx] / 255 - sp.bgColor[0])
          const gDiff = Math.abs(pixSamples[pIdx + 1] / 255 - sp.bgColor[1])
          const bDiff = Math.abs(pixSamples[pIdx + 2] / 255 - sp.bgColor[2])
          if (rDiff + gDiff + bDiff > 0.28) {
            hitInk = true
            break
          }
        }
        if (hitInk) {
          maxRight = Math.min(maxRight, Math.max(sp.x1, px - 2))
          break
        }
      }
    }

    const leftStartX = Math.min(pixW - 1, Math.max(0, Math.floor(sp.x0 - 4)))
    const leftEndX = Math.max(0, Math.ceil(minLeft))
    if (leftStartX > leftEndX && scanY1 >= scanY0) {
      for (let px = leftStartX; px >= leftEndX; px -= 2) {
        let hitInk = false
        for (let py = scanY0; py <= scanY1; py += 2) {
          const pIdx = (py * pixW + px) * nComp
          const rDiff = Math.abs(pixSamples[pIdx] / 255 - sp.bgColor[0])
          const gDiff = Math.abs(pixSamples[pIdx + 1] / 255 - sp.bgColor[1])
          const bDiff = Math.abs(pixSamples[pIdx + 2] / 255 - sp.bgColor[2])
          if (rDiff + gDiff + bDiff > 0.28) {
            hitInk = true
            break
          }
        }
        if (hitInk) {
          minLeft = Math.max(minLeft, Math.min(sp.x0, px + 2))
          break
        }
      }
    }

    sp.rightClearanceX = Math.max(sp.x1, maxRight)
    sp.leftClearanceX = Math.min(sp.x0, minLeft)
  }

  // Group consecutive ProseSpans into multi-line ProseGroups (supports first-line indents, 2-column & 3-column layouts, and avoids merging across horizontal table borders)
  proseSpans.sort((a, b) => (Math.abs(a.y0 - b.y0) <= 3 ? a.x0 - b.x0 : a.y0 - b.y0))
  const proseGroups: ProseGroup[] = []

  for (const sp of proseSpans) {
    // Search backwards for the most recent candidate group in the same horizontal column band
    let targetGroup: ProseGroup | undefined
    for (let gIdx = proseGroups.length - 1; gIdx >= 0; gIdx--) {
      const cand = proseGroups[gIdx]
      const lastSpan = cand.spans[cand.spans.length - 1]
      if (!lastSpan) continue
      if (sp.y0 - lastSpan.y1 > Math.max(12, lastSpan.size * 1.1)) break
      if (Math.abs(sp.x0 - cand.x0) <= 46) {
        targetGroup = cand
        break
      }
    }

    const lastSpan = targetGroup?.spans[targetGroup.spans.length - 1]
    let canMerge = false

    // Geometric & structural rule for bold spans: only merge consecutive bold lines when they form
    // a continuous full-width bold paragraph (same left margin, first line spans >=45% of page width,
    // not ALL-CAPS heading, and not a standalone numbered heading or figure/table caption ending in a number).
    const sameBoldAndStyle =
      targetGroup &&
      lastSpan &&
      sp.bold === targetGroup.bold &&
      sp.italic === targetGroup.italic &&
      (!sp.bold ||
        (!/^[\p{Lu}0-9\s.-]+$/u.test(lastSpan.text || '') &&
          Math.abs(sp.x0 - lastSpan.x0) <= 6 &&
          lastSpan.x1 - lastSpan.x0 >= pageW * 0.45 &&
          !/^(?:[IVXLC]+\.|\d+\.|\p{Lu}\.|[a-d]\))/iu.test(sp.text.trim()) &&
          !/\b\d+\s*$/.test(sp.text.trim())))

    if (
      targetGroup &&
      lastSpan &&
      !sp.isToc &&
      targetGroup.kind !== 'toc' &&
      sameBoldAndStyle &&
      Math.hypot(
        sp.color[0] - targetGroup.color[0],
        sp.color[1] - targetGroup.color[1],
        sp.color[2] - targetGroup.color[2]
      ) <= 0.15 &&
      Math.hypot(
        sp.bgColor[0] - targetGroup.bgColor[0],
        sp.bgColor[1] - targetGroup.bgColor[1],
        sp.bgColor[2] - targetGroup.bgColor[2]
      ) <= 0.12 &&
      Math.abs(sp.size - targetGroup.size) <= 1.0 &&
      sp.y0 - lastSpan.y1 >= -2.5 &&
      sp.y0 - lastSpan.y1 <= Math.max(8.5, lastSpan.size * 0.85) &&
      Math.abs(sp.x0 - targetGroup.x0) <= 46 &&
      (Math.abs(sp.rightClearanceX - targetGroup.rightClearanceX) <= 45 ||
        (sp.rightClearanceX < targetGroup.rightClearanceX &&
          (sp.rightClearanceX - sp.x0 >= pageW * 0.45 ||
            (Math.abs(sp.x0 - targetGroup.x0) <= 18 &&
              lastSpan.x1 - lastSpan.x0 >= pageW * 0.42 &&
              sp.rightClearanceX - sp.x0 >= 40)))) &&
      !(lastSpan.rightClearanceX < pageW * 0.65 && lastSpan.x1 - lastSpan.x0 < pageW * 0.35) &&
      lastSpan.x1 - lastSpan.x0 >=
        Math.max(
          pageW * 0.24,
          (Math.min(lastSpan.rightClearanceX, sp.rightClearanceX) - targetGroup.x0) * 0.56
        ) &&
      sp.x1 <= lastSpan.x1 + 28 &&
      !/:\s*$/.test(lastSpan.text) &&
      !/^(?:\[\d+\]|\d+\.|[IVXLC]+\.|[a-d]\)|[•–-])\s/i.test(sp.text.trim())
    ) {
      // Check per-line and inter-line vertical gap for math obstacles.
      // Line 0 is allowed to have leading math to the left of spans[0].x0 (handled via firstLineIndent),
      // whereas any subsequent merged line `sp` must be unobstructed from `Math.min(targetGroup.x0, sp.x0)` to `sp.x1`.
      // Furthermore, in multi-column symbol/formula tables, if `lastSpan` and `sp` each have their own
      // row-aligned math obstacle in an adjacent left or right column, they are separate table rows.
      const mergedLeftX = Math.min(targetGroup.x0, sp.x0)
      const gapBandBBox: BBox = {
        x: Math.max(lastSpan.x0, sp.x0),
        y: lastSpan.y0,
        w: Math.max(8, Math.min(lastSpan.x1, sp.x1) - Math.max(lastSpan.x0, sp.x0)),
        h: sp.y1 - lastSpan.y0,
      }
      const spBandBBox: BBox = {
        x: mergedLeftX,
        y: sp.y0,
        w: sp.x1 - mergedLeftX,
        h: sp.y1 - sp.y0,
      }
      const hasNewLeftSymbolRow =
        sp.x0 >= Math.min(bodyLeftMarginX, marginPad) + 25 &&
        mathObstacles.some((mo) => {
          const vOverlap = Math.min(sp.y1, mo.bbox.y + mo.bbox.h) - Math.max(sp.y0, mo.bbox.y)
          return vOverlap > 1.5 && mo.bbox.x + mo.bbox.w <= sp.x0 + 4 && mo.bbox.y >= lastSpan.y0 - 2
        })
      const lastCenterY = (lastSpan.y0 + lastSpan.y1) / 2
      const spCenterY = (sp.y0 + sp.y1) / 2
      const hasDistinctRightFormulaRows =
        sp.rightClearanceX < pageW - marginPad - 35 &&
        mathObstacles.some(
          (mo1) =>
            mo1.bbox.x >= lastSpan.x1 - 2 &&
            mo1.bbox.h <= lastSpan.size * 1.8 &&
            Math.abs(mo1.bbox.y + mo1.bbox.h / 2 - lastCenterY) <= lastSpan.size * 0.65 &&
            mathObstacles.some(
              (mo2) =>
                mo2 !== mo1 &&
                mo2.bbox.x >= sp.x1 - 2 &&
                mo2.bbox.h <= sp.size * 1.8 &&
                Math.abs(mo2.bbox.y + mo2.bbox.h / 2 - spCenterY) <= sp.size * 0.65 &&
                Math.abs(mo1.bbox.x - mo2.bbox.x) <= 30
            )
        )
      // Do not vertically merge across lines that are split horizontally into multiple prose fragments
      // (merging left fragment of line 1 with line 2 would skip the right fragment of line 1 and scramble reading order)
      const lastRowHasSiblingProse = proseSpans.some(
        (other) =>
          other !== lastSpan &&
          Math.abs(other.oy - lastSpan.oy) <= 2.5 &&
          Math.abs(other.x0 - lastSpan.x0) < pageW * 0.65
      )
      const spRowHasSiblingProse = proseSpans.some(
        (other) =>
          other !== sp &&
          Math.abs(other.oy - sp.oy) <= 2.5 &&
          Math.abs(other.x0 - sp.x0) < pageW * 0.65
      )
      const hitsMath =
        lastRowHasSiblingProse ||
        spRowHasSiblingProse ||
        hasNewLeftSymbolRow ||
        hasDistinctRightFormulaRows ||
        mathObstacles.some(
          (mo) => boxesOverlap(gapBandBBox, mo.bbox, -1.0) || boxesOverlap(spBandBBox, mo.bbox, -1.0)
        )

      // Also check if there is a horizontal ruled table border line drawn between lastSpan.y1 and sp.y0
      let hitsHorizontalBorder = false
      const gapY0 = Math.max(0, Math.floor(lastSpan.y1 + 0.5))
      const gapY1 = Math.min(pixH - 1, Math.ceil(sp.y0 - 0.5))
      const checkX0 = Math.max(0, Math.floor(Math.min(lastSpan.x0, sp.x0)))
      const checkX1 = Math.min(pixW - 1, Math.ceil(Math.max(lastSpan.x1, sp.x1)))
      if (gapY1 >= gapY0 && checkX1 - checkX0 >= 24) {
        for (let py = gapY0; py <= gapY1; py++) {
          let inkCount = 0
          let totalSamples = 0
          for (let px = checkX0; px <= checkX1; px += 4) {
            totalSamples++
            const pIdx = (py * pixW + px) * nComp
            const diff =
              Math.abs(pixSamples[pIdx] / 255 - sp.bgColor[0]) +
              Math.abs(pixSamples[pIdx + 1] / 255 - sp.bgColor[1]) +
              Math.abs(pixSamples[pIdx + 2] / 255 - sp.bgColor[2])
            if (diff > 0.15) inkCount++
          }
          if (totalSamples > 0 && inkCount / totalSamples >= 0.75) {
            hitsHorizontalBorder = true
            break
          }
        }
      }

      if (!hitsMath && !hitsHorizontalBorder) {
        canMerge = true
      }
    }

    if (canMerge && targetGroup) {
      targetGroup.spans.push(sp)
      targetGroup.x0 = Math.min(targetGroup.x0, sp.x0)
      targetGroup.y0 = Math.min(targetGroup.y0, sp.y0)
      targetGroup.x1 = Math.max(targetGroup.x1, sp.x1)
      targetGroup.y1 = Math.max(targetGroup.y1, sp.y1)
      targetGroup.leftClearanceX = Math.max(targetGroup.leftClearanceX, sp.leftClearanceX)
      targetGroup.rightClearanceX = Math.min(targetGroup.rightClearanceX, sp.rightClearanceX)
      let joined = targetGroup.spans[0].text
      for (let sIdx = 1; sIdx < targetGroup.spans.length; sIdx++) {
        const prevTxt = targetGroup.spans[sIdx - 1].text
        const curTxt = targetGroup.spans[sIdx].text
        const prevLast = prevTxt[prevTxt.length - 1] || ''
        const curFirst = curTxt[0] || ''
        const sep = CJK_CHAR_RE.test(prevLast) && CJK_CHAR_RE.test(curFirst) ? '' : ' '
        joined += sep + curTxt
      }
      targetGroup.sourceText = joined
    } else {
      const isHeading =
        sp.bold ||
        sp.size >= 13.5 ||
        /^(?:[IVXLC]+\.|\d+\.)\s+[\p{Lu}\p{Lo}]/u.test(sp.text)
      proseGroups.push({
        id: `p${pageIndex + 1}_b${proseGroups.length + 1}`,
        kind: sp.isToc ? 'toc' : isHeading ? 'heading' : 'prose',
        spans: [sp],
        x0: sp.x0,
        y0: sp.y0,
        x1: sp.x1,
        y1: sp.y1,
        leftClearanceX: sp.leftClearanceX,
        rightClearanceX: sp.rightClearanceX,
        sourceText: sp.isToc ? sp.tocTitle || sp.text : sp.text,
        size: sp.size,
        bold: sp.bold,
        italic: sp.italic,
        serif: sp.serif,
        mono: sp.mono,
        color: sp.color,
        bgColor: sp.bgColor,
      })
    }
  }

  // Attach native hyperlink URIs (both internal #page=N GoTo links and external URLs) to overlapping ProseGroups
  for (const group of proseGroups) {
    const gBox: BBox = {
      x: group.x0,
      y: group.y0,
      w: group.x1 - group.x0,
      h: group.y1 - group.y0,
    }
    const matchedLink = nativeLinks.find((nl) => boxesOverlap(gBox, nl.bbox, 2))
    if (matchedLink) {
      group.uri = matchedLink.uri
    } else if (group.kind === 'toc' && group.spans[0]?.tocPageNum) {
      const parsedPage = parseInt(group.spans[0].tocPageNum, 10)
      if (!Number.isNaN(parsedPage) && parsedPage >= 1) {
        group.uri = `#page=${parsedPage}`
      }
    }
  }

  // Also include any standalone nativeLinks that did not overlap a ProseGroup or existing linkObstacle
  for (const nl of nativeLinks) {
    const onGroup = proseGroups.some((g) =>
      boxesOverlap({ x: g.x0, y: g.y0, w: g.x1 - g.x0, h: g.y1 - g.y0 }, nl.bbox, 2)
    )
    const onLinkObs = linkObstacles.some((lo) => boxesOverlap(lo.bbox, nl.bbox, 2))
    if (!onGroup && !onLinkObs) {
      linkObstacles.push({
        bbox: nl.bbox,
        text: nl.uri,
        uri: nl.uri,
      })
    }
  }

  return { pageW, pageH, proseGroups, mathObstacles, linkObstacles }
}

const CJK_CHAR_RE = /[\u2E80-\u9FFF\uF900-\uFAFF\u3040-\u30FF\uAC00-\uD7AF\uFF00-\uFFEF]/u

/**
 * Tokenizes multilingual text (both space-delimited scripts and CJK character streams) for line wrapping.
 */
function tokenizeMultilingualWrap(text: string): Array<{ token: string; spaceBefore: boolean }> {
  const units: Array<{ token: string; spaceBefore: boolean }> = []
  const rawChunks = text.trim().split(/\s+/).filter(Boolean)

  for (let cIdx = 0; cIdx < rawChunks.length; cIdx++) {
    const chunk = rawChunks[cIdx]
    if (!CJK_CHAR_RE.test(chunk)) {
      units.push({ token: chunk, spaceBefore: cIdx > 0 })
      continue
    }
    // Split chunk into individual CJK characters (with attached closing punctuation) or non-CJK runs
    const subRe =
      /([\u2E80-\u9FFF\uF900-\uFAFF\u3040-\u30FF\uAC00-\uD7AF][，。、：；！？）》】」』”’.,:;!?)]*|[^\u2E80-\u9FFF\uF900-\uFAFF\u3040-\u30FF\uAC00-\uD7AF]+)/gu
    const parts = chunk.match(subRe) || [chunk]
    for (let pIdx = 0; pIdx < parts.length; pIdx++) {
      units.push({
        token: parts[pIdx],
        spaceBefore: cIdx > 0 && pIdx === 0 && !CJK_CHAR_RE.test(parts[0]),
      })
    }
  }
  return units
}

/**
 * Word-wraps multilingual and CJK text to fit within `maxWidth` (with optional first-line indent and last-line right obstacle inset) at `fontSize`.
 */
function wrapTextToLines(
  text: string,
  font: PDFFont,
  fontSize: number,
  maxWidth: number,
  firstLineIndent = 0,
  lastLineLimitIndex = -1,
  lastLineMaxWidth = maxWidth
): string[] {
  const units = tokenizeMultilingualWrap(text)
  if (units.length === 0) return []
  const lines: string[] = []
  let current = units[0].token

  for (let i = 1; i < units.length; i++) {
    let lineLimit = maxWidth
    if (lines.length === 0) {
      lineLimit = Math.max(36, maxWidth - firstLineIndent)
    } else if (lastLineLimitIndex > 0 && lines.length >= lastLineLimitIndex) {
      lineLimit = Math.max(36, lastLineMaxWidth)
    }
    const sep = units[i].spaceBefore ? ' ' : ''
    const candidate = `${current}${sep}${units[i].token}`
    const w = safeWidthOfText(font, candidate, fontSize)
    if (w <= lineLimit) {
      current = candidate
    } else {
      lines.push(current)
      current = units[i].token
    }
  }
  if (current) lines.push(current)
  return lines
}

function drawTextWithHorizScale(
  pdfPage: PDFPage,
  text: string,
  opts: { x: number; y: number; size: number; font: PDFFont; color: any; horizScalePct?: number }
) {
  const tz = opts.horizScalePct != null ? Math.round(opts.horizScalePct * 10) / 10 : 100
  try {
    if (tz < 99.5) {
      pdfPage.pushOperators(
        PDFOperator.of(PDFOperatorNames.SetTextHorizontalScaling, [PDFNumber.of(tz)])
      )
    }
    pdfPage.drawText(text, {
      x: opts.x,
      y: opts.y,
      size: opts.size,
      font: opts.font,
      color: opts.color,
    })
  } catch {
    // Ignore encoding edge cases
  } finally {
    if (tz < 99.5) {
      try {
        pdfPage.pushOperators(
          PDFOperator.of(PDFOperatorNames.SetTextHorizontalScaling, [PDFNumber.of(100)])
        )
      } catch {}
    }
  }
}

function safeWidthOfText(font: PDFFont, text: string, size: number): number {
  try {
    return font.widthOfTextAtSize(text, size)
  } catch {
    const cjkCount = (text.match(/[\u2E80-\u9FFF\uF900-\uFAFF\u3040-\u30FF\uAC00-\uD7AF]/gu) || []).length
    const otherCount = text.length - cjkCount
    return cjkCount * size * 0.98 + otherCount * size * 0.52
  }
}

export interface FontBundle {
  serifRegular: PDFFont
  serifBold: PDFFont
  serifItalic: PDFFont
  serifBoldItalic: PDFFont
  sansRegular: PDFFont
  sansBold: PDFFont
  sansItalic: PDFFont
  monoRegular: PDFFont
  unicodeSansRegular?: PDFFont
  unicodeSansBold?: PDFFont
  cjkRegular?: PDFFont
}

let cachedFontFiles: Record<string, Buffer> | null = null
let cachedCjkFontBuffer: Buffer | null = null

function loadSystemFontBuffers(): Record<string, Buffer> {
  if (cachedFontFiles) return cachedFontFiles
  const dejavuDir = 'node_modules/dejavu-fonts-ttf/ttf'
  const base = '/usr/share/fonts/truetype/liberation'
  if (fs.existsSync(`${dejavuDir}/DejaVuSans.ttf`)) {
    cachedFontFiles = {
      serifRegular: fs.readFileSync(`${dejavuDir}/DejaVuSerif.ttf`),
      serifBold: fs.readFileSync(`${dejavuDir}/DejaVuSerif-Bold.ttf`),
      serifItalic: fs.readFileSync(`${dejavuDir}/DejaVuSerif-Italic.ttf`),
      serifBoldItalic: fs.readFileSync(`${dejavuDir}/DejaVuSerif-BoldItalic.ttf`),
      sansRegular: fs.readFileSync(`${dejavuDir}/DejaVuSans.ttf`),
      sansBold: fs.readFileSync(`${dejavuDir}/DejaVuSans-Bold.ttf`),
      sansItalic: fs.readFileSync(`${dejavuDir}/DejaVuSans-Oblique.ttf`),
      monoRegular: fs.readFileSync(`${dejavuDir}/DejaVuSansMono.ttf`),
      unicodeSansRegular: fs.readFileSync(`${dejavuDir}/DejaVuSans.ttf`),
      unicodeSansBold: fs.readFileSync(`${dejavuDir}/DejaVuSans-Bold.ttf`),
    }
    return cachedFontFiles
  }
  if (fs.existsSync(`${base}/LiberationSerif-Regular.ttf`)) {
    cachedFontFiles = {
      serifRegular: fs.readFileSync(`${base}/LiberationSerif-Regular.ttf`),
      serifBold: fs.readFileSync(`${base}/LiberationSerif-Bold.ttf`),
      serifItalic: fs.readFileSync(`${base}/LiberationSerif-Italic.ttf`),
      serifBoldItalic: fs.readFileSync(`${base}/LiberationSerif-BoldItalic.ttf`),
      sansRegular: fs.readFileSync(`${base}/LiberationSans-Regular.ttf`),
      sansBold: fs.readFileSync(`${base}/LiberationSans-Bold.ttf`),
      sansItalic: fs.readFileSync(`${base}/LiberationSans-Italic.ttf`),
      monoRegular: fs.readFileSync(`${base}/LiberationMono-Regular.ttf`),
    }
    return cachedFontFiles
  }
  throw new Error('No system TrueType fonts found')
}

async function getCjkFontBuffer(): Promise<Buffer> {
  if (cachedCjkFontBuffer) return cachedCjkFontBuffer
  const mupdf = await getMupdf()
  const mdoc = new mupdf.PDFDocument()
  const f = new mupdf.Font('zh-Hans')
  const fontObj = mdoc.addFont(f)
  const ff2 = fontObj.get('DescendantFonts').get(0).get('FontDescriptor').get('FontFile2')
  cachedCjkFontBuffer = Buffer.from(ff2.readStream().asUint8Array())
  return cachedCjkFontBuffer
}

export async function embedFontBundle(pdfDoc: PDFDocument, targetLang = 'en'): Promise<FontBundle> {
  pdfDoc.registerFontkit(fontkit)
  const bufs = loadSystemFontBuffers()
  const [
    serifRegular,
    serifBold,
    serifItalic,
    serifBoldItalic,
    sansRegular,
    sansBold,
    sansItalic,
    monoRegular,
  ] = await Promise.all([
    pdfDoc.embedFont(bufs.serifRegular),
    pdfDoc.embedFont(bufs.serifBold),
    pdfDoc.embedFont(bufs.serifItalic),
    pdfDoc.embedFont(bufs.serifBoldItalic),
    pdfDoc.embedFont(bufs.sansRegular),
    pdfDoc.embedFont(bufs.sansBold),
    pdfDoc.embedFont(bufs.sansItalic),
    pdfDoc.embedFont(bufs.monoRegular),
  ])

  let unicodeSansRegular: PDFFont | undefined
  let unicodeSansBold: PDFFont | undefined
  if (bufs.unicodeSansRegular && bufs.unicodeSansBold) {
    ;[unicodeSansRegular, unicodeSansBold] = await Promise.all([
      pdfDoc.embedFont(bufs.unicodeSansRegular),
      pdfDoc.embedFont(bufs.unicodeSansBold),
    ])
  }

  let cjkRegular: PDFFont | undefined
  const normTarget = normalizeLangCode(targetLang, 'en')
  if (/^(?:zh|ja|ko)/i.test(normTarget)) {
    const cjkBuf = await getCjkFontBuffer()
    cjkRegular = await pdfDoc.embedFont(cjkBuf)
  }

  return {
    serifRegular,
    serifBold,
    serifItalic,
    serifBoldItalic,
    sansRegular,
    sansBold,
    sansItalic,
    monoRegular,
    unicodeSansRegular,
    unicodeSansBold,
    cjkRegular,
  }
}

function canFontEncodeText(font: PDFFont, text: string): boolean {
  try {
    font.widthOfTextAtSize(text, 10)
    return true
  } catch {
    return false
  }
}

async function pickFontForText(
  pdfDoc: PDFDocument,
  bundle: FontBundle,
  group: ProseGroup,
  text: string
): Promise<PDFFont> {
  const normLang = normalizeLangCode
  void normLang
  if (CJK_CHAR_RE.test(text)) {
    if (!bundle.cjkRegular) {
      const cjkBuf = await getCjkFontBuffer()
      bundle.cjkRegular = await pdfDoc.embedFont(cjkBuf)
    }
    return bundle.cjkRegular
  }
  // Hebrew / Arabic scripts are supported in DejaVuSans
  if (/[\u0590-\u06FF]/u.test(text)) {
    if (bundle.unicodeSansRegular && bundle.unicodeSansBold) {
      return group.bold ? bundle.unicodeSansBold : bundle.unicodeSansRegular
    }
    return group.bold ? bundle.sansBold : bundle.sansRegular
  }

  let candidate: PDFFont
  if (group.mono) {
    candidate = bundle.monoRegular
  } else if (!group.serif) {
    if (group.bold) candidate = bundle.sansBold
    else if (group.italic) candidate = bundle.sansItalic
    else candidate = bundle.sansRegular
  } else {
    if (group.bold && group.italic) candidate = bundle.serifBoldItalic
    else if (group.bold) candidate = bundle.serifBold
    else if (group.italic) candidate = bundle.serifItalic
    else candidate = bundle.serifRegular
  }

  if (canFontEncodeText(candidate, text)) {
    return candidate
  }
  // Fallback to LiberationSans
  const sansFallback = group.bold ? bundle.sansBold : bundle.sansRegular
  if (canFontEncodeText(sansFallback, text)) {
    return sansFallback
  }
  // Fallback to DejaVuSans (which has full mathematical operator & symbol coverage)
  if (bundle.unicodeSansRegular && bundle.unicodeSansBold) {
    const djvFallback = group.bold ? bundle.unicodeSansBold : bundle.unicodeSansRegular
    if (canFontEncodeText(djvFallback, text)) {
      return djvFallback
    }
  }
  // Final fallback to DroidSansFallback (full Unicode BMP coverage)
  if (!bundle.cjkRegular) {
    const cjkBuf = await getCjkFontBuffer()
    bundle.cjkRegular = await pdfDoc.embedFont(cjkBuf)
  }
  return bundle.cjkRegular
}

type ProseRedactionBox = {
  rx: number
  topY: number
  rw: number
  botY: number
  rh: number
  ry: number
  bgColor: [number, number, number]
}

/**
 * Builds obstacle-clipped redaction rectangles for every prose span that still needs
 * translation. Groups already written in the target language are left untouched.
 */
function buildProseRedactionBoxes(
  proseGroups: ReturnType<typeof analyzePdfPageLayout>['proseGroups'],
  mathObstacles: ReturnType<typeof analyzePdfPageLayout>['mathObstacles'],
  pageH: number,
  sourceLang: string,
  targetLang: string
): ProseRedactionBox[] {
  const boxes: ProseRedactionBox[] = []
  for (const group of proseGroups) {
    if (isAlreadyInTargetLanguage(group.sourceText, sourceLang, targetLang)) continue
    for (const sp of group.spans) {
      const hasExtendedDiacritics = MULTILINGUAL_SCRIPT_RE.test(sp.text)
      let padLeft = Math.max(1.5, sp.size * 0.1)
      let padRight = Math.max(1.5, sp.size * 0.1)
      let padTop = hasExtendedDiacritics ? Math.max(2.6, sp.size * 0.3) : Math.max(2.0, sp.size * 0.21)
      let padBottom = hasExtendedDiacritics ? Math.max(2.0, sp.size * 0.2) : Math.max(1.8, sp.size * 0.16)

      for (const mo of mathObstacles) {
        const horizOverlap =
          Math.min(sp.x1 + padRight, mo.bbox.x + mo.bbox.w) - Math.max(sp.x0 - padLeft, mo.bbox.x)
        if (horizOverlap > 1) {
          const moBottom = mo.bbox.y + mo.bbox.h
          if (moBottom <= sp.y0 + 1.5 && sp.y0 - moBottom < padTop) {
            padTop = Math.max(0, sp.y0 - moBottom - 0.3)
          }
          if (mo.bbox.y >= sp.y1 - 1.5 && mo.bbox.y - sp.y1 < padBottom) {
            padBottom = Math.max(0, mo.bbox.y - sp.y1 - 0.3)
          }
        }
        const vertOverlap =
          Math.min(sp.y1 + padBottom, mo.bbox.y + mo.bbox.h) - Math.max(sp.y0 - padTop, mo.bbox.y)
        if (vertOverlap > 1) {
          const moRight = mo.bbox.x + mo.bbox.w
          if (moRight <= sp.x0 + 1.5 && sp.x0 - moRight < padLeft) {
            padLeft = Math.max(0, sp.x0 - moRight - 0.4)
          }
          if (mo.bbox.x >= sp.x1 - 1.5 && mo.bbox.x - sp.x1 < padRight) {
            padRight = Math.max(0, mo.bbox.x - sp.x1 - 0.4)
          }
        }
      }

      const rx = Math.max(0, sp.x0 - padLeft)
      const rw = Math.max(2, sp.x1 - sp.x0 + padLeft + padRight)
      const topY = Math.max(0, sp.y0 - padTop)
      const botY = Math.min(pageH, sp.y1 + padBottom)
      const rh = Math.max(2, botY - topY)
      const ry = pageH - botY
      boxes.push({ rx, topY, rw, botY, rh, ry, bgColor: sp.bgColor })
    }
  }
  return boxes
}

/**
 * Physically redacts source prose glyphs from the ORIGINAL document with MuPDF's native
 * redaction pipeline (black_boxes=false, image_method=0, line_art_method=1, text_method=0)
 * on a private copy of the document, so the surviving page content (frozen math formulas,
 * form XObjects, decorations) stays fully self-consistent in MuPDF's own output file.
 *
 * Returns the redacted document bytes for pdf-lib to load, plus the 0-based page indices
 * whose redaction failed — those pages must fall back to paint-over rectangles during
 * typesetting (`paintOverProse`).
 */
export async function redactSourceProsePages(
  sourcePdfBytes: Buffer,
  pageIndices: number[],
  sourceLang: string,
  targetLang: string
): Promise<{ bytes: Buffer | null; failedPages: number[] }> {
  try {
    const mupdf = await getMupdf()
    const doc = mupdf.Document.openDocument(sourcePdfBytes, 'application/pdf')
    const pdf = doc.asPDF?.()
    if (!pdf) return { bytes: null, failedPages: [...pageIndices] }
    const failedPages: number[] = []
    let redactedAny = false
    for (const pageIndex of pageIndices) {
      try {
        const { proseGroups, mathObstacles, pageH } = analyzePdfPageLayout(mupdf, doc, pageIndex)
        const boxes = buildProseRedactionBoxes(
          proseGroups,
          mathObstacles,
          pageH,
          sourceLang,
          targetLang
        )
        if (boxes.length === 0) continue
        const page = pdf.loadPage(pageIndex)
        for (const rb of boxes) {
          const annot = page.createAnnotation('Redact')
          annot.setRect([rb.rx, rb.topY, rb.rx + rb.rw, rb.botY])
        }
        page.applyRedactions(false, 0, 1, 0)
        redactedAny = true
      } catch {
        failedPages.push(pageIndex)
      }
    }
    if (!redactedAny) return { bytes: null, failedPages: failedPages.length ? failedPages : [...pageIndices] }
    const out = pdf.saveToBuffer('compress')
    return { bytes: Buffer.from(out.asUint8Array()), failedPages }  } catch {
    return { bytes: null, failedPages: [...pageIndices] }
  }
}

/**
 * Translates and typesets a single page in-place on `pdfDoc`, preserving all vector equations and graphics.
 */
export async function translateAndTypesetPage(
  mupdfDoc: any,
  pdfDoc: PDFDocument,
  fontBundle: FontBundle,
  pageIndex: number,
  sourceLang: string,
  targetLang: string,
  options?: {
    provider?: string
    geminiKey?: string
    geminiModel?: string
    openaiKey?: string
    openaiEndpoint?: string
    openaiModel?: string
    minFontShrink?: number
    customGlossary?: string
    paintOverProse?: boolean
  }
): Promise<PageTranslationResult> {
  const mupdf = await getMupdf()
  const { pageW, pageH, proseGroups, mathObstacles, linkObstacles } = analyzePdfPageLayout(
    mupdf,
    mupdfDoc,
    pageIndex
  )
  const pdfPage = pdfDoc.getPage(pageIndex)
  const minShrink = Math.max(0.55, Math.min(0.95, options?.minFontShrink ?? 0.7))

  // Translate all proseGroups on this page in one fast batch
  const sourceTexts = proseGroups.map((g) => g.sourceText)
  const translatedTexts = await translateBatchWithFormulaShield(
    sourceTexts,
    sourceLang,
    targetLang,
    options
  )

  const blockMetas: LayoutBlockMeta[] = []
  const issues: PageTranslationResult['issues'] = []
  let scaledBlocksCount = 0

  const registerPdfLinkAnnotation = (bbox: BBox, uri: string) => {
    try {
      const rect = [
        bbox.x,
        pageH - (bbox.y + bbox.h),
        bbox.x + bbox.w,
        pageH - bbox.y,
      ]
      const pageMatch = uri.match(/^#page=(\d+)$/i)
      if (pageMatch) {
        const targetPageNum = parseInt(pageMatch[1], 10)
        if (targetPageNum >= 1 && targetPageNum <= pdfDoc.getPageCount()) {
          const targetPageRef = pdfDoc.getPage(targetPageNum - 1).ref
          const goToAnnot = pdfDoc.context.obj({
            Type: 'Annot',
            Subtype: 'Link',
            Rect: rect,
            Border: [0, 0, 0],
            Dest: [targetPageRef, PDFName.of('XYZ'), null, null, null],
          })
          pdfPage.node.addAnnot(pdfDoc.context.register(goToAnnot))
        }
      } else if (/^https?:\/\/|^mailto:/i.test(uri)) {
        const linkAnnot = pdfDoc.context.obj({
          Type: 'Annot',
          Subtype: 'Link',
          Rect: rect,
          Border: [0, 0, 0],
          A: {
            Type: 'Action',
            S: 'URI',
            URI: PDFString.of(uri),
          },
        })
        pdfPage.node.addAnnot(pdfDoc.context.register(linkAnnot))
      }
    } catch {
      // Ignore PDF annotation registration errors
    }
  }

  // Register clickable PDF /Link annotations & interactive UI link blocks for preserved standalone hyperlinks
  linkObstacles.forEach((lo, idx) => {
    registerPdfLinkAnnotation(lo.bbox, lo.uri)

    blockMetas.push({
      id: `p${pageIndex + 1}_lnk${idx + 1}`,
      kind: 'prose',
      bbox: lo.bbox,
      pageW,
      pageH,
      sourceText: lo.text,
      translatedText: `${lo.text} -> ${lo.uri}`,
      fontScale: 1.0,
      preserved: true,
      uri: lo.uri,
    })
  })

  // 1. Record preserved math clusters for layout inspector
  // Merge overlapping/nearby mathObstacles into visual formula clusters for clean UI display
  const mergedMath: BBox[] = []
  for (const mo of mathObstacles) {
    if (mo.bbox.w < 3 && mo.bbox.h < 3) continue
    if (linkObstacles.some((lo) => boxesOverlap(lo.bbox, mo.bbox, 1))) continue
    const existing = mergedMath.find((m) => boxesOverlap(m, mo.bbox, 6))
    if (existing) {
      const nx0 = Math.min(existing.x, mo.bbox.x)
      const ny0 = Math.min(existing.y, mo.bbox.y)
      const nx1 = Math.max(existing.x + existing.w, mo.bbox.x + mo.bbox.w)
      const ny1 = Math.max(existing.y + existing.h, mo.bbox.y + mo.bbox.h)
      existing.x = nx0
      existing.y = ny0
      existing.w = nx1 - nx0
      existing.h = ny1 - ny0
    } else {
      mergedMath.push({ ...mo.bbox })
    }
  }

  mergedMath.slice(0, 24).forEach((mb, idx) => {
    blockMetas.push({
      id: `p${pageIndex + 1}_m${idx + 1}`,
      kind: 'math',
      bbox: mb,
      pageW,
      pageH,
      sourceText: 'Vector Math Expression (Frozen IR)',
      translatedText: 'Preserved 100% in original PDF vector paths & glyphs',
      fontScale: 1.0,
      preserved: true,
    })
  })

  const preservedTargetGroups = proseGroups.map((g) =>
    isAlreadyInTargetLanguage(g.sourceText, sourceLang, targetLang)
  )

  // 2. Two-Pass Rendering Architecture (matching LayoutLingua renderer.py & PDFMathTranslate):
  // PASS 1 happened in `redactSourceProsePages`, which physically removed the source prose
  // glyphs from this page's content stream via MuPDF's native redaction pipeline while
  // keeping the page resources self-consistent (frozen math forms intact). When that
  // pre-pass could not run for this page (`paintOverProse`), fall back to painting
  // background-matched rectangles so the original glyphs stay covered instead.
  if (options?.paintOverProse) {
    const paintRects = buildProseRedactionBoxes(
      proseGroups,
      mathObstacles,
      pageH,
      sourceLang,
      targetLang
    )
    for (const rb of paintRects) {
      pdfPage.drawRectangle({
        x: rb.rx,
        y: rb.ry,
        width: rb.rw,
        height: rb.rh,
        color: rgb(rb.bgColor[0], rb.bgColor[1], rb.bgColor[2]),
        borderWidth: 0,
      })
    }
  }

  // PASS 2: Typeset translated text for each ProseGroup after all redactions are complete.
  for (let i = 0; i < proseGroups.length; i++) {
    const group = proseGroups[i]
    const trText = (translatedTexts[i] || group.sourceText).trim()
    group.translatedText = trText
    const groupBBox: BBox = {
      x: group.x0,
      y: group.y0,
      w: group.x1 - group.x0,
      h: group.y1 - group.y0,
    }
    if (group.uri) {
      registerPdfLinkAnnotation(groupBBox, group.uri)
    }

    if (preservedTargetGroups[i]) {
      blockMetas.push({
        id: group.id,
        kind: group.kind,
        bbox: groupBBox,
        pageW,
        pageH,
        sourceText: group.sourceText,
        translatedText: trText,
        fontScale: 1.0,
        preserved: true,
        uri: group.uri,
      })
      continue
    }

    const font = await pickFontForText(pdfDoc, fontBundle, group, trText)
    const fgColor = rgb(group.color[0], group.color[1], group.color[2])
    let appliedScale = 1.0
    let overflowFallback = false

    // Step 2a: Table of Contents (TOC) lines with leader dots and uniform vertical height via PDF Tz horizontal condensation
    if (group.kind === 'toc' && group.spans[0]?.isToc) {
      const sp = group.spans[0]
      const pageNumStr = sp.tocPageNum || ''
      const totalW = sp.x1 - sp.x0
      const pageNumW = safeWidthOfText(font, pageNumStr, group.size)
      const maxTitleW = Math.max(40, totalW - pageNumW - 8)

      let fontSize = group.size
      let horizScalePct = 100
      const rawTitleW = safeWidthOfText(font, trText, fontSize)
      let renderedTitleW = rawTitleW

      if (rawTitleW > maxTitleW) {
        const effectiveMinScale = Math.min(minShrink, 0.5)
        const reqTotalScale = maxTitleW / Math.max(1, rawTitleW)
        // Use PDF Tz horizontal condensation down to 78% first (and down to 65% if vertical scale reaches floor)
        let tzFactor = Math.max(0.78, Math.min(1.0, reqTotalScale))
        let neededVertScale = reqTotalScale / tzFactor
        if (neededVertScale < effectiveMinScale) {
          tzFactor = Math.max(0.65, Math.min(1.0, reqTotalScale / effectiveMinScale))
          neededVertScale = reqTotalScale / tzFactor
        }
        horizScalePct = tzFactor * 100
        appliedScale = Math.max(effectiveMinScale, Math.min(1.0, neededVertScale))
        if (neededVertScale < effectiveMinScale - 0.01) overflowFallback = true
        fontSize = group.size * appliedScale
        renderedTitleW = safeWidthOfText(font, trText, fontSize) * tzFactor
      }

      const baselinePdfY = pageH - sp.oy
      drawTextWithHorizScale(pdfPage, trText, {
        x: sp.x0,
        y: baselinePdfY,
        size: fontSize,
        font,
        color: fgColor,
        horizScalePct,
      })

      if (pageNumStr) {
        drawTextWithHorizScale(pdfPage, pageNumStr, {
          x: sp.x1 - pageNumW,
          y: baselinePdfY,
          size: group.size,
          font,
          color: fgColor,
        })
      }

      // Fill leader dots between title and page number
      const dotStart = sp.x0 + renderedTitleW + 3
      const dotEnd = sp.x1 - pageNumW - 3
      if (dotEnd > dotStart + 2) {
        const dotUnit = safeWidthOfText(font, '.', group.size)
        const count = Math.max(2, Math.floor((dotEnd - dotStart) / Math.max(2, dotUnit)))
        const dots = '.'.repeat(count)
        drawTextWithHorizScale(pdfPage, dots, {
          x: dotStart,
          y: baselinePdfY,
          size: group.size,
          font,
          color: fgColor,
        })
      }
    } else if (group.spans.length === 1) {
      // Single-line slot or heading (with bidirectional clearance & PDF Tz horizontal condensation)
      const sp = group.spans[0]
      const origW = Math.max(12, sp.x1 - sp.x0)
      const blockedOnRight = sp.rightClearanceX - sp.x1 < 12
      const availLeftShift = blockedOnRight
        ? Math.min(28, Math.max(0, sp.x0 - sp.leftClearanceX))
        : origW < 45
        ? Math.min(6, Math.max(0, sp.x0 - sp.leftClearanceX))
        : 0

      const fullW = safeWidthOfText(font, trText, group.size)
      const neededLeftShift =
        fullW > sp.rightClearanceX - sp.x0
          ? Math.min(availLeftShift, fullW - (sp.rightClearanceX - sp.x0))
          : 0
      const drawX = sp.x0 - neededLeftShift
      const clearanceW = Math.max(origW, sp.rightClearanceX - drawX)
      const maxAllowedW = Math.min(clearanceW * 1.02, Math.max(origW * 2.2, origW + 180))

      const effectiveMinScale = Math.min(minShrink, 0.5)

      if (fullW <= maxAllowedW) {
        // Fits on a single line at 100% original font size!
        const baselinePdfY = pageH - sp.oy
        drawTextWithHorizScale(pdfPage, trText, {
          x: drawX,
          y: baselinePdfY,
          size: group.size,
          font,
          color: fgColor,
        })
      } else {
        // Check if 2-line compact wrapping is possible when unobstructed below
        let minBelowY = pageH - 20
        const spMidY = (sp.y0 + sp.y1) / 2
        for (const mo of mathObstacles) {
          const hOverlap =
            Math.min(drawX + clearanceW, mo.bbox.x + mo.bbox.w) - Math.max(drawX, mo.bbox.x)
          const moMidY = mo.bbox.y + mo.bbox.h / 2
          if (hOverlap > 2 && moMidY > spMidY + 4 && mo.bbox.y + mo.bbox.h > sp.y1 + 1) {
            minBelowY = Math.min(minBelowY, Math.max(sp.y1, mo.bbox.y))
          }
        }
        for (let j = 0; j < proseGroups.length; j++) {
          if (j === i) continue
          const og = proseGroups[j]
          const ogEffectiveRight = Math.max(og.x1, Math.min(og.rightClearanceX, og.x0 + 140))
          const hOverlap = Math.min(drawX + clearanceW, ogEffectiveRight) - Math.max(drawX, og.x0)
          const ogMidY = (og.y0 + og.y1) / 2
          if (hOverlap > 2 && ogMidY > spMidY + 4 && og.y1 > sp.y1 + 1) {
            minBelowY = Math.min(minBelowY, Math.max(sp.y1, og.y0))
          }
        }
        const vertGapBelow = minBelowY - sp.y1
        const singleLineScale = clearanceW / Math.max(1, fullW)

        const drawSingleLineCondensed = () => {
          // Anisotropic single-line fit: combine PDF Tz horizontal condensation (down to 82% normally, or down to 64% for tight inline slots) with vertical font scale
          let tzFactor = Math.max(0.82, Math.min(1.0, singleLineScale))
          let neededVertScale = singleLineScale / tzFactor
          if (neededVertScale < effectiveMinScale) {
            tzFactor = Math.max(0.64, Math.min(1.0, singleLineScale / effectiveMinScale))
            neededVertScale = singleLineScale / tzFactor
          }
          appliedScale = Math.max(effectiveMinScale, Math.min(1.0, neededVertScale))
          const renderedW = fullW * appliedScale * tzFactor
          if (renderedW > clearanceW * 1.08 + 2.5) overflowFallback = true
          const fontSize = group.size * appliedScale
          const baselinePdfY = pageH - sp.oy
          drawTextWithHorizScale(pdfPage, trText, {
            x: drawX,
            y: baselinePdfY,
            size: fontSize,
            font,
            color: fgColor,
            horizScalePct: tzFactor * 100,
          })
        }

        if (singleLineScale < 0.78 && vertGapBelow >= group.size * 0.95 && clearanceW >= 42) {
          // Find the highest scale in [effectiveMinScale, 0.90] that wraps cleanly into <= 2 lines
          let bestWrapScale = 0
          let bestWrappedLines: string[] = []
          for (let cand = 0.90; cand >= effectiveMinScale - 0.001; cand -= 0.04) {
            const s = Math.max(effectiveMinScale, cand)
            const candLines = wrapTextToLines(trText, font, group.size * s, clearanceW)
            const allFitWidth = candLines.every(
              (ln) => safeWidthOfText(font, ln, group.size * s) <= clearanceW * 1.02
            )
            if (candLines.length <= 2 && allFitWidth) {
              bestWrapScale = s
              bestWrappedLines = candLines
              break
            }
          }

          if (bestWrapScale > 0 && bestWrappedLines.length <= 2) {
            appliedScale = bestWrapScale
            const wrapSize = group.size * bestWrapScale
            const compactStep = wrapSize * 1.02
            const startOy = sp.oy - wrapSize * 0.18
            for (let lnIdx = 0; lnIdx < bestWrappedLines.length; lnIdx++) {
              const py = pageH - (startOy + lnIdx * compactStep)
              drawTextWithHorizScale(pdfPage, bestWrappedLines[lnIdx], {
                x: drawX,
                y: py,
                size: wrapSize,
                font,
                color: fgColor,
              })
            }
          } else {
            drawSingleLineCondensed()
          }
        } else {
          drawSingleLineCondensed()
        }
      }
    } else {
      // Multi-line paragraph or display heading block (supports first-line indent, last-line obstacle inset, and strict vertical clearance)
      const rightMarginLimit = Math.max(group.x1, pageW - Math.min(36, Math.max(18, pageW * 0.05)))
      const numOrigLines = group.spans.length
      const nonLastSpans = numOrigLines > 1 ? group.spans.slice(0, -1) : group.spans
      const nonLastRightClearance = Math.min(...nonLastSpans.map((s) => s.rightClearanceX))
      const rawBoxW = Math.max(
        group.x1 - group.x0,
        Math.min(nonLastRightClearance - group.x0, (group.x1 - group.x0) * 1.45)
      )
      const boxW = Math.max(40, Math.min(rawBoxW, rightMarginLimit - group.x0))
      const boxH = group.y1 - group.y0
      const firstLineIndent =
        group.spans[0].x0 > group.x0 + 3 && group.spans[0].x0 - group.x0 < boxW * 0.45
          ? group.spans[0].x0 - group.x0
          : 0
      const lastSpan = group.spans[numOrigLines - 1]
      const lastLineMaxW =
        lastSpan && lastSpan.rightClearanceX - group.x0 < boxW - 6
          ? Math.max(36, Math.min(boxW, lastSpan.rightClearanceX - group.x0))
          : boxW

      // Check vertical obstacle clearance directly below this multi-line group
      let minBelowY = pageH - 16
      const lastSpanMidY = lastSpan ? (lastSpan.y0 + lastSpan.y1) / 2 : (group.y0 + group.y1) / 2
      for (const mo of mathObstacles) {
        const hOverlap =
          Math.min(group.x0 + boxW, mo.bbox.x + mo.bbox.w) - Math.max(group.x0, mo.bbox.x)
        const moMidY = mo.bbox.y + mo.bbox.h / 2
        if (hOverlap > 2 && moMidY > lastSpanMidY + 4 && mo.bbox.y + mo.bbox.h > group.y1 + 1) {
          minBelowY = Math.min(minBelowY, Math.max(group.y1, mo.bbox.y))
        }
      }
      for (let j = 0; j < proseGroups.length; j++) {
        if (j === i) continue
        const og = proseGroups[j]
        const hOverlap = Math.min(group.x0 + boxW, og.x1) - Math.max(group.x0, og.x0)
        const ogMidY = (og.y0 + og.y1) / 2
        if (hOverlap > 2 && ogMidY > lastSpanMidY + 4 && og.y1 > group.y1 + 1) {
          minBelowY = Math.min(minBelowY, Math.max(group.y1, og.y0))
        }
      }

      const rawSoftPad = Math.min(Math.max(3.0, boxH * 0.15), 1.2 * group.size * minShrink)
      const availGapBelow = Math.max(0, minBelowY - group.y1 - 1.2)
      const softPad = Math.min(rawSoftPad, availGapBelow)
      const maxBottomY = group.y1 + softPad
      const effectiveMinScale = Math.min(minShrink, 0.5)

      let bestScale = effectiveMinScale
      let bestLines = wrapTextToLines(
        trText,
        font,
        group.size * effectiveMinScale,
        boxW,
        firstLineIndent,
        numOrigLines - 1,
        lastLineMaxW
      )
      let fitted = false

      for (let s = 1.0; s >= effectiveMinScale - 0.001; s -= 0.02) {
        const candScale = Math.max(effectiveMinScale, s)
        const testSize = group.size * candScale
        const lines = wrapTextToLines(
          trText,
          font,
          testSize,
          boxW,
          firstLineIndent,
          numOrigLines - 1,
          lastLineMaxW
        )
        const candStep =
          lines.length <= numOrigLines && numOrigLines > 1
            ? (group.spans[numOrigLines - 1].oy - group.spans[0].oy) /
              Math.max(1, lines.length - 1)
            : testSize * 1.12
        const projectedBottomY =
          group.spans[0].oy +
          (lines.length - 1) * Math.min(candStep, testSize * 1.28) +
          testSize * 0.22
        const hasRightObstacleOnLastLine = lastLineMaxW < boxW - 6
        const fitsVertically = hasRightObstacleOnLastLine
          ? lines.length <= numOrigLines
          : lines.length <= numOrigLines || projectedBottomY <= maxBottomY
        const fitsHorizontally = lines.every((ln, idx) => {
          const lineMaxW =
            idx === 0
              ? Math.max(36, boxW - firstLineIndent)
              : idx >= numOrigLines - 1
              ? lastLineMaxW
              : boxW
          return safeWidthOfText(font, ln, testSize) <= lineMaxW * 1.01
        })

        if (fitsVertically && fitsHorizontally) {
          bestScale = candScale
          bestLines = lines
          fitted = true
          break
        }
      }

      // If standard wrapping at effectiveMinScale still needs more lines than fit vertically,
      // try horizontal condensation (Tz down to 82%) so fewer lines are needed without truncating any text
      if (!fitted) {
        const testSize = group.size * effectiveMinScale
        for (const tzPct of [92, 86, 80]) {
          const factor = 100 / tzPct
          const condLines = wrapTextToLines(
            trText,
            font,
            testSize,
            boxW * factor,
            firstLineIndent * factor,
            numOrigLines - 1,
            lastLineMaxW * factor
          )
          const candStep =
            condLines.length <= numOrigLines && numOrigLines > 1
              ? (group.spans[numOrigLines - 1].oy - group.spans[0].oy) /
                Math.max(1, condLines.length - 1)
              : testSize * 1.08
          const projectedBottomY =
            group.spans[0].oy +
            (condLines.length - 1) * Math.min(candStep, testSize * 1.22) +
            testSize * 0.22
          if (condLines.length <= numOrigLines || projectedBottomY <= maxBottomY + 1.5) {
            bestLines = condLines
            fitted = true
            break
          }
        }
      }

      if (!fitted) {
        overflowFallback = true
      }

      appliedScale = bestScale
      const fontSize = group.size * appliedScale
      const startOy = group.spans[0].oy
      const availTotalAscent = Math.max(
        fontSize * 0.95,
        maxBottomY - fontSize * 0.22 - startOy
      )
      const naturalStep =
        bestLines.length <= numOrigLines && numOrigLines > 1
          ? (group.spans[numOrigLines - 1].oy - startOy) / Math.max(1, bestLines.length - 1)
          : fontSize * 1.12
      const lineStep =
        bestLines.length > 1
          ? Math.min(
              naturalStep,
              fontSize * 1.28,
              Math.max(fontSize * 0.92, availTotalAscent / (bestLines.length - 1))
            )
          : naturalStep

      for (let lnIdx = 0; lnIdx < bestLines.length; lnIdx++) {
        const curOy = startOy + lnIdx * lineStep
        const py = pageH - curOy
        const lineX = lnIdx === 0 ? group.x0 + firstLineIndent : group.x0
        const lineMaxW =
          lnIdx === 0
            ? Math.max(36, boxW - firstLineIndent)
            : lnIdx >= numOrigLines - 1
            ? lastLineMaxW
            : boxW
        const lineW = safeWidthOfText(font, bestLines[lnIdx], fontSize)
        const horizScalePct = lineW > lineMaxW ? Math.max(76, (lineMaxW / lineW) * 100) : 100
        drawTextWithHorizScale(pdfPage, bestLines[lnIdx], {
          x: lineX,
          y: py,
          size: fontSize,
          font,
          color: fgColor,
          horizScalePct,
        })
      }
    }

    if (appliedScale < 0.99) {
      scaledBlocksCount++
    }

    // Matching ThanhNguyxnOrg/LayoutLingua/layoutlingua/server.py lines 570-590:
    // Adaptive font scaling within [effectiveMinScale, 1.0] is BlockFittingStatus.SUCCESS.
    // Only emit a warning in `issues` when a block overflows even at minimum scale (OVERFLOW_FALLBACK).
    if (overflowFallback) {
      issues.push({
        id: `iss_p${pageIndex + 1}_${group.id}`,
        severity: 'warning',
        page: pageIndex + 1,
        code: 'OVERFLOW_FALLBACK',
        title: `Page ${pageIndex + 1}: Text fit warning at minimum scale (${Math.round(
          appliedScale * 100
        )}%)`,
        detail: `Source: "${group.sourceText.slice(0, 80)}"`,
        region: group.id,
      })
    }

    blockMetas.push({
      id: group.id,
      kind: group.kind,
      bbox: groupBBox,
      pageW,
      pageH,
      sourceText: group.sourceText,
      translatedText: trText,
      fontScale: Number(appliedScale.toFixed(2)),
      preserved: false,
      uri: group.uri,
    })
  }

  return {
    pageNumber: pageIndex + 1,
    pageW,
    pageH,
    blocksTranslated: proseGroups.length,
    mathBlocksPreserved: mergedMath.length,
    scaledBlocksCount,
    status: issues.length > 0 ? 'warn' : 'ok',
    blocks: blockMetas,
    issues,
  }
}

/**
 * Decodes a PDFString or PDFHexString outline title into Unicode (handling UTF-16BE, UTF-16LE, UTF-8, PDFDocEncoding, and legacy VNI).
 */
function decodePdfOutlineTitle(titleObj: PDFString | PDFHexString): string {
  try {
    const bytes = titleObj.asBytes()
    if (bytes.length >= 2 && bytes[0] === 0xfe && bytes[1] === 0xff) {
      return titleObj.decodeText()
    }
    if (bytes.length >= 2 && bytes[0] === 0xff && bytes[1] === 0xfe) {
      return new TextDecoder('utf-16le').decode(bytes.subarray(2))
    }
    if (bytes.some((b) => b >= 0x80)) {
      try {
        const utf8 = new TextDecoder('utf-8', { fatal: true }).decode(bytes)
        if (utf8.trim()) return utf8
      } catch {
        // Fall through to PDFDocEncoding / VNI
      }
    }
    const raw = titleObj.decodeText()
    if (/[A-Za-z][ÆæØøŒœŸÿ©®™µ¶]|[a-zA-Z][ùúûõïäëâêÙÚÛÕÏÄËÂÊ]/.test(raw)) {
      return decodeVniToUnicode(raw)
    }
    return raw
  } catch {
    return titleObj.decodeText()
  }
}

/**
 * Traverses and translates the PDF Document Catalog `/Outlines` (Bookmark / Table of Contents sidebar tree) in-place.
 */
export async function translatePdfOutlines(
  pdfDoc: PDFDocument,
  sourceLang: string,
  targetLang: string,
  options?: {
    provider?: string
    geminiKey?: string
    geminiModel?: string
    openaiKey?: string
    openaiEndpoint?: string
    openaiModel?: string
    customGlossary?: string
  }
): Promise<number> {
  try {
    const outlinesRef = pdfDoc.catalog.get(PDFName.of('Outlines'))
    if (!outlinesRef) return 0
    const outlinesDict = pdfDoc.context.lookupMaybe(outlinesRef, PDFDict)
    if (!outlinesDict) return 0

    const items: Array<{ dict: PDFDict; title: string }> = []
    const visited = new Set<any>()

    const walk = (refOrObj: any) => {
      if (!refOrObj || visited.has(refOrObj)) return
      visited.add(refOrObj)
      const dict = pdfDoc.context.lookupMaybe(refOrObj, PDFDict)
      if (!dict || visited.has(dict)) return
      visited.add(dict)

      const titleEntry = dict.get(PDFName.of('Title'))
      if (titleEntry) {
        const lookedUp = pdfDoc.context.lookup(titleEntry)
        if (lookedUp instanceof PDFString || lookedUp instanceof PDFHexString) {
          const decoded = decodePdfOutlineTitle(lookedUp).trim()
          if (decoded) {
            items.push({ dict, title: decoded })
          }
        }
      }

      const firstChild = dict.get(PDFName.of('First'))
      if (firstChild) walk(firstChild)

      const nextSibling = dict.get(PDFName.of('Next'))
      if (nextSibling) walk(nextSibling)
    }

    const rootFirst = outlinesDict.get(PDFName.of('First'))
    if (rootFirst) walk(rootFirst)
    if (items.length === 0) return 0

    const sourceTitles = items.map((item) => item.title)
    const translatedTitles = await translateBatchWithFormulaShield(
      sourceTitles,
      sourceLang,
      targetLang,
      options
    )

    for (let i = 0; i < items.length; i++) {
      const tr = (translatedTitles[i] || items[i].title).trim()
      if (tr) {
        items[i].dict.set(PDFName.of('Title'), PDFHexString.fromText(tr))
      }
    }
    return items.length
  } catch {
    return 0
  }
}

/**
 * Subsets embedded TrueType fonts and deduplicates PDF streams/objects via MuPDF (`subsetFonts` + `garbage=4,compress`).
 * Prevents multi-page font stream duplication and keeps exported PDFs compact.
 */
export async function optimizePdfBuffer(pdfBytes: Buffer): Promise<Buffer> {
  try {
    const mupdf = await getMupdf()
    const doc = mupdf.Document.openDocument(pdfBytes, 'application/pdf').asPDF()
    if (!doc) return pdfBytes
    doc.subsetFonts()
    const out = doc.saveToBuffer('garbage=4,compress')
    return Buffer.from(out.asUint8Array())
  } catch {
    return pdfBytes
  }
}

/**
 * Renders a specific 1-indexed page of a PDF buffer into a crisp PNG Buffer using MuPDF.
 */
export async function renderPdfPageToPng(
  pdfBytes: Buffer,
  pageNumber: number,
  dpi = 150
): Promise<Buffer> {
  const mupdf = await getMupdf()
  const doc = mupdf.Document.openDocument(pdfBytes, 'application/pdf')
  const count = doc.countPages()
  const idx = Math.max(0, Math.min(count - 1, pageNumber - 1))
  const page = doc.loadPage(idx)
  const zoom = dpi / 72
  const matrix = mupdf.Matrix.scale(zoom, zoom)
  const pixmap = page.toPixmap(matrix, mupdf.ColorSpace.DeviceRGB, false, true)
  return Buffer.from(pixmap.asPNG())
}
