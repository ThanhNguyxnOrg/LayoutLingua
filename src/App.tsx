import { useState, useEffect } from 'react'
import OpenScreen, { type SelectedDocument } from './components/OpenScreen'
import Workspace from './components/Workspace'
import HistoryScreen from './components/HistoryScreen'
import SettingsModal from './components/SettingsModal'
import HelpModal from './components/HelpModal'
import { AppHeader, NavRail, type RailItem } from './components/shell'

export default function App() {
  const [doc, setDoc] = useState<SelectedDocument | null>(null)
  const [rail, setRail] = useState<RailItem>('documents')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)

  // Global keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'o') {
        e.preventDefault()
        setDoc(null)
        setRail('documents')
      } else if (e.key === '?' && !['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement)?.tagName)) {
        e.preventDefault()
        setHelpOpen(true)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  const handleRailChange = (newRail: RailItem) => {
    if (newRail === 'settings') {
      setSettingsOpen(true)
    } else {
      setRail(newRail)
    }
  }

  const handleOpenDoc = (selectedDoc?: SelectedDocument) => {
    if (!selectedDoc) return
    setDoc(selectedDoc)
    setRail('documents')
  }

  return (
    <div className="flex h-screen w-full min-w-[800px] flex-col bg-canvas antialiased text-ink overflow-hidden">
      {rail === 'history' ? (
        <>
          <AppHeader
            center={
              <span className="text-[13px] font-medium text-muted">
                Viewing Recent Document History
              </span>
            }
            onHelp={() => setHelpOpen(true)}
          />
          <div className="flex min-h-0 flex-1">
            <NavRail active={rail} onChange={handleRailChange} />
            <HistoryScreen
              onOpenDoc={(item) => {
                handleOpenDoc({
                  id: item.id,
                  name: item.name,
                  pages: item.pages,
                  size: item.size,
                  path: item.path,
                  detectedLang: item.detectedLang,
                })
              }}
              onNavigateToOpen={() => setRail('documents')}
            />
          </div>
        </>
      ) : doc ? (
        <Workspace
          docInfo={doc}
          onClose={() => setDoc(null)}
          onHelp={() => setHelpOpen(true)}
          onOpenSettings={() => setSettingsOpen(true)}
          rail={<NavRail active={rail} onChange={handleRailChange} />}
        />
      ) : (
        <>
          <AppHeader
            center={
              <span className="text-[13px] font-medium text-muted">
                No document open — Ready to translate
              </span>
            }
            onHelp={() => setHelpOpen(true)}
          />
          <div className="flex min-h-0 flex-1">
            <NavRail active={rail} onChange={handleRailChange} />
            <OpenScreen onOpen={handleOpenDoc} />
          </div>
        </>
      )}

      {/* Global Modals */}
      {settingsOpen && <SettingsModal onClose={() => setSettingsOpen(false)} />}
      {helpOpen && <HelpModal onClose={() => setHelpOpen(false)} />}
    </div>
  )
}
