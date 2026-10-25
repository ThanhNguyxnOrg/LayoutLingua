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

  // Keep modal provider in perfect two-way sync if changed externally
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
        {/* Header */}
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

        {/* Tab Switcher */}
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
            <span>📖 Setup Guide & Instructions</span>
          </button>
        </div>

        {/* Tab 1: Configuration */}
        {activeTab === 'config' && (
          <div className="p-6 space-y-6 overflow-y-auto flex-1">
            {/* Provider Selection */}
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
                    name: 'Google AI Studio (Gemini)',
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
                      {p.id !== 'google' && (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.preventDefault()
                            setActiveTab('guide')
                          }}
                          className="text-[11px] font-semibold text-teal hover:underline cursor-pointer"
                        >
                          Setup instructions
                        </button>
                      )}
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {/* Conditional Provider Config */}
            {settings.provider === 'google' && (
              <div className="rounded-lg border border-teal/30 bg-teal-soft/20 p-4 space-y-1.5">
                <p className="text-[13px] font-bold text-teal-ink">Zero Setup Required</p>
                <p className="text-[12px] text-muted leading-relaxed">
                  Google Translate RPC connects directly to Google Neural MT with automatic formula token isolation (⟦LL_FORMULA_0000⟧). Ready to translate immediately without API keys or accounts.
                </p>
              </div>
            )}

            {settings.provider === 'gemini' && (
              <div className="rounded-lg border border-line bg-canvas/30 p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[13px] font-bold text-ink">Google AI Studio Settings</span>
                  <button
                    type="button"
                    onClick={() => setActiveTab('guide')}
                    className="text-[12px] text-teal hover:underline cursor-pointer font-semibold"
                  >
                    How to get a free Gemini Key →
                  </button>
                </div>
                <label className="flex flex-col gap-1.5 text-[12.5px] font-semibold text-ink">
                  Gemini API Key
                  <input
                    type="password"
                    value={settings.geminiKey}
                    placeholder="AIzaSy..."
                    onChange={(e) => setSettings({ ...settings, geminiKey: e.target.value })}
                    className="h-9 rounded-md border border-line-strong bg-white px-3 font-mono text-[13px]"
                  />
                </label>
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
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-[13px] font-bold text-ink">OpenAI-Compatible Endpoint Configuration</span>
                    <p className="text-[11.5px] text-muted">Supports any inference server implementing the OpenAI /v1 API standard (Cloud & Local).</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setActiveTab('guide')}
                    className="text-[12px] text-teal hover:underline cursor-pointer font-semibold shrink-0"
                  >
                    Setup guide →
                  </button>
                </div>

                <label className="flex flex-col gap-1.5 text-[12.5px] font-semibold text-ink">
                  API Base URL (Endpoint)
                  <input
                    type="text"
                    value={settings.openaiEndpoint}
                    placeholder="https://api.openai.com/v1 or http://localhost:11434/v1"
                    onChange={(e) => setSettings({ ...settings, openaiEndpoint: e.target.value })}
                    className="h-9 rounded-md border border-line-strong bg-white px-3 font-mono text-[13px]"
                  />
                  <span className="text-[11px] text-muted">
                    Examples: <code>https://api.openai.com/v1</code>, <code>https://openrouter.ai/api/v1</code>, <code>https://api.deepseek.com/v1</code>, <code>http://localhost:11434/v1</code> (Ollama)
                  </span>
                </label>

                <label className="flex flex-col gap-1.5 text-[12.5px] font-semibold text-ink">
                  API Key
                  <input
                    type="password"
                    value={settings.openaiKey}
                    placeholder="sk-... (leave blank or type 'ollama' for local servers)"
                    onChange={(e) => setSettings({ ...settings, openaiKey: e.target.value })}
                    className="h-9 rounded-md border border-line-strong bg-white px-3 font-mono text-[13px]"
                  />
                </label>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-[12.5px] font-semibold text-ink">
                      Model ID
                    </label>
                    <button
                      type="button"
                      disabled={fetchingModels || !settings.openaiEndpoint}
                      onClick={fetchModels}
                      className="text-[12px] font-semibold text-teal hover:underline disabled:opacity-50 cursor-pointer flex items-center gap-1"
                    >
                      {fetchingModels ? 'Scanning server...' : '🔍 Fetch Available Models'}
                    </button>
                  </div>
                  
                  <input
                    type="text"
                    list="discovered-models-list"
                    value={settings.openaiModel}
                    placeholder="e.g. gpt-4o-mini, anthropic/claude-3.5-sonnet, deepseek-chat, llama3.2"
                    onChange={(e) => setSettings({ ...settings, openaiModel: e.target.value })}
                    className="h-9 w-full rounded-md border border-line-strong bg-white px-3 font-mono text-[13px]"
                  />

                  {discoveredModels.length > 0 && (
                    <>
                      <datalist id="discovered-models-list">
                        {discoveredModels.map((m) => (
                          <option key={m} value={m} />
                        ))}
                      </datalist>
                      <div className="pt-1">
                        <span className="text-[11px] font-semibold text-muted block mb-1">
                          Found {discoveredModels.length} models on server (click to choose):
                        </span>
                        <div className="flex flex-wrap gap-1 max-h-24 overflow-y-auto p-1 border border-line rounded bg-white">
                          {discoveredModels.map((m) => (
                            <button
                              key={m}
                              type="button"
                              onClick={() => setSettings((prev) => ({ ...prev, openaiModel: m }))}
                              className={`px-2 py-0.5 rounded text-[11px] font-mono border transition-colors cursor-pointer ${
                                settings.openaiModel === m
                                  ? 'bg-teal text-white border-teal'
                                  : 'bg-canvas text-ink border-line hover:border-teal'
                              }`}
                            >
                              {m}
                            </button>
                          ))}
                        </div>
                      </div>
                    </>
                  )}

                  <p className="text-[11.5px] text-muted">
                    Type any custom model ID, or click <strong>Fetch Available Models</strong> to auto-load models directly from your server.
                  </p>
                </div>
              </div>
            )}

            {settings.provider === 'argos' && (
              <div className="rounded-lg border border-line bg-canvas/30 p-4 space-y-2">
                <span className="text-[13px] font-bold text-ink">Argos Translate (Offline Model)</span>
                <p className="text-[12px] text-muted leading-relaxed">
                  Runs 100% offline via CTranslate2. Requires the Python package <code>pip install argostranslate</code>.
                </p>
              </div>
            )}

            {/* Layout Invariants */}
            <div>
              <h3 className="text-[13px] font-bold tracking-wider uppercase text-muted mb-3">
                Layout & Formula Preservation
              </h3>
              <div className="space-y-3">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.preserveFormulas}
                    onChange={(e) => setSettings({ ...settings, preserveFormulas: e.target.checked })}
                    className="accent-teal size-4 rounded"
                  />
                  <div>
                    <span className="text-[13.5px] font-semibold text-ink">
                      Strict Formula & Equation Token Preservation
                    </span>
                    <p className="text-[12px] text-muted">
                      Protects LaTeX equations with token delimiters to avoid translation drift.
                    </p>
                  </div>
                </label>
              </div>
            </div>

            {/* Academic Glossary & User Custom Dictionary */}
            <div className="space-y-2 pt-2 border-t border-line">
              <div className="flex items-center justify-between">
                <h3 className="text-[13px] font-bold tracking-wider uppercase text-muted">
                  Terminology Glossary (Optional)
                </h3>
                <span className="text-[11px] font-bold text-teal bg-teal-soft/30 px-2 py-0.5 rounded">
                  Built-in Multilingual STEM Active
                </span>
              </div>
              <p className="text-[12px] text-muted leading-relaxed">
                LayoutLingua automatically applies standardized academic & math translations (Theorems, Lemmas, Proofs, Matrices, etc.). You can optionally add custom terms below (one per line: <code>Original = Translation</code>).
              </p>
              <textarea
                rows={3}
                value={settings.customGlossary || ''}
                onChange={(e) => setSettings({ ...settings, customGlossary: e.target.value })}
                placeholder={"e.g.\nTheorem = <target-language term>\nEigenvalue = <target-language term>"}
                className="w-full rounded-md border border-line-strong p-2.5 font-mono text-[12.5px] focus:border-teal focus:ring-1 focus:ring-teal bg-white"
              />
            </div>
          </div>
        )}

        {/* Tab 2: Detailed Setup Guide */}
        {activeTab === 'guide' && (
          <div className="p-6 space-y-6 overflow-y-auto flex-1">
            {/* Guide 1: Google Zero Setup */}
            <div className="rounded-xl border border-teal/40 bg-teal-soft/10 p-5 space-y-2.5">
              <div className="flex items-center justify-between">
                <h4 className="text-[15px] font-bold text-teal-ink flex items-center gap-2">
                  <span>⚡ Google Translate RPC</span>
                  <span className="text-[11px] font-bold bg-teal text-white px-2 py-0.5 rounded-full uppercase">
                    Zero Setup
                  </span>
                </h4>
              </div>
              <p className="text-[13px] text-ink leading-relaxed">
                <strong>No configuration needed!</strong> Translates directly via Google Neural Machine Translation while shielding all mathematical equations and formulas.
              </p>
              <ul className="text-[12.5px] text-muted space-y-1 list-disc list-inside">
                <li>Requires an active internet connection.</li>
                <li>Zero API keys, zero accounts, zero cost.</li>
                <li>To use: Simply choose <strong>Google Translate RPC</strong> and click Translate.</li>
              </ul>
            </div>

            {/* Guide 2: OpenAI-Compatible (Cloud & Local) */}
            <div className="rounded-xl border border-line p-5 space-y-3 bg-canvas/30">
              <div className="flex items-center justify-between">
                <h4 className="text-[15px] font-bold text-ink flex items-center gap-2">
                  <span>🌐 OpenAI-Compatible API (Cloud & Local LLMs)</span>
                  <span className="text-[11px] font-bold bg-amber-100 text-amber-800 px-2 py-0.5 rounded-full uppercase">
                    Universal Protocol
                  </span>
                </h4>
              </div>
              <p className="text-[13px] text-ink leading-relaxed">
                Connects to any inference backend implementing the standard OpenAI <code>/v1</code> REST API. You can freely specify any Base URL, API Key, and Model ID, or click <strong>Fetch Available Models</strong> to auto-load models.
              </p>
              
              <div className="space-y-2 text-[12.5px] text-ink">
                <div className="p-2.5 rounded-lg bg-white border border-line space-y-1">
                  <div className="font-bold text-teal flex items-center gap-1.5">🦙 Local Ollama (100% Private, Zero-Cost)</div>
                  <div className="text-muted leading-relaxed">
                    1. Download and install from <code>https://ollama.com</code>.<br />
                    2. In terminal, run: <code className="font-mono bg-canvas px-1 py-0.5 rounded text-ink">ollama run llama3.2</code> (or <code>ollama run qwen2.5</code>).<br />
                    3. In LayoutLingua Settings: Set <strong>Base URL</strong> to <code className="font-mono text-ink">http://localhost:11434/v1</code>, leave API Key blank (or type <code>ollama</code>), and click <strong>Fetch Available Models</strong>.
                  </div>
                </div>

                <div className="p-2.5 rounded-lg bg-white border border-line space-y-1">
                  <div className="font-bold text-teal flex items-center gap-1.5">🧠 OpenAI Official (GPT-4o, GPT-4o-mini)</div>
                  <div className="text-muted leading-relaxed">
                    Set Base URL to <code className="font-mono text-ink">https://api.openai.com/v1</code>, enter your OpenAI API key, and specify Model ID (e.g. <code>gpt-4o-mini</code>).
                  </div>
                </div>

                <div className="p-2.5 rounded-lg bg-white border border-line space-y-1">
                  <div className="font-bold text-teal flex items-center gap-1.5">🔀 OpenRouter (Claude 3.5 Sonnet, Llama 3.3, DeepSeek)</div>
                  <div className="text-muted leading-relaxed">
                    Set Base URL to <code className="font-mono text-ink">https://openrouter.ai/api/v1</code>, enter your OpenRouter key, and set Model ID (e.g. <code>anthropic/claude-3.5-sonnet</code>).
                  </div>
                </div>

                <div className="p-2.5 rounded-lg bg-white border border-line space-y-1">
                  <div className="font-bold text-teal flex items-center gap-1.5">🐋 DeepSeek API</div>
                  <div className="text-muted leading-relaxed">
                    Set Base URL to <code className="font-mono text-ink">https://api.deepseek.com/v1</code>, enter your DeepSeek key, and set Model ID to <code>deepseek-chat</code>.
                  </div>
                </div>
              </div>
            </div>

            {/* Guide 3: Google AI Studio (Gemini) */}
            <div className="rounded-xl border border-line p-5 space-y-2.5 bg-canvas/30">
              <div className="flex items-center justify-between">
                <h4 className="text-[15px] font-bold text-ink flex items-center gap-2">
                  <span>✨ Google AI Studio (Gemini)</span>
                  <span className="text-[11px] font-bold bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full uppercase">
                    Free Tier Available
                  </span>
                </h4>
              </div>
              <p className="text-[13px] text-ink leading-relaxed">
                Delivers high academic translation quality with free tier API keys directly from Google.
              </p>
              <ol className="text-[12.5px] text-ink space-y-1.5 list-decimal list-inside pl-1">
                <li>Navigate to <code className="bg-white px-1.5 py-0.5 rounded border border-line text-teal font-mono">https://aistudio.google.com/</code>.</li>
                <li>Log in and click <strong>"Get API key"</strong> $\rightarrow$ <strong>"Create API key"</strong>.</li>
                <li>Paste your key into the <strong>Google AI Studio</strong> settings tab (Model ID: <code className="font-mono">gemini-2.5-flash</code>).</li>
              </ol>
            </div>

            {/* Guide 4: Argos Translate */}
            <div className="rounded-xl border border-line p-5 space-y-2.5 bg-canvas/30">
              <div className="flex items-center justify-between">
                <h4 className="text-[15px] font-bold text-ink flex items-center gap-2">
                  <span>📦 Argos Translate</span>
                  <span className="text-[11px] font-bold bg-gray-100 text-gray-700 px-2 py-0.5 rounded-full uppercase">
                    Offline NMT
                  </span>
                </h4>
              </div>
              <p className="text-[13px] text-ink leading-relaxed">
                Zero-key offline neural translation using CTranslate2 for systems without dedicated GPUs.
              </p>
              <ul className="text-[12.5px] text-ink space-y-1 list-disc list-inside">
                <li>Run in terminal: <code className="font-mono bg-white px-1.5 py-0.5 rounded border border-line">pip install argostranslate</code></li>
                <li>LayoutLingua will automatically manage model packages upon first run.</li>
              </ul>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-line bg-canvas/20 px-6 py-4 shrink-0">
          <Button size="sm" onClick={onClose}>
            Close
          </Button>
          {activeTab === 'config' ? (
            <Button variant="primary" size="sm" onClick={handleSave} className="min-w-[100px]">
              {saved ? (
                <>
                  <IconCheck className="size-4" /> Saved!
                </>
              ) : (
                'Save Settings'
              )}
            </Button>
          ) : (
            <Button variant="primary" size="sm" onClick={() => setActiveTab('config')}>
              Go to Configure →
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
