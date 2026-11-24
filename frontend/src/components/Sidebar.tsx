import { useEffect, useMemo, useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useApp } from '../context'
import { IconCheckBox, IconFile, IconLock, IconPlus, IconSearch, IconUsers } from '../icons'
import type { Conversation, Group, Task, User } from '../types'
import { Logo } from './Logo'

const trLower = (s: string) => s.replace(/I/g, 'ı').replace(/İ/g, 'i').toLowerCase()

export function Sidebar() {
  const { me, org, sidebarVersion, switchUser } = useApp()
  const navigate = useNavigate()
  const [convs, setConvs] = useState<Conversation[]>([])
  const [tasks, setTasks] = useState<Task[]>([])
  const [groups, setGroups] = useState<Group[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [q, setQ] = useState('')

  useEffect(() => {
    if (!me) return
    api.conversations().then(setConvs)
    api.myTasks().then(setTasks)
    api.groups().then(setGroups)
  }, [me, sidebarVersion])

  useEffect(() => {
    api.users().then(setUsers)
  }, [])

  const f = trLower(q.trim())
  const match = (s: string) => !f || trLower(s).includes(f)
  const shownConvs = useMemo(() => convs.filter((c) => match(c.title)).slice(0, 12), [convs, f]) // eslint-disable-line
  const shownTasks = useMemo(() => tasks.filter((t) => match(`${t.key} ${t.title}`)).slice(0, 8), [tasks, f]) // eslint-disable-line
  const shownGroups = useMemo(() => groups.filter((g) => match(g.name)), [groups, f]) // eslint-disable-line

  return (
    <aside className="sidebar" aria-label="Kenar menü">
      <div className="brand">
        <Logo size="sm" />
        <span>
          Görev Asistanı<span className="brand-dot" aria-hidden="true" />
        </span>
      </div>

      <Link to="/" className="btn primary block">
        <IconPlus />
        Yeni sohbet
      </Link>

      <label className="search">
        <IconSearch size={15} />
        <span className="sr-only">Ara</span>
        <input type="search" placeholder="Sohbet, görev, grup ara" value={q} onChange={(e) => setQ(e.target.value)} />
      </label>

      <nav className="navsec" aria-labelledby="nav-chats">
        <h2 id="nav-chats">Sohbetler</h2>
        {shownConvs.length === 0 && <div className="empty-note">Henüz sohbet yok</div>}
        {shownConvs.map((c) => (
          <NavLink key={c.id} to={`/c/${c.id}`} className={({ isActive }) => `navitem${isActive ? ' active' : ''}`}>
            <span className="grow">{c.title}</span>
          </NavLink>
        ))}
      </nav>

      <nav className="navsec" aria-labelledby="nav-tasks">
        <h2 id="nav-tasks">Görev geçmişi</h2>
        {shownTasks.length === 0 && <div className="empty-note">Atanmış görev yok</div>}
        {shownTasks.map((t) => (
          <button
            key={t.id}
            type="button"
            className="navitem"
            style={{ border: 0, background: 'none', cursor: 'pointer', textAlign: 'left' }}
            onClick={async () => {
              const r = await api.startConversation(`${t.key} görevini neden ben aldım?`)
              navigate(`/c/${r.conversation.id}`)
            }}
          >
            <span className="grow">
              {t.key} · {t.title}
            </span>
            <span className="meta" style={{ color: t.status === 'done' ? 'var(--ok)' : 'var(--primary)' }}>
              {t.status === 'done' ? 'Bitti' : 'Sürüyor'}
            </span>
          </button>
        ))}
      </nav>

      <nav className="navsec" aria-labelledby="nav-groups">
        <h2 id="nav-groups">Gruplarım</h2>
        {shownGroups.map((g) => (
          <div key={g.id} className="navitem">
            <span className="chip-sq" style={{ background: g.color }} aria-hidden="true">
              {g.short}
            </span>
            <span className="grow">{g.name}</span>
            <span className="meta">{g.member_count}</span>
          </div>
        ))}
        <NavLink to="/toplantilar" className={({ isActive }) => `navitem${isActive ? ' active' : ''}`}>
          <span className="chip-sq" style={{ background: '#eef1f5' }} aria-hidden="true">
            <IconUsers size={14} />
          </span>
          <span className="grow">Toplantılar</span>
        </NavLink>
        {me?.is_lead && (
          <NavLink to="/dokumanlar" className={({ isActive }) => `navitem${isActive ? ' active' : ''}`}>
            <span className="chip-sq" style={{ background: '#eef1f5' }} aria-hidden="true">
              <IconFile size={14} />
            </span>
            <span className="grow">Dokümanlar</span>
          </NavLink>
        )}
        {me?.is_lead && (
          <NavLink to="/ekip" className={({ isActive }) => `navitem${isActive ? ' active' : ''}`}>
            <span className="chip-sq" style={{ background: '#eef1f5' }} aria-hidden="true">
              <IconUsers size={14} />
            </span>
            <span className="grow">Ekip yükü</span>
          </NavLink>
        )}
        {me?.is_lead && (
          <NavLink to="/etiketle" className={({ isActive }) => `navitem${isActive ? ' active' : ''}`}>
            <span className="chip-sq" style={{ background: '#eef1f5' }} aria-hidden="true">
              <IconCheckBox size={14} />
            </span>
            <span className="grow">Veri etiketleme</span>
          </NavLink>
        )}
      </nav>

      <div className="side-foot">
        <div className="privacy">
          <IconLock size={13} />
          {org?.model_label ?? 'Yerel model'} · Veri kurum dışına çıkmaz
        </div>
        {me && (
          <div className="person" style={{ padding: '0 6px' }}>
            <div className="avatar" aria-hidden="true">{me.initials}</div>
            <div>
              <b style={{ fontSize: 14 }}>{me.name}</b>
              <small>
                {me.role} · {me.team_name}
              </small>
            </div>
          </div>
        )}
        <label className="userswitch">
          <span className="sr-only">Kullanıcı değiştir (geliştirme)</span>
          <select value={me?.id ?? ''} onChange={(e) => { switchUser(e.target.value); navigate('/') }}>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name} — {u.is_lead ? 'Takım lideri' : u.role}
              </option>
            ))}
          </select>
        </label>
      </div>
    </aside>
  )
}
