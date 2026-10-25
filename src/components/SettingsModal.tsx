import { useState, useEffect } from 'react'
import { IconX, IconCheck } from './icons'
import { Button } from './ui'
import {
  type AppSettings,
  type ProviderType,
  loadSettings,
  saveSettings,
  useSettings,
} from '../services/settings'
import { apiUrl } from '../services/api'

export { type AppSettings, loadSettings, saveSettings }

export default function SettingsModal({
  onClose,
  initialTab = 'config',
}: {
  onClose: () => void
  initialTab?: 'config' | 'guide'
}) {
  const [globalSettings, updateGlobalSettings] = useSettings()
  const [settings, setSettings] = useState<AppSettings>(globalSettings)
  const [saved, setSaved] = useState(false)
  const [activeTab, setActiveTab] = useState<'config' | 'guide'>(initialTab)
  const [discoveredModels, setDiscoveredModels] = useState<string[]>([])
  const [fetchingModels, setFetchingModels] = useState(false)

  useEffect(() => {
    setSettings((prev) => (prev.provider !== globalSettings.provider ? { ...prev, provider: globalSettings.provider } : prev))
  }, [globalSettings.provider])

  const handleSelectProvider = (newProvider: ProviderType) => {
    setSettings((prev) => {
      const next = { ...prev, provider: newProvider }
      updateGlobalSettings(next)
      return next
    })
  }

  const fetchModels = async () => {
    setFetchingModels(true)
    try {
      const res = await fetch(
        apiUrl(
          `/api/models?base_url=${encodeURIComponent(settings.openaiEndpoint)}&api_key=${encodeURIComponent(
            settings.openaiKey
          )}`
        )
      )
      if (res.ok) {
        const data = await res.json()
        if (data.models && data.models.length > 0) {
          setDiscoveredModels(data.models)
          if (!settings.openaiModel || !data.models.includes(settings.openaiModel)) {
            setSettings((prev) => ({ ...prev, openaiModel: data.models[0] }))
          }
        }
      }
    } catch (e) {
      console.warn('Failed to fetch models:', e)
    } finally {
      setFetchingModels(false)
    }
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const handleSave = () => {
    updateGlobalSettings(settings)
    setSaved(true)
    setTimeout(() => {
      setSaved(false)
      onClose()
    }, 600)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 backdrop-blur-xs p-6 select-none animate-in fade-in duration-150">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        className="w-[660px] max-w-full rounded-xl border border-line bg-white shadow-2xl overflow-hidden flex flex-col max-h-[85vh]"
      >
        <div className="flex items-center justify-between border-b border-line px-6 py-4 bg-canvas/40 shrink-0">
          <div className="flex items-center gap-3">
            <h2 id="settings-title" className="text-[17px] font-bold text-ink">
              Provider & Application Settings
            </h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded-md p-1.5 text-muted hover:bg-canvas hover:text-ink transition-colors"
          >
            <IconX className="size-4" />
          </button>
        </div>

        <div className="flex border-b border-line bg-canvas/20 px-6 shrink-0">
          <button
            onClick={() => setActiveTab('config')}
            className={`py-3 px-4 text-[13.5px] font-bold border-b-2 transition-colors cursor-pointer ${
              activeTab === 'config'
                ? 'border-teal text-teal'
                : 'border-transparent text-muted hover:text-ink'
            }`}
          >
            Configure Providers
          </button>
          <button
            onClick={() => setActiveTab('guide')}
            className={`py-3 px-4 text-[13.5px] font-bold border-b-2 transition-colors cursor-pointer flex items-center gap-1.5 ${
              activeTab === 'guide'
                ? 'border-teal text-teal'
                : 'border-transparent text-muted hover:text-ink'
            }`}
          >
            <span>Setup Guide & Instructions</span>
          </button>
        </div>

        {activeTab === 'config' && (
          <div className="p-6 space-y-6 overflow-y-auto flex-1">
            <div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-[13px] font-bold tracking-wider uppercase text-muted">
                  Translation Engine & Provider
                </h3>
                <button
                  type="button"
                  onClick={() => setActiveTab('guide')}
                  className="text-[12px] font-semibold text-teal hover:underline cursor-pointer"
                >
                  Need help? View Setup Guide →
                </button>
              </div>

              <div className="grid grid-cols-2 gap-3">
                {[
                  {
                    id: 'google',
                    name: 'Google Translate RPC',
                    sub: 'Fast batch web translation, zero setup (Free)',
                    badge: 'Zero Setup',
                  },
                  {
                    id: 'openai',
                    name: 'OpenAI-Compatible API',
                    sub: 'Cloud & Local: OpenAI, Claude, DeepSeek, Ollama, LM Studio',
                    badge: 'Universal LLM',
                  },
                  {
                    id: 'gemini',
                    name: 'Google Gemini API',
                    sub: 'Top mathematical reasoning & accuracy with API key',
                    badge: 'Free Tier',
                  },
                  {
                    id: 'argos',
                    name: 'Argos Translate (Offline)',
                    sub: 'Lightweight offline CTranslate2 NMT model',
                    badge: 'Offline',
                  },
                ].map((p) => (
                  <label
                    key={p.id}
                    className={`flex cursor-pointer flex-col rounded-lg border p-3.5 transition-all ${
                      settings.provider === p.id
                        ? 'border-teal bg-teal-soft/30 ring-1 ring-teal'
                        : 'border-line hover:border-line-strong bg-white'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-[13.5px] font-bold text-ink">{p.name}</span>
                      <input
                        type="radio"
                        name="provider"
                        value={p.id}
                        checked={settings.provider === p.id}
                        onChange={() => handleSelectProvider(p.id as ProviderType)}
                        className="accent-teal size-4"
                      />
                    </div>
                    <span className="mt-1 text-[12px] text-muted leading-snug">{p.sub}</span>
                    <div className="mt-2 flex items-center justify-between">
                      <span className="inline-block text-[10px] font-bold tracking-wide uppercase px-1.5 py-0.5 rounded bg-canvas text-muted">
                        {p.badge}
                      </span>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {settings.provider === 'google' && (
              <div className="rounded-lg border border-teal/30 bg-teal-soft/20 p-4 space-y-1.5">
                <p className="text-[13px] font-bold text-teal">Zero Setup Required</p>
                <p className="text-[12px] text-muted leading-relaxed">
                  Google Translate RPC connects directly to Google Neural MT with automatic formula token isolation (⟦MATH_0⟧). Ready to translate immediately.
                </p>
              </div>
            )}

            {settings.provider === 'gemini' && (
              <div className="rounded-lg border border-line bg-canvas/30 p-4 space-y-3">
                <label className="flex flex-col gap-1.5 text-[12.5px] font-semibold text-ink">
                  Model ID
                  <input
                    type="text"
                    value={settings.geminiModel}
                    placeholder="gemini-2.5-flash"
                    onChange={(e) => setSettings({ ...settings, geminiModel: e.target.value })}
                    className="h-9 rounded-md border border-line-strong bg-white px-3 font-mono text-[13px]"
                  />
                </label>
              </div>
            )}

            {settings.provider === 'openai' && (
              <div className="rounded-lg border border-line bg-canvas/30 p-4 space-y-3.5">
                <label className="flex flex-col gap-1.5 text-[12.5px] font-semibold text-ink">
                  API Base URL (Endpoint)
                  <input
                    type="text"
                    value={settings.openaiEndpoint}
                    placeholder="https://api.openai.com/v1 or http://localhost:11434/v1"
                    onChange={(e) => setSettings({ ...settings, openaiEndpoint: e.target.value })}
                    className="h-9 rounded-md border border-line-strong bg-white px-3 font-mono text-[13px]"
                  />
                </label>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-[12.5px] font-semibold text-ink">Model ID</label>
                    <button
                      type="button"
                      disabled={fetchingModels || !settings.openaiEndpoint}
                      onClick={fetchModels}
                      className="text-[12px] font-semibold text-teal hover:underline disabled:opacity-50 cursor-pointer"
                    >
                      {fetchingModels ? 'Scanning server...' : 'Fetch Available Models'}
                    </button>
                  </div>
                  <input
                    type="text"
                    value={settings.openaiModel}
                    onChange={(e) => setSettings({ ...settings, openaiModel: e.target.value })}
                    className="h-9 w-full rounded-md border border-line-strong bg-white px-3 font-mono text-[13px]"
                  />
                  {discoveredModels.length > 0 && (
                    <div className="flex flex-wrap gap-1 pt-1">
                      {discoveredModels.map((m) => (
                        <button
                          key={m}
                          type="button"
                          onClick={() => setSettings((prev) => ({ ...prev, openaiModel: m }))}
                          className={`px-2 py-0.5 rounded text-[11px] font-mono border cursor-pointer ${
                            settings.openaiModel === m
                              ? 'bg-teal text-white border-teal'
                              : 'bg-canvas text-ink border-line'
                          }`}
                        >
                          {m}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            <div className="space-y-2 pt-2 border-t border-line">
              <div className="flex items-center justify-between">
                <h3 className="text-[13px] font-bold tracking-wider uppercase text-muted">
                  Terminology Glossary (Optional)
                </h3>
                <span className="text-[11px] font-bold text-teal bg-teal-soft/30 px-2 py-0.5 rounded">
                  Built-in Multilingual STEM Active
                </span>
              </div>
              <textarea
                rows={3}
                value={settings.customGlossary || ''}
                onChange={(e) => setSettings({ ...settings, customGlossary: e.target.value })}
                placeholder={"e.g.\nTheorem = Định lý\nEigenvalue = Giá trị riêng"}
                className="w-full rounded-md border border-line-strong p-2.5 font-mono text-[12.5px] bg-white"
              />
            </div>
          </div>
        )}

        {activeTab === 'guide' && (
          <div className="p-6 space-y-4 overflow-y-auto flex-1 text-[13px] text-ink leading-relaxed">
            <div className="rounded-xl border border-teal/40 bg-teal-soft/10 p-4 space-y-1.5">
              <h4 className="font-bold text-teal">Google Translate RPC (Zero Setup)</h4>
              <p className="text-muted">
                Translates directly via Google Neural Machine Translation while shielding mathematical equations and inline tokens (`⟦MATH_0⟧`).
              </p>
            </div>
            <div className="rounded-xl border border-line p-4 space-y-1.5 bg-canvas/30">
              <h4 className="font-bold text-ink">OpenAI-Compatible & Local Ollama</h4>
              <p className="text-muted">
                Point Base URL to `http://localhost:11434/v1` (Ollama) or `https://api.openai.com/v1` and select your preferred model.
              </p>
            </div>
          </div>
        )}

        <div className="flex items-center justify-between border-t border-line bg-canvas/20 px-6 py-4 shrink-0">
          <Button size="sm" onClick={onClose}>
            Close
          </Button>
          <Button variant="primary" size="sm" onClick={handleSave} className="min-w-[100px]">
            {saved ? (
              <>
                <IconCheck className="size-4" /> Saved!
              </>
            ) : (
              'Save Settings'
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}
