import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import type { TaskSource } from '../types'

const MONTHS = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık']
const trDate = (iso: string | null) => {
  if (!iso) return '—'
  const d = new Date(iso.length === 10 ? iso + 'T00:00:00' : iso + 'Z')
  return `${d.getDate()} ${MONTHS[d.getMonth()]}`
}
const daysLeft = (iso: string | null) => {
  if (!iso) return null
  const ms = new Date(iso + 'T23:59:59').getTime() - Date.now()
  return Math.ceil(ms / 86_400_000)
}

interface Para {
  start: number
  end: number
  text: string
}

/** Dokümanı paragraflara böler; her paragrafın metindeki konumunu korur. */
function paragraphs(text: string): Para[] {
  const out: Para[] = []
  let pos = 0
  for (const line of text.split('\n')) {
    if (line.trim()) out.push({ start: pos, end: pos + line.length, text: line })
    pos += line.length + 1
  }
  return out
}

/**
 * Personel için sade görev görünümü: ne isteniyor, kim verdi, ne zaman, neden ben;
 * yanında dokümanda yalnızca bu görevin cümlesi vurgulu. Diğer görevler ve öneriler yok.
 */
export default function TaskSourceView() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [t, setT] = useState<TaskSource | null>(null)
  const [error, setError] = useState('')
  const [full, setFull] = useState(false)
  const markRef = useRef<HTMLElement>(null)

  useEffect(() => {
    setT(null)
    setFull(false)
    api.taskSource(Number(id)).then(setT).catch((e) => setError((e as Error).message))
  }, [id])

  useEffect(() => {
    markRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [t, full])

  const paras = useMemo(() => (t?.document ? paragraphs(t.document.text) : []), [t])
  const hit = useMemo(() => (t ? paras.findIndex((p) => p.start <= t.start && t.start < p.end) : -1), [paras, t])

  if (!t) return <div className="center-msg">{error || 'Yükleniyor…'}</div>

  const left = daysLeft(t.due)
  const shown = full || hit < 0 ? paras : paras.slice(Math.max(0, hit - 2), hit + 3)
  const hiddenBefore = !full && hit > 2
  const hiddenAfter = !full && hit >= 0 && hit + 3 < paras.length

  const ask = async () => {
    const r = await api.startConversation(`${t.key} görevini açıklar mısın?`, true)
    navigate(`/c/${r.conversation.id}`, { state: { pending: `${t.key} görevini açıklar mısın?` } })
  }

  return (
    <div className="review-bg">
      <div className="page" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div>
          <button type="button" className="linkbtn" onClick={() => navigate(-1)} style={{ fontSize: 13 }}>← Geri</button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 4, flexWrap: 'wrap' }}>
            <span className="keytag">{t.key}</span>
            <h1 style={{ margin: 0, fontSize: 22 }}>{t.title}</h1>
            <span className={`badge ${t.status === 'done' ? 'done' : 'active'}`}>{t.status_label}</span>
          </div>
        </div>

        <div className="src-wrap">
          <section className="src-main" aria-label="Görev özeti">
            <div>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)', letterSpacing: '.04em', marginBottom: 6 }}>
                DOKÜMANDA YAZAN
              </div>
              <blockquote className="ask">{t.sentence}</blockquote>
            </div>

            <div className="facts">
              <div className="fact">
                <span>Teslim</span>
                <b>{trDate(t.due)}</b>
                {left !== null && (
                  <span style={{ color: left < 0 ? 'var(--warn)' : left <= 2 ? 'var(--warn-ink)' : 'var(--muted)' }}>
                    {left < 0 ? `${-left} gün gecikti` : left === 0 ? 'bugün' : `${left} gün kaldı`}
                  </span>
                )}
              </div>
              <div className="fact">
                <span>Tahmini süre</span>
                <b>{t.est_days} iş günü</b>
              </div>
              <div className="fact">
                <span>Atayan</span>
                <b>{t.assigned_by ?? '—'}</b>
                {t.assigned_at && <span>{trDate(t.assigned_at)}</span>}
              </div>
              <div className="fact">
                <span>{t.is_mine ? 'Sorumlu' : 'Atanan'}</span>
                <b>{t.is_mine ? 'Sen' : (t.assignee?.name ?? '—')}</b>
              </div>
            </div>

            {t.reasons.length > 0 && (
              <div className="panel">
                <h2>{t.is_mine ? 'Neden sana verildi?' : 'Neden bu kişi?'}</h2>
                <ul>{t.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
              </div>
            )}

            <div className="actions" style={{ justifyContent: 'flex-start' }}>
              <button type="button" className="btn primary" onClick={ask}>Asistana açıklat</button>
            </div>
          </section>

          {t.document && (
            <section className="docpane src-doc" aria-label="Kaynak doküman">
              <div className="eyebrow">Kaynak · {t.ref}</div>
              <h1>{t.document.title}</h1>
              <p style={{ margin: '0 0 12px', fontSize: 13, color: 'var(--muted)' }}>
                {t.document.uploaded_by?.name} · {trDate(t.document.created_at)}
              </p>
              <div className="doctext">
                {hiddenBefore && (
                  <button type="button" className="linkbtn" onClick={() => setFull(true)}>… önceki {hit - 2} paragrafı göster</button>
                )}
                {shown.map((p) => {
                  if (p.start <= t.start && t.start < p.end) {
                    const a = t.start - p.start
                    const b = Math.min(p.text.length, t.end - p.start)
                    return (
                      <p key={p.start}>
                        <span className="dim">{p.text.slice(0, a)}</span>
                        <mark className="mine" ref={markRef}>{p.text.slice(a, b)}</mark>
                        <span className="dim">{p.text.slice(b)}</span>
                      </p>
                    )
                  }
                  return <p key={p.start} className="dim">{p.text}</p>
                })}
                {hiddenAfter && (
                  <button type="button" className="linkbtn" onClick={() => setFull(true)}>
                    … sonraki {paras.length - hit - 3} paragrafı göster
                  </button>
                )}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  )
}
