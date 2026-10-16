import type { DocumentService, ProgressCallback } from './adapter'
import type {
  DocumentInfo,
  Page,
  Issue,
  TranslationOptions,
  TranslationProgress,
  ExportOptions,
} from './types'
import { pages, issues } from '../components/data'

export class MockDocumentService implements DocumentService {
  private isCancelled = false

  async openDocument(file: File | string): Promise<DocumentInfo> {
    const name = typeof file === 'string' ? file.split(/[\\/]/).pop() || file : file.name
    const size = typeof file === 'string' ? 2450000 : file.size

    return {
      name,
      size,
      pageCount: pages.length,
      wordCount: 4820,
      detectedLang: 'en',
      isEncrypted: false,
    }
  }

  async getPages(): Promise<Page[]> {
    return pages.map((p) => ({
      n: p.n,
      status: p.status === 'ok' ? 'translated' : p.status === 'warn' ? 'review' : 'failed',
      issues: p.status === 'warn' ? 1 : p.status === 'fallback' ? 2 : 0,
      words: p.blockCount * 45,
      engine: 'PyMuPDF + DocLayout-YOLO',
    }))
  }

  async getIssues(): Promise<Issue[]> {
    return issues.map((iss) => ({
      id: iss.id,
      page: iss.page,
      title: iss.title,
      sub: iss.detail,
      sev: iss.severity === 'failure' ? 'high' : iss.severity === 'warning' ? 'med' : 'low',
      bbox: [48, 120, 520, 240],
      code: iss.code,
      context: iss.next,
    }))
  }

  async startTranslation(
    options: TranslationOptions,
    onProgress?: ProgressCallback
  ): Promise<void> {
    this.isCancelled = false
    const totalPages = pages.length
    const pageStatusMap: Record<number, any> = {}

    for (let pageIdx = 1; pageIdx <= totalPages; pageIdx++) {
      if (this.isCancelled) {
        onProgress?.({
          phase: 'cancelled',
          currentPage: pageIdx,
          totalPages,
          percent: Math.round(((pageIdx - 1) / totalPages) * 100),
          currentStage: 'extract',
          pageStatusMap,
          message: 'Translation was cancelled by user.',
        })
        return
      }

      // Simulate translation progression
      const stages: Array<'extract' | 'layout' | 'translate' | 'typeset' | 'verify'> = [
        'extract',
        'layout',
        'translate',
        'typeset',
        'verify',
      ]

      for (const stage of stages) {
        if (this.isCancelled) return
        await new Promise((r) => setTimeout(r, 60))

        const progressPercent = Math.min(
          99,
          Math.round((((pageIdx - 1) * stages.length + stages.indexOf(stage) + 1) / (totalPages * stages.length)) * 100)
        )

        onProgress?.({
          phase: 'processing',
          currentPage: pageIdx,
          totalPages,
          percent: progressPercent,
          currentStage: stage,
          pageStatusMap,
          message: `Page ${pageIdx}/${totalPages}: Executing ${stage} stage...`,
        })
      }

      const pData = pages.find((p) => p.n === pageIdx)
      pageStatusMap[pageIdx] = pData?.status === 'ok' ? 'translated' : pData?.status === 'warn' ? 'review' : 'failed'
    }

    onProgress?.({
      phase: 'done',
      currentPage: totalPages,
      totalPages,
      percent: 100,
      currentStage: 'verify',
      pageStatusMap,
      message: 'Document translation completed successfully.',
    })
  }

  async cancelTranslation(): Promise<void> {
    this.isCancelled = true
  }

  async exportDocument(options: ExportOptions): Promise<{ outputPath: string }> {
    await new Promise((r) => setTimeout(r, 400))
    return {
      outputPath: options.outputPath || 'Documents/translated/output.pdf',
    }
  }
}
