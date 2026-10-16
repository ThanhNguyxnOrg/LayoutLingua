import { useState, useEffect } from 'react'

export type ProviderType = 'google' | 'openai' | 'gemini' | 'argos' | 'ollama'

export interface AppSettings {
  provider: ProviderType
  geminiKey: string
  geminiModel: string
  openaiKey: string
  openaiEndpoint: string
  openaiModel: string
  ollamaEndpoint?: string
  ollamaModel?: string
  targetLang: string
  preserveFormulas: boolean
  minFontShrink: number
}

export const DEFAULT_SETTINGS: AppSettings = {
  provider: 'google',
  geminiKey: '',
  geminiModel: 'gemini-2.5-flash',
  openaiKey: '',
  openaiEndpoint: 'https://api.openai.com/v1',
  openaiModel: 'gpt-4o-mini',
  targetLang: 'vi',
  preserveFormulas: true,
  minFontShrink: 0.7,
}

const STORAGE_KEY = 'layoutlingua_settings'
const EVENT_NAME = 'layoutlingua:settings_updated'

export function loadSettings(): AppSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      const merged = { ...DEFAULT_SETTINGS, ...parsed }
      // Transparent migration: convert legacy 'ollama' provider to unified 'openai'
      if (merged.provider === 'ollama') {
        merged.provider = 'openai'
        if (parsed.ollamaEndpoint) merged.openaiEndpoint = parsed.ollamaEndpoint
        if (parsed.ollamaModel) merged.openaiModel = parsed.ollamaModel
      }
      return merged
    }
  } catch {}
  return DEFAULT_SETTINGS
}

export function saveSettings(s: AppSettings) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s))
    window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: s }))
  } catch {}
}

export function useSettings(): [AppSettings, (s: AppSettings | ((prev: AppSettings) => AppSettings)) => void] {
  const [settings, setSettings] = useState<AppSettings>(loadSettings)

  useEffect(() => {
    const handleUpdate = (e: Event) => {
      const custom = e as CustomEvent<AppSettings>
      if (custom.detail) {
        setSettings(custom.detail)
      } else {
        setSettings(loadSettings())
      }
    }
    window.addEventListener(EVENT_NAME, handleUpdate)
    window.addEventListener('storage', handleUpdate)
    return () => {
      window.removeEventListener(EVENT_NAME, handleUpdate)
      window.removeEventListener('storage', handleUpdate)
    }
  }, [])

  const updateSettings = (val: AppSettings | ((prev: AppSettings) => AppSettings)) => {
    const next = typeof val === 'function' ? val(settings) : val
    setSettings(next)
    saveSettings(next)
  }

  return [settings, updateSettings]
}
