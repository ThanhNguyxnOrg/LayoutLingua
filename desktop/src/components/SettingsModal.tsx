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
                    id: 'gemini',
                    name: 'Google AI Studio (Gemini)',
                    sub: 'Top mathematical reasoning & accuracy with API key',
                    badge: 'Free Tier',
                  },
                  {
                    id: 'ollama',
                    name: 'Ollama (Local LLM)',
                    sub: 'Zero-key, 100% private, llama3 / qwen2.5',
                    badge: 'Local Private',
                  },
                  {
                    id: 'openai',
                    name: 'OpenAI / DeepSeek / Custom',
                    sub: 'Custom API endpoint & model compatible',
                    badge: 'Custom URL',
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
                        onChange={() => setSettings({ ...settings, provider: p.id as ProviderType })}
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

            {settings.provider === 'ollama' && (
              <div className="rounded-lg border border-line bg-canvas/30 p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[13px] font-bold text-ink">Local Ollama Server</span>
                  <button
                    type="button"
                    onClick={() => setActiveTab('guide')}
                    className="text-[12px] text-teal hover:underline cursor-pointer font-semibold"
                  >
                    Ollama setup instructions →
                  </button>
                </div>
                <label className="flex flex-col gap-1.5 text-[12.5px] font-semibold text-ink">
                  Ollama Endpoint (Base URL)
                  <input
                    type="text"
                    value={settings.ollamaEndpoint}
                    placeholder="http://localhost:11434/v1"
                    onChange={(e) => setSettings({ ...settings, ollamaEndpoint: e.target.value })}
                    className="h-9 rounded-md border border-line-strong bg-white px-3 font-mono text-[13px]"
                  />
                </label>
                <label className="flex flex-col gap-1.5 text-[12.5px] font-semibold text-ink">
                  Model Name
                  <input
                    type="text"
                    value={settings.ollamaModel}
                    placeholder="llama3 or qwen2.5"
                    onChange={(e) => setSettings({ ...settings, ollamaModel: e.target.value })}
                    className="h-9 rounded-md border border-line-strong bg-white px-3 font-mono text-[13px]"
                  />
                </label>
              </div>
            )}

            {settings.provider === 'openai' && (
              <div className="rounded-lg border border-line bg-canvas/30 p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[13px] font-bold text-ink">OpenAI / DeepSeek Configuration</span>
                  <button
                    type="button"
                    onClick={() => setActiveTab('guide')}
                    className="text-[12px] text-teal hover:underline cursor-pointer font-semibold"
                  >
                    DeepSeek / OpenAI setup guide →
                  </button>
                </div>
                <label className="flex flex-col gap-1.5 text-[12.5px] font-semibold text-ink">
                  API Base Endpoint
                  <input
                    type="text"
                    value={settings.openaiEndpoint}
                    placeholder="https://api.deepseek.com/v1 or https://api.openai.com/v1"
                    onChange={(e) => setSettings({ ...settings, openaiEndpoint: e.target.value })}
                    className="h-9 rounded-md border border-line-strong bg-white px-3 font-mono text-[13px]"
                  />
                </label>
                <label className="flex flex-col gap-1.5 text-[12.5px] font-semibold text-ink">
                  API Key
                  <input
                    type="password"
                    value={settings.openaiKey}
                    placeholder="sk-..."
                    onChange={(e) => setSettings({ ...settings, openaiKey: e.target.value })}
                    className="h-9 rounded-md border border-line-strong bg-white px-3 font-mono text-[13px]"
                  />
                </label>
                <label className="flex flex-col gap-1.5 text-[12.5px] font-semibold text-ink">
                  Model Name
                  <input
                    type="text"
                    value={settings.openaiModel}
                    placeholder="deepseek-chat or gpt-4o-mini"
                    onChange={(e) => setSettings({ ...settings, openaiModel: e.target.value })}
                    className="h-9 rounded-md border border-line-strong bg-white px-3 font-mono text-[13px]"
                  />
                </label>
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

            {/* Guide 2: Google AI Studio (Gemini) */}
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
                Delivers the highest academic translation quality and understands complex scientific contexts.
              </p>
              <ol className="text-[12.5px] text-ink space-y-1.5 list-decimal list-inside pl-1">
                <li>Open your browser and navigate to: <code className="bg-white px-1.5 py-0.5 rounded border border-line text-teal font-mono">https://aistudio.google.com/</code></li>
                <li>Log in with your Google account.</li>
                <li>Click <strong>"Get API key"</strong> on the left sidebar, then click <strong>"Create API key"</strong>.</li>
                <li>Copy the key (starts with <code className="font-mono text-muted">AIzaSy...</code>).</li>
                <li>Switch to the <strong>Configure Providers</strong> tab, select <strong>Google AI Studio</strong>, and paste your key.</li>
                <li>Recommended model ID: <code className="font-mono">gemini-2.5-flash</code>.</li>
              </ol>
            </div>

            {/* Guide 3: Ollama */}
            <div className="rounded-xl border border-line p-5 space-y-2.5 bg-canvas/30">
              <div className="flex items-center justify-between">
                <h4 className="text-[15px] font-bold text-ink flex items-center gap-2">
                  <span>🦙 Ollama (100% Offline Local LLM)</span>
                  <span className="text-[11px] font-bold bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full uppercase">
                    100% Private
                  </span>
                </h4>
              </div>
              <p className="text-[13px] text-ink leading-relaxed">
                Runs completely on your local machine GPU/CPU. Zero data ever leaves your computer.
              </p>
              <ol className="text-[12.5px] text-ink space-y-1.5 list-decimal list-inside pl-1">
                <li>Download Ollama from <code className="bg-white px-1.5 py-0.5 rounded border border-line text-teal font-mono">https://ollama.com</code> and install it.</li>
                <li>Open PowerShell or Terminal and pull your model:
                  <div className="mt-1 bg-ink text-white p-2 rounded-md font-mono text-[12px]">ollama run llama3</div>
                  <span className="text-[11.5px] text-muted">Or for multilingual strength: <code>ollama run qwen2.5</code></span>
                </li>
                <li>Ensure Ollama is running in background (accessible at <code>http://localhost:11434</code>).</li>
                <li>Select <strong>Ollama (Local LLM)</strong> in settings with Model Name set to <code>llama3</code> or <code>qwen2.5</code>.</li>
              </ol>
            </div>

            {/* Guide 4: DeepSeek / OpenAI */}
            <div className="rounded-xl border border-line p-5 space-y-2.5 bg-canvas/30">
              <div className="flex items-center justify-between">
                <h4 className="text-[15px] font-bold text-ink flex items-center gap-2">
                  <span>🌐 DeepSeek / OpenAI Compatible</span>
                  <span className="text-[11px] font-bold bg-amber-100 text-amber-800 px-2 py-0.5 rounded-full uppercase">
                    Custom Endpoint
                  </span>
                </h4>
              </div>
              <p className="text-[13px] text-ink leading-relaxed">
                Supports DeepSeek, Groq, OpenRouter, or official OpenAI models.
              </p>
              <ul className="text-[12.5px] text-ink space-y-1.5 list-disc list-inside pl-1">
                <li><strong>For DeepSeek:</strong> Set Endpoint to <code className="font-mono text-xs">https://api.deepseek.com/v1</code>, Model Name to <code className="font-mono text-xs">deepseek-chat</code>, and enter your DeepSeek API key.</li>
                <li><strong>For OpenAI:</strong> Set Endpoint to <code className="font-mono text-xs">https://api.openai.com/v1</code>, Model Name to <code className="font-mono text-xs">gpt-4o-mini</code>, and enter your OpenAI key.</li>
              </ul>
            </div>

            {/* Guide 5: Argos Translate */}
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
                Zero-key offline neural translation using CTranslate2.
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
