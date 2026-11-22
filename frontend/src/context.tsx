import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, setUserId } from './api'
import type { Org, User } from './types'

interface AppState {
  org: Org | null
  me: User | null
  sidebarVersion: number
  refreshSidebar: () => void
  switchUser: (id: string) => void
}

const Ctx = createContext<AppState | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const [org, setOrg] = useState<Org | null>(null)
  const [me, setMe] = useState<User | null>(null)
  const [sidebarVersion, setSidebarVersion] = useState(0)

  useEffect(() => {
    api.org().then((o) => {
      setOrg(o)
      const root = document.documentElement.style
      root.setProperty('--accent', o.accent)
      root.setProperty('--primary', o.primary || o.accent)
      document.title = o.name && o.name !== 'Kurum Adı' ? `Görev Asistanı · ${o.name}` : 'Görevlendirme Asistanı'
    })
  }, [])

  const loadMe = useCallback(() => {
    api.me().then(setMe)
  }, [])
  useEffect(loadMe, [loadMe])

  const refreshSidebar = useCallback(() => setSidebarVersion((v) => v + 1), [])
  const switchUser = useCallback(
    (id: string) => {
      setUserId(id)
      loadMe()
      refreshSidebar()
    },
    [loadMe, refreshSidebar],
  )

  return <Ctx.Provider value={{ org, me, sidebarVersion, refreshSidebar, switchUser }}>{children}</Ctx.Provider>
}

export function useApp() {
  const v = useContext(Ctx)
  if (!v) throw new Error('AppProvider eksik')
  return v
}
