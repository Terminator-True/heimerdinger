import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'
import { SettingsDialog } from './SettingsDialog'

const UNAUTHORIZED_EVENT = 'heimerdinger:unauthorized'

interface SettingsContextValue {
  open: boolean
  openDialog: () => void
  closeDialog: () => void
}

const SettingsContext = createContext<SettingsContextValue | null>(null)

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const openDialog = useCallback(() => setOpen(true), [])
  const closeDialog = useCallback(() => setOpen(false), [])

  useEffect(() => {
    // Any view's 401 opens the key-entry flow; no redirect, no route guard.
    // The listener lives here so it survives dialog mount/unmount cycles.
    window.addEventListener(UNAUTHORIZED_EVENT, openDialog)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, openDialog)
  }, [openDialog])

  return (
    <SettingsContext.Provider value={{ open, openDialog, closeDialog }}>
      {children}
      <SettingsDialog />
    </SettingsContext.Provider>
  )
}

export function useSettings(): SettingsContextValue {
  const ctx = useContext(SettingsContext)
  if (!ctx) throw new Error('useSettings must be used within SettingsProvider')
  return ctx
}
