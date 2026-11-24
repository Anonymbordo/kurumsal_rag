import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useApp } from '../context'
import type { MeetingInfo, User } from '../types'

export const MEETING_STATUS: Record<MeetingInfo['status'], string> = {
  live: 'Devam ediyor',
  processing: 'İşleniyor',
  done: 'Rapor hazır',
  failed: 'Hata',
}

/** Toplantılar: yeni toplantı aç, geçmiş toplantıların raporlarına git. */
export default function Meetings() {
  const { me } = useApp()
  const navigate = useNavigate()
  const [list, setList] = useState<MeetingInfo[] | null>(null)
  const [members, setMembers] = useState<User[]>([])
  const [title, setTitle] = useState('')
  const [picked, setPicked] = useState<string[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.meetings().then(setList).catch((e) => setError((e as Error).message))
    api.teamMembers().then(setMembers).catch(() => {})
  }, [me])

  const create = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const m = await api.createMeeting(title, picked)
      navigate(`/toplanti/${m.id}`)
    } catch (err) {
      setError((err as Error).message)
      setBusy(false)
    }
  }

  const others = members.filter((u) => u.id !== me?.id)
  return (
    <div className="review-bg">
      <div className="page narrow" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 24 }}>Toplantılar</h1>
          <p style={{ margin: '4px 0 0', color: 'var(--muted)', fontSize: 14 }}>
            Görüşme portal içinde yapılır. Toplantı bitince konuşmalar yazıya dökülür, rapor hazırlanır ve görev önerileri lider onayına düşer.
          </p>
        </div>

        <form className="panel" onSubmit={create} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <h2 style={{ margin: 0, fontSize: 16 }}>Yeni toplantı</h2>
          <label className="field">
            <span>Konu</span>
            <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Sprint 19 planlama" required minLength={2} />
          </label>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ fontSize: 13, color: 'var(--muted)' }}>Katılımcılar:</span>
            {others.map((u) => {
              const on = picked.includes(u.id)
              return (
                <button
                  key={u.id}
                  type="button"
                  className={`choice${on ? ' on' : ''}`}
                  aria-pressed={on}
                  style={{ minHeight: 32, padding: '4px 12px', fontSize: 13 }}
                  onClick={() => setPicked((p) => (on ? p.filter((x) => x !== u.id) : [...p, u.id]))}
                >
                  {u.name} <span>· {u.role}</span>
                </button>
              )
            })}
          </div>
          <div>
            <button type="submit" className="btn primary" disabled={busy || title.trim().length < 2}>
              Toplantıyı başlat
            </button>
          </div>
        </form>

        {error && <div className="error" role="alert">{error}</div>}
        {list?.length === 0 && <div className="panel">Henüz toplantı yok.</div>}
        {list?.map((m) => (
          <Link key={m.id} to={`/toplanti/${m.id}`} className="card" style={{ textDecoration: 'none', color: 'inherit' }}>
            <div className="card-head">
              <div style={{ minWidth: 0 }}>
                <b style={{ fontSize: 15 }}>{m.title}</b>
                <div style={{ fontSize: 13, color: 'var(--muted)' }}>
                  {new Date(m.started_at + 'Z').toLocaleString('tr-TR', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })} ·{' '}
                  {m.participants.map((p) => p.name.split(' ')[0]).join(', ')}
                </div>
              </div>
              <span className={`badge ${m.status === 'done' ? 'done' : m.status === 'live' ? 'new' : 'active'}`}>
                {MEETING_STATUS[m.status]}
              </span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
