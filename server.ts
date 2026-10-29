import express from 'express'
import path from 'node:path'
import fs from 'node:fs'
import os from 'node:os'
import http from 'node:http'
import { spawn, execSync, type ChildProcess } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { createServer as createViteServer } from 'vite'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const PYTHON_PORT = Number(process.env.PYTHON_ENGINE_PORT) || 8765
let pythonProc: ChildProcess | null = null
let pythonReady = false
let bootstrappingVenv = false

function resolvePythonBinary(): string {
  const localVenvWin = path.join(process.cwd(), '.venv', 'Scripts', 'python.exe')
  if (fs.existsSync(localVenvWin)) {
    return localVenvWin
  }
  const localVenvPosix = path.join(process.cwd(), '.venv', 'bin', 'python')
  if (fs.existsSync(localVenvPosix)) {
    return localVenvPosix
  }

  const venvPy = '/tmp/pyvenv/bin/python'
  const readyMarker = '/tmp/pyvenv/.ready'
  if (fs.existsSync(venvPy) && fs.existsSync(readyMarker)) {
    return venvPy
  }
  if (!bootstrappingVenv && process.platform !== 'win32') {
    bootstrappingVenv = true
    try {
      console.log('[PythonEngine] Bootstrapping /tmp/pyvenv with PyMuPDF...')
      execSync(
        'python3 -m venv --without-pip /tmp/pyvenv && curl -sS https://bootstrap.pypa.io/get-pip.py | /tmp/pyvenv/bin/python && /tmp/pyvenv/bin/pip install -q pymupdf platformdirs ftfy numpy && /tmp/pyvenv/bin/python -c "import pymupdf" && touch /tmp/pyvenv/.ready',
        { stdio: 'inherit', timeout: 90000 }
      )
      if (fs.existsSync(venvPy) && fs.existsSync(readyMarker)) {
        return venvPy
      }
    } catch (err) {
      console.warn('[PythonEngine] Venv bootstrap notice:', err)
    } finally {
      bootstrappingVenv = false
    }
  }
  return process.platform === 'win32' ? 'python.exe' : 'python3'
}

function ensurePythonEngineRunning(): void {
  if (pythonProc && !pythonProc.killed) return
  const pyBin = resolvePythonBinary()

  try {
    pythonProc = spawn(pyBin, ['-m', 'layoutlingua.server'], {
      cwd: process.cwd(),
      env: {
        ...process.env,
        HOST: '127.0.0.1',
        PORT: String(PYTHON_PORT),
        PYTHON_ENGINE_PORT: String(PYTHON_PORT),
        PYTHONUNBUFFERED: '1',
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    })

    pythonProc.stdout?.on('data', (chunk) => {
      const msg = chunk.toString()
      if (msg.includes('listening') || msg.includes('Listening') || msg.includes(String(PYTHON_PORT))) {
        pythonReady = true
      }
      process.stdout.write(`[PythonEngine] ${msg}`)
    })

    pythonProc.stderr?.on('data', (chunk) => {
      process.stderr.write(`[PythonEngine] ${chunk.toString()}`)
    })

    pythonProc.on('exit', (code) => {
      pythonReady = false
      pythonProc = null
      console.warn(`[PythonEngine] exited with code ${code}, restarting in 1s...`)
      setTimeout(() => ensurePythonEngineRunning(), 1000)
    })
  } catch (err) {
    console.error('[PythonEngine] Failed to spawn python server:', err)
  }
}

async function waitForPythonEngine(maxWaitMs = 6000): Promise<boolean> {
  if (pythonReady) return true
  const start = Date.now()
  while (Date.now() - start < maxWaitMs) {
    try {
      const resp = await fetch(`http://127.0.0.1:${PYTHON_PORT}/api/health`, {
        signal: AbortSignal.timeout(400),
      })
      if (resp.ok) {
        pythonReady = true
        return true
      }
    } catch {
      // Wait for Python server to bind
    }
    await new Promise((r) => setTimeout(r, 120))
  }
  return pythonReady
}

const PROXY_PREFIXES = [
  '/api/',
  '/upload',
  '/translate',
  '/status',
  '/cancel',
  '/page-preview',
  '/page-image/',
  '/pdf/',
  '/save',
  '/system-folders',
  '/pick-folder',
  '/open-folder',
  '/export-python-engine',
  '/session-status',
]

async function startServer() {
  ensurePythonEngineRunning()
  void waitForPythonEngine(6000)

  const app = express()
  const PORT = Number(process.env.PORT) || 3000

  const resolveUserDirectory = (rawDir: string): string => {
    const home = path.resolve(os.homedir())
    const trimmed = (rawDir || '~/Downloads').trim()
    let candidate: string
    if (trimmed === '~' || trimmed.startsWith('~/') || trimmed.startsWith('~\\')) {
      candidate = path.resolve(home, trimmed.slice(2))
    } else {
      candidate = path.resolve(trimmed)
    }
    if (candidate === home || candidate.startsWith(home + path.sep)) {
      return candidate
    }
    return path.join(home, 'Downloads')
  }

  const validateProviderBaseUrl = (rawUrl: string): string | null => {
    try {
      const parsed = new URL((rawUrl || 'https://api.openai.com/v1').trim())
      if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return null
      if (parsed.username || parsed.password) return null
      const host = parsed.hostname.toLowerCase()
      const blocked = new Set([
        '169.254.169.254',
        'metadata.google.internal',
        'metadata.goog',
        '100.100.100.200',
        '0.0.0.0',
        '::',
        '[::]',
      ])
      if (
        blocked.has(host) ||
        host.startsWith('169.254.') ||
        host.startsWith('fe80:') ||
        host.endsWith('.internal')
      ) {
        return null
      }
      if (
        (host === 'localhost' || host === '127.0.0.1' || host === '::1') &&
        (Number(parsed.port) === PYTHON_PORT || Number(parsed.port) === PORT)
      ) {
        return null
      }
      return `${parsed.protocol}//${parsed.host}${parsed.pathname}`.replace(/\/$/, '')
    } catch {
      return null
    }
  }

  // Discover OpenAI-compatible models directly or pass through
  app.get(['/api/models', '/api/fetch-models'], async (req, res) => {
    const rawBaseUrl = String(req.query.base_url || 'https://api.openai.com/v1')
    const baseUrl = validateProviderBaseUrl(rawBaseUrl)
    if (!baseUrl) {
      res.status(400).json({
        models: [],
        status: 'error',
        error: 'Invalid or restricted provider base_url.',
      })
      return
    }
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

  // Proxy all engine API endpoints directly to the Python LayoutLingua server (port 8765)
  app.use(async (req, res, next) => {
    const shouldProxy = PROXY_PREFIXES.some(
      (p) => req.path === p || req.path.startsWith(p)
    )
    if (!shouldProxy) {
      return next()
    }

    if (!pythonReady) {
      ensurePythonEngineRunning()
      await waitForPythonEngine(15000)
    }

    const proxyReq = http.request(
      {
        hostname: '127.0.0.1',
        port: PYTHON_PORT,
        path: req.originalUrl,
        method: req.method,
        headers: {
          ...req.headers,
          host: `127.0.0.1:${PYTHON_PORT}`,
        },
      },
      (proxyRes) => {
        res.status(proxyRes.statusCode || 200)
        for (const [k, v] of Object.entries(proxyRes.headers)) {
          if (v !== undefined) {
            res.setHeader(k, v as any)
          }
        }
        proxyRes.pipe(res)
      }
    )

    proxyReq.on('error', (err: any) => {
      if (err?.code === 'ECONNREFUSED') {
        pythonReady = false
      }
      if (!res.headersSent) {
        res.status(502).json({
          error: `Python engine unavailable on port ${PYTHON_PORT}: ${err.message}`,
        })
      }
    })

    req.on('aborted', () => {
      proxyReq.destroy()
    })

    req.pipe(proxyReq)
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
    console.log(`[LayoutLingua] Frontend + Python Engine Proxy listening on http://0.0.0.0:${PORT}`)
  })
}

startServer()
