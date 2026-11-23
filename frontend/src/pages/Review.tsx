import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { Confidence } from '../components/Confidence'
import { useApp } from '../context'
import { IconAlert } from '../icons'
import type { DocPerson, DocumentInfo, Person, Task, User } from '../types'

/** Doküman metnini, görev kaynaklarını numaralı vurgularla gösterir. */
function DocText({ text, tasks, focus }: { text: string; tasks: Task[]; focus: number | null }) {
  const spans = tasks
    .filter((t) => t.source.start >= 0 && t.source.end > t.source.start)
    .sort((a, b) => a.source.start - b.source.start)
  const out: ReactNode[] = []
  let pos = 0
  for (const t of spans) {
    if (t.source.start < pos) continue
    out.push(text.slice(pos, t.source.start))
    out.push(
      <mark key={t.id} id={`src-${t.id}`} className={focus === t.id ? 'focus' : ''}>
        <sup>{t.order_no}</sup>
        {text.slice(t.source.start, t.source.end)}
      </mark>,
    )
    pos = t.source.end
  }
  out.push(text.slice(pos))
  return <div className="doctext">{out}</div>
}

interface CardProps {
  t: Task
  members: User[]
  canDecide: boolean
  focused: boolean
  onFocus: () => void
  onDecide: (action: Action, assignee?: string, reason?: 'not_task' | 'not_now') => Promise<void>
  showWorkstream: boolean
  onAddPeople: (names: string[]) => void
}

type Action = 'pick' | 'accept' | 'reject' | 'undo' | 'promote' | 'dismiss' | 'share'

function TaskCard({ t, members, canDecide, focused, onFocus, onDecide, showWorkstream, onAddPeople }: CardProps) {
  const [editing, setEditing] = useState(false)
  const [rejecting, setRejecting] = useState(false)
  const hidden = t.forcing && !t.assignee
  const who: Person | null = t.assignee ?? t.suggested
  const changed = !!(t.assignee && t.suggested && t.assignee.id !== t.suggested.id)
  const overload = !!(who && who.load >= 90 && t.alternative && t.alternative.id !== who.id)
  const decided = t.status === 'accepted' || t.status === 'rejected'
  const locked = t.status === 'exported' || t.status === 'done'

  const statusText =
    t.status === 'accepted' ? `✓ Onaylandı · ${who?.name}` :
    t.status === 'rejected' ? (t.reject_reason === 'not_now' ? 'Reddedildi · görev ama şimdi değil' : 'Reddedildi · görev değil') :
    locked ? `${t.key} · ${t.status_label} · ${who?.name}` :
    hidden ? 'Önce kendi seçiminizi yapın' : 'Karar bekliyor'

  const pick = (id: string) => onDecide('pick', id).then(() => setEditing(false))

  return (
    <article className={`task ${t.status}${focused ? ' focus' : ''}`}>
      <div className="task-head">
        <div className="task-title">
          <span className="num" aria-hidden="true">{t.order_no}</span>
          <div>
            <h3>{t.title}</h3>
            {t.detail && <p className="task-sub">{t.detail}</p>}
          </div>
        </div>
        <div className="task-meta">
          {showWorkstream && t.workstream && <span className="ws-chip" title="HDBSCAN ile bulunan iş alanı">{t.workstream}</span>}
          {t.is_outlier && <span className="ws-chip odd" title="Ekipte benzeri yapılmamış görev">Alışılmadık</span>}
          <span>Tahmini {t.est_days} gün</span>
          <span aria-hidden="true">·</span>
          <button type="button" className="btn small" onClick={onFocus}>Kaynak {t.source.ref}</button>
        </div>
      </div>

      {t.unknown_mentions.length > 0 && !decided && !locked && (
        <p className="inline-warn">
          Cümlede adı geçen <b>{t.unknown_mentions.join(', ')}</b> ekipte kayıtlı değil, bu yüzden model başka birini
          öneremiyor.{' '}
          {canDecide && (
            <button type="button" className="linkbtn" onClick={() => onAddPeople(t.unknown_mentions)}>
              Ekibe ekle ve öneriyi yenile
            </button>
          )}
        </p>
      )}

      {hidden && canDecide ? (
        <div className="forcing">
          <div style={{ display: 'flex', gap: 10 }}>
            <span style={{ color: 'var(--warn)', flex: 'none', marginTop: 2 }}><IconAlert size={18} /></span>
            <div>
              <b>Model bu görevde emin değil</b>
              <p>Önerisini görmeden önce bu işi kime vereceğinizi seçin. Ardından iki seçimi yan yana göreceksiniz.</p>
            </div>
          </div>
          <div className="choices">
            {members.map((m) => (
              <button key={m.id} type="button" className="choice" onClick={() => pick(m.id)}>
                {m.name} <span>· {m.role} · %{m.load}</span>
              </button>
            ))}
          </div>
        </div>
      ) : (
        who && (
          <div className="split">
            <div className="who">
              <div className="label-row">
                <span className="eyebrow">{changed || t.lead_picked_first ? 'Sizin seçiminiz' : 'Önerilen kişi'}</span>
                <Confidence level={t.confidence} />
              </div>
              <div className="person">
                <div className="avatar lg" aria-hidden="true">{who.initials}</div>
                <div>
                  <b>{who.name}</b>
                  <small>{who.role} · Sprint yükü %{who.load}</small>
                </div>
              </div>
              {changed && t.suggested && (
                <p className="inline-note">
                  Model önerisi: <b>{t.suggested.name}</b>.{' '}
                  {canDecide && !decided && !locked && (
                    <button type="button" className="linkbtn" onClick={() => pick(t.suggested!.id)}>Öneriyi kullan</button>
                  )}
                </p>
              )}
              {overload && t.alternative && (
                <p className="inline-warn">
                  {who.name} bu sprintte %{who.load} dolu. Alternatif: <b>{t.alternative.name}</b> (yük %{t.alternative.load}).{' '}
                  {canDecide && !decided && !locked && (
                    <button type="button" className="linkbtn" onClick={() => pick(t.alternative!.id)}>Alternatife ver</button>
                  )}
                </p>
              )}
            </div>
            <div className="why">
              <span className="eyebrow">Neden bu kişi?</span>
              <ul>{t.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
            </div>
          </div>
        )
      )}

      {editing && canDecide && (
        <div className="choices">
          <span style={{ fontSize: 13, color: 'var(--muted)' }}>Kime verilsin?</span>
          {members.map((m) => (
            <button key={m.id} type="button" className={`choice${who?.id === m.id ? ' on' : ''}`} onClick={() => pick(m.id)}>
              {m.name} <span>· %{m.load}</span>
            </button>
          ))}
        </div>
      )}

      <div className="task-foot">
        <span className={`status ${t.status}`}>{statusText}</span>
        {canDecide && !locked && (
          <div className="actions">
            {decided ? (
              <button type="button" className="btn" onClick={() => onDecide('undo')}>Geri al</button>
            ) : (
              <>
                {rejecting ? (
                  <>
                    <button type="button" className="btn" onClick={() => onDecide('reject', undefined, 'not_task').then(() => setRejecting(false))}>Görev değil</button>
                    <button type="button" className="btn" onClick={() => onDecide('reject', undefined, 'not_now').then(() => setRejecting(false))}>Görev ama şimdi değil</button>
                  </>
                ) : (
                  <button type="button" className="btn" onClick={() => setRejecting(true)}>Reddet</button>
                )}
                {!hidden && <button type="button" className="btn" onClick={() => setEditing((v) => !v)}>Kişiyi değiştir</button>}
                <button type="button" className="btn primary" disabled={hidden} onClick={() => onDecide('accept')}>Onayla</button>
              </>
            )}
          </div>
        )}
      </div>
    </article>
  )
}

export default function Review() {
  const { id } = useParams()
  const docId = Number(id)
  const { me, org, refreshSidebar } = useApp()
  const navigate = useNavigate()
  const [doc, setDoc] = useState<DocumentInfo | null>(null)
  const [tasks, setTasks] = useState<Task[]>([])
  const [members, setMembers] = useState<User[]>([])
  const [focus, setFocus] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [people, setPeople] = useState<DocPerson[]>([])
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [skipPeople, setSkipPeople] = useState<Set<string>>(new Set())
  const canDecide = !!me?.is_lead

  useEffect(() => {
    setError('')
    api.document(docId).then(setDoc).catch((e) => setError((e as Error).message))
    api.documentTasks(docId).then(setTasks).catch(() => {})
    api.documentPeople(docId).then(setPeople).catch(() => {})
  }, [docId])

  useEffect(() => {
    if (canDecide) api.teamMembers().then(setMembers)
  }, [canDecide, tasks])

  const mainTasks = useMemo(() => tasks.filter((t) => t.kind !== 'announcement' && t.status !== 'candidate' && t.status !== 'dismissed'), [tasks])
  const candidates = useMemo(() => tasks.filter((t) => t.kind !== 'announcement' && (t.status === 'candidate' || t.status === 'dismissed')), [tasks])
  const announcements = useMemo(() => tasks.filter((t) => t.kind === 'announcement'), [tasks])
  const unregistered = useMemo(() => people.filter((p) => !p.user_id), [people])

  const counts = useMemo(() => {
    const c = { accepted: 0, rejected: 0, pending: 0, announced: 0 }
    for (const t of tasks) {
      if (t.status === 'accepted') c.accepted++
      else if (t.status === 'rejected') c.rejected++
      else if (t.status === 'suggested') c.pending++
      else if (t.status === 'announced') c.announced++
    }
    return c
  }, [tasks])

  const run = async (fn: () => Promise<void>) => {
    setError('')
    setBusy(true)
    try { await fn() } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  const extract = () => run(async () => setTasks(await api.extract(docId)))

  /** Dokümanda geçen kayıtsız kişileri ekibe ekle, ardından önerileri yeniden hesapla. */
  const addPeople = (names: string[]) =>
    run(async () => {
      if (!names.length) return
      await api.importPeople(docId, names)
      setPeople(await api.documentPeople(docId))
      if (tasks.length) setTasks(await api.extract(docId))
      refreshSidebar()
    })

  const decide = (t: Task) => (action: Action, assignee?: string, reason?: 'not_task' | 'not_now') =>
    run(async () => {
      const updated = await api.decide(t.id, action, assignee, reason)
      setTasks((ts) => ts.map((x) => (x.id === updated.id ? updated : x)))
    })

  const deleteDoc = () =>
    run(async () => {
      await api.deleteDocument(docId)
      refreshSidebar()
      navigate('/dokumanlar')
    })

  const exportAccepted = () =>
    run(async () => {
      await api.exportDocument(docId)
      refreshSidebar()
      navigate('/ekip')
    })

  const focusOn = (t: Task) => {
    setFocus((f) => (f === t.id ? null : t.id))
    document.getElementById(`src-${t.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  if (error && !doc) return <div className="center-msg">{error}</div>
  if (!doc) return <div className="center-msg">Yükleniyor…</div>

  return (
    <div className="review-bg">
      <div className="page">
        {canDecide && (
          <ol className="steps" aria-label="Adımlar">
            <li>1 · Doküman yükle</li>
            <li className="on">2 · Görevleri incele ve onayla</li>
            <li>3 · Aktar</li>
          </ol>
        )}
        <div className="cols">
          <section className="docpane" aria-labelledby="doc-title">
            <span className="eyebrow">Kaynak doküman</span>
            <h1 id="doc-title">{doc.title}</h1>
            <p style={{ margin: '0 0 20px', fontSize: 13, color: 'var(--muted)' }}>
              Yükleyen: {doc.uploaded_by?.name} · {new Date(doc.created_at).toLocaleDateString('tr-TR', { day: 'numeric', month: 'long', year: 'numeric' })}
              {canDecide && (
                <>
                  {' · '}
                  {confirmDelete ? (
                    <>
                      Silinsin mi?{' '}
                      <button type="button" className="linkbtn" onClick={() => setConfirmDelete(false)}>Vazgeç</button>{' '}
                      <button type="button" className="linkbtn" onClick={deleteDoc}>Evet, sil</button>
                    </>
                  ) : (
                    <button type="button" className="linkbtn" onClick={() => setConfirmDelete(true)}>Dokümanı sil</button>
                  )}
                </>
              )}
            </p>
            <DocText text={doc.text ?? ''} tasks={tasks.filter((t) => t.status !== 'dismissed')} focus={focus} />
          </section>

          <section className="taskcol" aria-labelledby="tasks-title">
            <div className="panel summary">
              <div>
                <h2 id="tasks-title">
                  {mainTasks.length ? `Dokümandan ${mainTasks.length} görev çıkarıldı` : 'Henüz görev çıkarılmadı'}
                </h2>
                <p>Kişi atamaları modelin önerisidir. Her birini onaylayın, değiştirin ya da reddedin.</p>
              </div>
              <div className="legend">
                <Confidence level={3} label={false} /> Yüksek
                <Confidence level={2} label={false} /> Orta
                <Confidence level={1} label={false} /> Düşük
              </div>
            </div>

            {canDecide && unregistered.length > 0 && (
              <section className="panel" aria-labelledby="people-title" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div>
                  <h2 id="people-title" style={{ margin: 0, fontSize: 16 }}>
                    Dokümanda geçen {unregistered.length} kişi ekipte kayıtlı değil
                  </h2>
                  <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--muted)' }}>
                    Model yalnızca kayıtlı ekip üyelerine görev önerebilir. Uzmanlık alanı, rolden tahmin edilir; sonra Ekip sayfasından düzeltebilirsiniz.
                  </p>
                </div>
                <div className="choices">
                  {unregistered.map((p) => {
                    const on = !skipPeople.has(p.name)
                    return (
                      <button
                        key={p.name}
                        type="button"
                        className={`choice${on ? ' on' : ''}`}
                        aria-pressed={on}
                        onClick={() =>
                          setSkipPeople((s) => {
                            const n = new Set(s)
                            if (n.has(p.name)) n.delete(p.name)
                            else n.add(p.name)
                            return n
                          })
                        }
                      >
                        {p.name} {p.role && <span>· {p.role}{p.is_lead ? ' (lider)' : ''}</span>}
                      </button>
                    )
                  })}
                </div>
                <div>
                  <button
                    type="button"
                    className="btn primary"
                    disabled={busy || unregistered.every((p) => skipPeople.has(p.name))}
                    onClick={() => addPeople(unregistered.filter((p) => !skipPeople.has(p.name)).map((p) => p.name))}
                  >
                    Seçilenleri ekibe ekle{tasks.length ? ' ve önerileri yenile' : ''}
                  </button>
                </div>
              </section>
            )}

            {tasks.length === 0 && canDecide && (
              <button type="button" className="btn primary" onClick={extract} disabled={busy}>
                {busy ? 'Çıkarılıyor…' : 'Görevleri çıkar'}
              </button>
            )}
            {error && <div className="error" role="alert">{error}</div>}

            {mainTasks.map((t) => (
              <TaskCard
                key={t.id}
                t={t}
                members={members}
                canDecide={canDecide}
                focused={focus === t.id}
                onFocus={() => focusOn(t)}
                onDecide={decide(t)}
                showWorkstream={!!org?.show_workstreams}
                onAddPeople={addPeople}
              />
            ))}

            {canDecide && announcements.length > 0 && (
              <section className="panel" aria-labelledby="ann-title" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div>
                  <h2 id="ann-title" style={{ margin: 0, fontSize: 16 }}>Duyurular: tek kişiye değil, tüm ekibe</h2>
                  <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--muted)' }}>
                    Bunlar kişiye atanmaz. Paylaşılanlar aktarımda tüm ekibin "benimle paylaşılanlar" listesine düşer.
                  </p>
                </div>
                {announcements.map((a) => (
                  <div key={a.id} className="card" style={{ flexDirection: 'row', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                    <button type="button" className="btn small" onClick={() => focusOn(a)}>{a.source.ref}</button>
                    <span style={{ flex: '1 1 300px', minWidth: 0, fontSize: 14 }}>{a.source.quote}</span>
                    {a.status === 'announcement' ? (
                      <div className="actions">
                        <button type="button" className="btn small" onClick={() => decide(a)('dismiss')}>Önemsiz</button>
                        <button type="button" className="btn small" onClick={() => decide(a)('promote')}>Görev yap</button>
                        <button type="button" className="btn small primary" onClick={() => decide(a)('share')}>Ekiple paylaş</button>
                      </div>
                    ) : (
                      <span style={{ fontSize: 13, color: 'var(--muted)' }}>
                        {a.status === 'announced' ? 'Ekiple paylaşılacak' : 'Paylaşılmayacak'} ·{' '}
                        <button type="button" className="linkbtn" onClick={() => decide(a)('undo')}>Geri al</button>
                      </span>
                    )}
                  </div>
                ))}
              </section>
            )}

            {canDecide && candidates.length > 0 && (
              <section className="panel" aria-labelledby="cand-title" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div>
                  <h2 id="cand-title" style={{ margin: 0, fontSize: 16 }}>Model emin olamadı: bunlar görev mi?</h2>
                  <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--muted)' }}>
                    Eşiğin biraz altında kalan cümleler. Cevabınız modelin bir sonraki eğitiminde kullanılır.
                  </p>
                </div>
                {candidates.map((c) => (
                  <div key={c.id} className="card" style={{ flexDirection: 'row', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                    <button type="button" className="btn small" onClick={() => focusOn(c)}>{c.source.ref}</button>
                    <span style={{ flex: '1 1 300px', minWidth: 0, fontSize: 14 }}>{c.source.quote}</span>
                    {c.detect_score != null && <span className="ws-chip">%{Math.round(c.detect_score * 100)}</span>}
                    {c.status === 'candidate' ? (
                      <div className="actions">
                        <button type="button" className="btn small" onClick={() => decide(c)('dismiss')}>Değil</button>
                        <button type="button" className="btn small primary" onClick={() => decide(c)('promote')}>Görev</button>
                      </div>
                    ) : (
                      <span style={{ fontSize: 13, color: 'var(--muted)' }}>
                        Görev değil · <button type="button" className="linkbtn" onClick={() => decide(c)('undo')}>Geri al</button>
                      </span>
                    )}
                  </div>
                ))}
              </section>
            )}

            {canDecide && (mainTasks.length > 0 || announcements.length > 0) && (
              <div className="exportbar">
                <div className="counts">
                  <span><b>{counts.accepted}</b> onaylandı</span>
                  <span><b>{counts.rejected}</b> reddedildi</span>
                  {counts.announced > 0 && <span><b>{counts.announced}</b> duyuru</span>}
                  <span className="wait"><b>{counts.pending}</b> karar bekliyor</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                  <span className="hint">{counts.pending ? 'Bekleyen görevler aktarılmaz' : 'Tüm görevler karara bağlandı'}</span>
                  <button type="button" className="btn" disabled={!(counts.accepted || counts.announced) || busy} onClick={exportAccepted}>
                    Onaylananları aktar ({counts.accepted}){counts.announced ? ` + ${counts.announced} duyuru` : ''}
                  </button>
                </div>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
