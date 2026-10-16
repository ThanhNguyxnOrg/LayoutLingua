import type {
  DocumentInfo,
  Page,
  Issue,
  Stage,
  TranslationOptions,
  TranslationProgress,
  ExportOptions,
} from './types'

export type ProgressCallback = (progress: TranslationProgress) => void

export interface DocumentService {
  /**
   * Opens and parses a PDF document.
   */
  openDocument(file: File | string): Promise<DocumentInfo>

  /**
   * Retrieves the current list of pages with metadata.
   */
  getPages(): Promise<Page[]>

  /**
   * Retrieves detected quality / layout issues for the document.
   */
  getIssues(): Promise<Issue[]>

  /**
   * Starts layout-aware document translation with real-time telemetry streaming.
   */
  startTranslation(
    options: TranslationOptions,
    onProgress?: ProgressCallback
  ): Promise<void>

  /**
   * Cancels any active translation job gracefully.
   */
  cancelTranslation(): Promise<void>

  /**
   * Exports the translated document to the requested format and location.
   */
  exportDocument(options: ExportOptions): Promise<{ outputPath: string }>
}
