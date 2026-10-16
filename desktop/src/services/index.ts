import type { DocumentService } from './adapter'
import { MockDocumentService } from './mockService'
import { TauriDocumentService, isTauriEnvironment } from './tauriService'

let instance: DocumentService | null = null

export function getDocumentService(): DocumentService {
  if (!instance) {
    if (isTauriEnvironment()) {
      console.info('[LayoutLingua Desktop] Running in native Tauri desktop environment.')
      instance = new TauriDocumentService()
    } else {
      console.info('[LayoutLingua Desktop] Running in browser preview mode using MockDocumentService.')
      instance = new MockDocumentService()
    }
  }
  return instance
}

export * from './types'
export * from './adapter'
export { isTauriEnvironment }
