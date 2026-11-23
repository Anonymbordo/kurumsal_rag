import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useApp } from '../context'
import type { AccuracyRow, SkillOption, TeamLoad, User } from '../types'

/** Ekip üyeleri: ekle, uzmanlık alanlarını düzelt, görev geçmişi olmayanı çıkar. */
function Members({ onChange }: { onChange: () => void }) {
  const [members, setMembers] = useState<User[]>([])
  const [skills, setSkills] = useState<SkillOption[]>([])
  const [name, setName] = useState('')
  const [role, setRole] = useState('')
  const [picked, setPicked] = useState<string[]>([])
  const [error, setError] = useState('')

  const load = () => api.teamMembers().then(setMembers)
  useEffect(() => {
    load()
    api.skillOptions().then(setSkills)
  }, [])

  const label = (id: string) => skills.find((s) => s.id === id)?.label ?? id
  const act = async (fn: () => Promise<unknown>) => {
    setError('')
    try {
      await fn()
      await load()
      onChange()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const add = (e: FormEvent) => {
    e.preventDefault()
    if (name.trim().length < 2) return
    act(async () => {
      // Uzmanlık seçilmezse sunucu rolden tahmin eder ("Backend Geliştirici" → backend)
      await api.addMember({ name, role, skills: picked.length ? picked : undefined })
      setName('')
      setRole('')
      setPicked([])
    })
  }

  const toggle = (u: User, id: string) =>
    act(() => api.updateMember(u.id, { skills: u.skills.includes(id) ? u.skills.filter((s) => s !== id) : [...u.skills, id] }))

  return (
    <section className="panel" style={{ padding: '22px 24px', display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div>
        <h2 style={{ margin: 0, fontSize: 17 }}>Ekip üyeleri</h2>
        <p style={{ margin: '4px 0 0', fontSize: 14, color: 'var(--muted)' }}>
          Model yalnızca buradaki kişilere görev önerir. Kurum kurulumunda bu liste Active Directory'den gelir.
        </p>
      </div>
      {members.map((u) => (
        <div key={u.id} className="card" style={{ gap: 8 }}>
          <div className="card-head">
            <div>
              <b>{u.name}</b> <span style={{ color: 'var(--muted)', fontSize: 13 }}>· {u.role} · yük %{u.load}</span>
            </div>
            <button type="button" className="linkbtn" onClick={() => act(() => api.removeMember(u.id))}>Çıkar</button>
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {skills.map((sk) => (
              <button
                key={sk.id}
                type="button"
                className={`choice${u.skills.includes(sk.id) ? ' on' : ''}`}
                aria-pressed={u.skills.includes(sk.id)}
                style={{ minHeight: 30, padding: '4px 10px', fontSize: 12 }}
                onClick={() => toggle(u, sk.id)}
              >
                {sk.label}
              </button>
            ))}
          </div>
        </div>
      ))}
      <form onSubmit={add} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <label className="field" style={{ flex: '1 1 180px' }}>
            <span>Ad Soyad</span>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Oğuzhan Tekin" />
          </label>
          <label className="field" style={{ flex: '1 1 180px' }}>
            <span>Rol</span>
            <input value={role} onChange={(e) => setRole(e.target.value)} placeholder="Mobil Geliştirici" />
          </label>
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize: 13, color: 'var(--muted)' }}>Uzmanlık (boş bırakılırsa rolden tahmin edilir):</span>
          {skills.map((sk) => (
            <button
              key={sk.id}
              type="button"
              className={`choice${picked.includes(sk.id) ? ' on' : ''}`}
              aria-pressed={picked.includes(sk.id)}
              style={{ minHeight: 30, padding: '4px 10px', fontSize: 12 }}
              onClick={() => setPicked((p) => (p.includes(sk.id) ? p.filter((x) => x !== sk.id) : [...p, sk.id]))}
            >
              {label(sk.id)}
            </button>
          ))}
        </div>
        <div>
          <button type="submit" className="btn primary" disabled={name.trim().length < 2}>Ekibe ekle</button>
        </div>
      </form>
      {error && <div className="error" role="alert">{error}</div>}
    </section>
  )
}

const ACC_COLORS: Record<number, string> = {
  3: 'var(--primary)',
  2: 'color-mix(in srgb, var(--primary) 55%, #fff)',
  1: '#C2410C',
}

export default function Team() {
  const [load, setLoad] = useState<TeamLoad | null>(null)
  const [acc, setAcc] = useState<AccuracyRow[]>([])
  const [fixes, setFixes] = useState<{ label: string; count: number }[]>([])
  const { me } = useApp()

  const reloadLoad = () => api.teamLoad().then(setLoad)
  useEffect(() => {
    reloadLoad()
    api.accuracy().then(setAcc)
    api.corrections().then(setFixes)
  }, [])

  if (!load) return <div className="center-msg">Yükleniyor…</div>
  const over = load.members.filter((m) => m.after > load.limit)

  return (
    <div className="review-bg">
      <div className="page cols">
        <section className="panel" style={{ flex: '3 1 560px', minWidth: 0, padding: '22px 24px' }}>
          <h1 style={{ margin: 0, fontSize: 20 }}>Ekip yükü</h1>
          <p style={{ margin: '4px 0 18px', fontSize: 14, color: 'var(--muted)' }}>
            Açık renk: sprint başındaki yük. Koyu renk: aktarılan ve onaylanan yeni işler.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {load.members.map((m) => {
              const hot = m.after > load.limit
              return (
                <div className="loadrow" key={m.id}>
                  <div>
                    <div style={{ fontSize: 15, fontWeight: 600 }}>{m.name}</div>
                    <div style={{ fontSize: 13, color: 'var(--muted)' }}>{m.role} · {m.new_tasks} yeni görev</div>
                  </div>
                  <div className="loadbar" role="img" aria-label={`${m.name}: sprint başı yüzde ${m.before}, şimdi yüzde ${m.after}`}>
                    <i style={{ width: `${Math.min(m.after, 100)}%`, background: hot ? '#C2410C' : 'var(--primary)' }} />
                    <i style={{ width: `${Math.min(m.before, 100)}%`, background: hot ? '#F2B48A' : 'color-mix(in srgb, var(--primary) 30%, #fff)' }} />
                    <i className="limit" style={{ left: `${load.limit}%` }} />
                  </div>
                  <div style={{ fontSize: 15, fontWeight: 700, textAlign: 'right', color: hot ? '#9A3412' : 'var(--ink)' }}>%{m.after}</div>
                </div>
              )
            })}
          </div>
          {over.length > 0 && (
            <p className="inline-warn" style={{ marginTop: 18, fontSize: 14 }}>
              <b>{over.map((m) => m.name).join(', ')}</b> %{load.limit} kapasite sınırının üzerinde. Bazı görevleri başka birine
              vermeyi ya da sonraki sprinte almayı düşünebilirsiniz.
            </p>
          )}
        </section>

        <aside style={{ flex: '2 1 380px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 20 }}>
          <section className="panel" style={{ padding: '22px 24px' }}>
            <h2 style={{ fontSize: 17 }}>Model önerileri ne kadar tuttu?</h2>
            <p style={{ margin: '0 0 16px', fontSize: 14, color: 'var(--muted)' }}>
              Liderin öneriyi değiştirmeden onayladığı oran, güven seviyesine göre.
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {acc.map((a) => (
                <div className="accrow" key={a.level}>
                  <span>{a.label}</span>
                  <div className="accbar" role="img" aria-label={`${a.label}: yüzde ${a.unchanged_pct ?? 0}`}>
                    <i style={{ width: `${a.unchanged_pct ?? 0}%`, background: ACC_COLORS[a.level] }} />
                  </div>
                  <b style={{ textAlign: 'right' }}>{a.unchanged_pct == null ? '—' : `%${a.unchanged_pct}`}</b>
                </div>
              ))}
            </div>
            <p style={{ margin: '16px 0 0', fontSize: 13, color: 'var(--muted)', lineHeight: 1.55 }}>
              Düşük güvenli önerilerde lider önce kendi seçimini yapar; model önerisi ondan sonra gösterilir.
            </p>
          </section>
          <section className="panel" style={{ padding: '22px 24px' }}>
            <h2 style={{ fontSize: 17 }}>En çok düzeltilen alanlar</h2>
            {fixes.length === 0 ? (
              <p style={{ margin: 0, fontSize: 14, color: 'var(--muted)' }}>Henüz düzeltme yok.</p>
            ) : (
              <ul style={{ listStyle: 'none', padding: 0 }}>
                {fixes.map((f) => (
                  <li key={f.label} style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>{f.label}</span>
                    <span style={{ color: 'var(--muted)' }}>{f.count} düzeltme</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
          {me?.is_lead && <Members onChange={reloadLoad} />}
          <Link to="/yukle" className="btn">Yeni doküman yükle</Link>
        </aside>
      </div>
    </div>
  )
}
