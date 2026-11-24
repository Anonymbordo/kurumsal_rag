import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useApp } from '../context'
import type { Dashboard as DashboardData } from '../types'

/*
 * Lider panosu. Renk kuralları (dataviz yöntemi):
 *  - Veri renkleri markadan ayrı: kurum kırmızısı yalnızca arayüzde; veri mavisi/turuncusu doğrulandı
 *    (kategorik 2 slot: CVD ΔE 24.7; akış rampası 5 adım, tek ton, monoton açıklık).
 *  - Durum renkleri (gecikme, aşırı yük) her zaman ikon + etiketle; renk tek başına anlam taşımaz.
 *  - Her grafikte üzerine gelince ipucu, her kartta "Tablo" görünümü.
 */

const MONTHS = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara']
const DAYS = ['Paz', 'Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt']
const d0 = (iso: string) => new Date(iso + 'T00:00:00')
const fmt = (d: Date) => `${d.getDate()} ${MONTHS[d.getMonth()]}`

type Tip = { x: number; y: number; body: ReactNode } | null

function Card({
  title,
  sub,
  children,
  table,
}: {
  title: string
  sub?: string
  children: ReactNode
  table?: ReactNode
}) {
  const [asTable, setAsTable] = useState(false)
  return (
    <section className="viz-card">
      <header>
        <div>
          <h2>{title}</h2>
          {sub && <p>{sub}</p>}
        </div>
        {table && (
          <button type="button" className="viz-toggle" aria-pressed={asTable} onClick={() => setAsTable((v) => !v)}>
            {asTable ? 'Grafik' : 'Tablo'}
          </button>
        )}
      </header>
      {asTable && table ? <div className="viz-table">{table}</div> : children}
    </section>
  )
}

function Kpi({ label, value, note, status }: { label: string; value: ReactNode; note?: ReactNode; status?: 'critical' | 'good' }) {
  return (
    <div className="kpi">
      <span className="kpi-label">{label}</span>
      <span className="kpi-value">{value}</span>
      {note && (
        <span className={`kpi-note${status ? ` st-${status}` : ''}`}>
          {status === 'critical' && <span aria-hidden="true">▲ </span>}
          {note}
        </span>
      )}
    </div>
  )
}

/** Dokümandan işe: taranan cümleden tamamlanan işe kadar her aşama ve bir öncekine oranı. */
function Funnel({ data, onTip }: { data: DashboardData['funnel']; onTip: (t: Tip) => void }) {
  const max = Math.max(1, ...data.map((d) => d.count))
  return (
    <div className="funnel">
      {data.map((d, i) => {
        const prev = i > 0 ? data[i - 1].count : null
        const rate = prev ? Math.round((d.count / prev) * 100) : null
        return (
          <div
            key={d.stage}
            className="funnel-row"
            onMouseMove={(e) =>
              onTip({
                x: e.clientX,
                y: e.clientY,
                body: (
                  <>
                    <b>{d.stage}</b>
                    <div>{d.count} {i === 0 ? 'cümle' : 'görev'}</div>
                    {rate !== null && <div>Önceki aşamanın %{rate}'i</div>}
                  </>
                ),
              })
            }
            onMouseLeave={() => onTip(null)}
          >
            <span className="funnel-label">{d.stage}</span>
            <span className="funnel-track">
              <span className={`funnel-bar s${i}`} style={{ width: `${Math.max(1.5, (d.count / max) * 100)}%` }} />
            </span>
            <span className="funnel-value">
              <b>{d.count}</b>
              {rate !== null && <span className="muted"> · %{rate}</span>}
            </span>
          </div>
        )
      })}
    </div>
  )
}

/** Ekip yükü: mevcut iş + bu araçla atanan, kapasite sınırı çizgisiyle. */
function Load({ data, limit, onTip }: { data: DashboardData['load']; limit: number; onTip: (t: Tip) => void }) {
  const scale = Math.max(120, ...data.map((d) => d.total + 10))
  const pos = (v: number) => `${(v / scale) * 100}%`
  return (
    <div className="load">
      <div className="viz-legend" aria-hidden="true">
        <span><i className="sw s1" /> Mevcut iş</span>
        <span><i className="sw s2" /> Bu araçla atanan</span>
        <span><i className="sw-line" /> Kapasite sınırı %{limit}</span>
      </div>
      <div className="load-rows">
        <span className="load-limit" style={{ left: `calc(var(--load-label) + (100% - var(--load-label) - var(--load-value)) * ${limit / scale})` }}>
          <span>%{limit}</span>
        </span>
        {data.map((d) => {
          const over = d.total >= 100 ? 'critical' : d.total > limit ? 'serious' : null
          return (
            <div
              key={d.id}
              className="load-row"
              onMouseMove={(e) =>
                onTip({
                  x: e.clientX,
                  y: e.clientY,
                  body: (
                    <>
                      <b>{d.name}</b> <span className="muted">· {d.role}</span>
                      <div><i className="sw s1" /> Mevcut iş: %{d.base}</div>
                      <div><i className="sw s2" /> Bu araçla atanan: %{d.added}</div>
                      <div>Toplam: <b>%{d.total}</b>{over ? ' — kapasite üstünde' : ''}</div>
                    </>
                  ),
                })
              }
              onMouseLeave={() => onTip(null)}
            >
              <span className="load-name">
                {d.name}
                <small>{d.role}</small>
              </span>
              <span className="load-track">
                {d.base > 0 && <span className="seg s1" style={{ width: pos(d.base) }} />}
                {d.added > 0 && <span className="seg s2" style={{ width: pos(d.added) }} />}
              </span>
              <span className="load-value">
                <b>%{d.total}</b>
                {over && (
                  <span className={`st-${over}`}>
                    {' '}
                    <span aria-hidden="true">▲</span> {over === 'critical' ? 'aşırı yük' : 'sınırda'}
                  </span>
                )}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

/** Teslim takvimi: kişi × gün (bugünden 14 gün). Gecikenler solda ayrı sütunda. */
function Schedule({
  data,
  members,
  today,
  onTip,
  onOpen,
}: {
  data: DashboardData['schedule']
  members: DashboardData['members']
  today: string
  onTip: (t: Tip) => void
  onOpen: (id: number) => void
}) {
  const start = d0(today)
  const days = Array.from({ length: 14 }, (_, i) => new Date(start.getTime() + i * 86_400_000))
  const key = (d: Date) => d.toISOString().slice(0, 10)
  const cell = useMemo(() => {
    const m = new Map<string, DashboardData['schedule']>()
    for (const t of data) {
      const k = `${t.assignee_id}|${t.overdue ? 'late' : t.due}`
      m.set(k, [...(m.get(k) ?? []), t])
    }
    return m
  }, [data])
  const rows = members.filter((u) => data.some((t) => t.assignee_id === u.id))
  if (rows.length === 0) return <p className="muted" style={{ margin: 0 }}>Önümüzdeki 14 günde teslimi olan açık görev yok.</p>

  const dots = (items: DashboardData['schedule'] | undefined, late: boolean) =>
    items?.length ? (
      <button
        type="button"
        className={`dot${late ? ' late' : ''}${items.length > 1 ? ' many' : ''}`}
        aria-label={`${items.length} görev: ${items.map((t) => t.key).join(', ')}`}
        onClick={() => onOpen(items[0].id)}
        onMouseMove={(e) =>
          onTip({
            x: e.clientX,
            y: e.clientY,
            body: (
              <>
                <b>{items[0].assignee}</b>
                {late && <div className="st-critical"><span aria-hidden="true">▲</span> Gecikmiş</div>}
                {items.map((t) => (
                  <div key={t.id}>
                    <span className="muted">{t.key}</span> {t.title} <span className="muted">· {fmt(d0(t.due))}</span>
                  </div>
                ))}
              </>
            ),
          })
        }
        onMouseLeave={() => onTip(null)}
      >
        {items.length > 1 ? items.length : ''}
      </button>
    ) : null

  return (
    <div className="sched" style={{ gridTemplateColumns: `minmax(120px, 1.4fr) 64px repeat(14, minmax(26px, 1fr))` }}>
      <span />
      <span className="sched-h late-h">Gecikmiş</span>
      {days.map((d, i) => (
        <span key={i} className={`sched-h${i === 0 ? ' today' : ''}${d.getDay() % 6 === 0 ? ' weekend' : ''}`}>
          {i === 0 ? 'Bugün' : DAYS[d.getDay()]}
          <small>{d.getDate()}</small>
        </span>
      ))}
      {rows.map((u) => (
        <div key={u.id} className="sched-row" style={{ display: 'contents' }}>
          <span className="sched-name">{u.name}</span>
          <span className="sched-c late-c">{dots(cell.get(`${u.id}|late`), true)}</span>
          {days.map((d, i) => (
            <span key={i} className={`sched-c${i === 0 ? ' today' : ''}${d.getDay() % 6 === 0 ? ' weekend' : ''}`}>
              {dots(cell.get(`${u.id}|${key(d)}`), false)}
            </span>
          ))}
        </div>
      ))}
    </div>
  )
}

/** Model güvenilirliği: güven seviyesine göre liderin öneriyi değiştirmeden onayladığı oran. */
function Calibration({ data, onTip }: { data: DashboardData['accuracy']; onTip: (t: Tip) => void }) {
  return (
    <div className="calib">
      {data.map((r) => (
        <div
          key={r.level}
          className="calib-row"
          onMouseMove={(e) =>
            onTip({
              x: e.clientX,
              y: e.clientY,
              body: (
                <>
                  <b>{r.label}</b>
                  <div>{r.total} karar{r.unchanged_pct !== null ? `, %${r.unchanged_pct}'i değiştirilmeden onaylandı` : ''}</div>
                </>
              ),
            })
          }
          onMouseLeave={() => onTip(null)}
        >
          <span className="calib-label">
            <span className={`conf l${r.level}`} aria-hidden="true"><i /><i /><i /></span> {r.label}
          </span>
          <span className="funnel-track">
            {r.unchanged_pct !== null && <span className="calib-bar" style={{ width: `${Math.max(1.5, r.unchanged_pct)}%` }} />}
          </span>
          <span className="funnel-value">
            {r.unchanged_pct === null ? <span className="muted">veri yok</span> : <b>%{r.unchanged_pct}</b>}
            <span className="muted"> · {r.total} karar</span>
          </span>
        </div>
      ))}
    </div>
  )
}

export default function Dashboard() {
  const { me } = useApp()
  const navigate = useNavigate()
  const [d, setD] = useState<DashboardData | null>(null)
  const [error, setError] = useState('')
  const [tip, setTip] = useState<Tip>(null)

  useEffect(() => {
    if (me?.is_lead) api.dashboard().then(setD).catch((e) => setError((e as Error).message))
  }, [me])

  if (me && !me.is_lead) return <div className="center-msg">Pano takım liderlerine açık.</div>
  if (!d) return <div className="center-msg">{error || 'Yükleniyor…'}</div>
  const k = d.kpis
  const open = (id: number) => navigate(`/gorev/${id}`)

  return (
    <div className="review-bg viz-root">
      <div className="page" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div className="card-head">
          <div>
            <h1 style={{ margin: 0, fontSize: 24 }}>Ekip panosu</h1>
            <p style={{ margin: '4px 0 0', color: 'var(--muted)', fontSize: 14 }}>
              {me?.team_name} · {fmt(d0(d.today))} · tüm hesaplamalar kurum sunucusunda
            </p>
          </div>
          {k.pending > 0 && (
            <Link to="/dokumanlar" className="btn primary">{k.pending} karar bekliyor</Link>
          )}
        </div>

        <div className="kpis">
          <Kpi label="Açık görev" value={k.open} note="onaylanmış, devam eden" />
          <Kpi label="Bu hafta teslim" value={k.due_week} note="önümüzdeki 7 gün" />
          <Kpi
            label="Geciken"
            value={k.overdue}
            note={k.overdue ? 'teslim tarihi geçti' : 'gecikme yok'}
            status={k.overdue ? 'critical' : undefined}
          />
          <Kpi label="Karar bekleyen öneri" value={k.pending} note="lider onayı bekliyor" />
          <Kpi
            label="Öneri isabeti"
            value={k.accuracy_pct === null ? '—' : `%${k.accuracy_pct}`}
            note={k.decided ? `${k.decided} kararda kişi değiştirilmedi` : 'henüz karar yok'}
          />
        </div>

        <div className="viz-grid">
          <Card
            title="Dokümandan işe"
            sub="Taranan cümlelerden tamamlanan işe kadar her aşama; yanında bir önceki aşamaya oranı."
            table={
              <table>
                <thead><tr><th>Aşama</th><th>Sayı</th><th>Önceki aşamaya oran</th></tr></thead>
                <tbody>
                  {d.funnel.map((f, i) => (
                    <tr key={f.stage}>
                      <td>{f.stage}</td>
                      <td>{f.count}</td>
                      <td>{i && d.funnel[i - 1].count ? `%${Math.round((f.count / d.funnel[i - 1].count) * 100)}` : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            }
          >
            <Funnel data={d.funnel} onTip={setTip} />
          </Card>

          <Card
            title="Model ne kadar güvenilir?"
            sub="Güven seviyesine göre, liderin öneriyi kişi değiştirmeden onayladığı oran. Yüksek güven gerçekten daha isabetli olmalı."
            table={
              <table>
                <thead><tr><th>Güven</th><th>Karar</th><th>Değiştirilmeden</th></tr></thead>
                <tbody>
                  {d.accuracy.map((r) => (
                    <tr key={r.level}><td>{r.label}</td><td>{r.total}</td><td>{r.unchanged_pct === null ? '—' : `%${r.unchanged_pct}`}</td></tr>
                  ))}
                </tbody>
              </table>
            }
          >
            <Calibration data={d.accuracy} onTip={setTip} />
          </Card>
        </div>

        <Card
          title="Ekip yükü"
          sub="Sprint kapasitesine göre. Turuncu kısım bu araçla verilen görevler."
          table={
            <table>
              <thead><tr><th>Kişi</th><th>Rol</th><th>Mevcut</th><th>Bu araçla</th><th>Toplam</th></tr></thead>
              <tbody>
                {d.load.map((r) => (
                  <tr key={r.id}><td>{r.name}</td><td>{r.role}</td><td>%{r.base}</td><td>%{r.added}</td><td>%{r.total}</td></tr>
                ))}
              </tbody>
            </table>
          }
        >
          <Load data={d.load} limit={d.limit} onTip={setTip} />
        </Card>

        <Card
          title="Teslim takvimi"
          sub="Önümüzdeki 14 gün. Noktaya tıklayınca görev açılır; içinde sayı olan nokta aynı gün birden fazla teslim demek."
          table={
            <table>
              <thead><tr><th>Görev</th><th>Kişi</th><th>Teslim</th><th>Durum</th></tr></thead>
              <tbody>
                {d.schedule.map((t) => (
                  <tr key={t.id}>
                    <td><Link to={`/gorev/${t.id}`}>{t.key}</Link> {t.title}</td>
                    <td>{t.assignee}</td>
                    <td>{fmt(d0(t.due))}</td>
                    <td>{t.overdue ? <span className="st-critical">▲ Gecikmiş</span> : 'Zamanında'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          }
        >
          <Schedule data={d.schedule} members={d.members} today={d.today} onTip={setTip} onOpen={open} />
        </Card>
      </div>

      {tip && (
        <div className="viz-tip" role="tooltip" style={{ left: Math.min(tip.x + 14, window.innerWidth - 300), top: tip.y + 14 }}>
          {tip.body}
        </div>
      )}
    </div>
  )
}
