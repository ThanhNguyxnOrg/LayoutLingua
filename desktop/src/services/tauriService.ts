import type { DocumentService, ProgressCallback } from './adapter'
import type {
  DocumentInfo,
  Page,
  Issue,
  TranslationOptions,
  TranslationProgress,
  ExportOptions,
} from './types'

// Check if running inside Tauri runtime environment
export function isTauriEnvironment(): boolean {
  return typeof window !== 'undefined' && ('__TAURI_INTERNALS__' in window || '__TAURI__' in window)
}

export class TauriDocumentService implements DocumentService {
  private activeJobId: string | null = null

  async openDocument(file: File | string): Promise<DocumentInfo> {
    const filePath = typeof file === 'string' ? file : file.name
    // Call Tauri Rust command: parse_pdf_via_python
    if (isTauriEnvironment()) {
      try {
        const { invoke } = await import('@tauri-apps/api/core')
        const result = await invoke<DocumentInfo>('open_document', { path: filePath })
        return result
      } catch (err) {
        console.warn('[Tauri IPC] Failed to invoke open_document, falling back:', err)
      }
    }

    return {
      name: typeof file === 'string' ? file.split(/[\\/]/).pop() || file : file.name,
      size: typeof file === 'string' ? 1024000 : file.size,
      pageCount: 1,
      wordCount: 500,
      detectedLang: 'en',
      isEncrypted: false,
    }
  }

  async getPages(): Promise<Page[]> {
    if (isTauriEnvironment()) {
      try {
        const { invoke } = await import('@tauri-apps/api/core')
        return await invoke<Page[]>('get_pages')
      } catch (err) {
        console.warn('[Tauri IPC] Failed to invoke get_pages:', err)
      }
    }
    return []
  }

  async getIssues(): Promise<Issue[]> {
    if (isTauriEnvironment()) {
      try {
        const { invoke } = await import('@tauri-apps/api/core')
        return await invoke<Issue[]>('get_issues')
      } catch (err) {
        console.warn('[Tauri IPC] Failed to invoke get_issues:', err)
      }
    }
    return []
  }

  async startTranslation(
    options: TranslationOptions,
    onProgress?: ProgressCallback
  ): Promise<void> {
    if (isTauriEnvironment()) {
      const { invoke } = await import('@tauri-apps/api/core')
      const { listen } = await import('@tauri-apps/api/event')

      // Listen to streaming progress events emitted from Tauri Rust sidecar
      const unlisten = await listen<TranslationProgress>('translation-progress', (event) => {
        onProgress?.(event.payload)
      })

      try {
        await invoke('start_translation', { options })
      } finally {
        unlisten()
      }
    } else {
      console.warn('[Tauri IPC] Not running in Tauri runtime. Please run inside desktop app.')
    }
  }

  async cancelTranslation(): Promise<void> {
    if (isTauriEnvironment()) {
      const { invoke } = await import('@tauri-apps/api/core')
      await invoke('cancel_translation')
    }
  }

  async exportDocument(options: ExportOptions): Promise<{ outputPath: string }> {
    if (isTauriEnvironment()) {
      const { invoke } = await import('@tauri-apps/api/core')
      return await invoke<{ outputPath: string }>('export_document', { options })
    }
    return { outputPath: options.outputPath || 'export.pdf' }
  }
}
