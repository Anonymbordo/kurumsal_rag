import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useApp } from '../context'
import type { DocListItem } from '../types'

const TYPE_LABELS: Record<string, string> = { meeting: 'Toplantı notu', analysis: 'Analiz', spec: 'Şartname' }

/** Ekibin yüklediği dokümanlar: aç ya da sil. */
export default function Documents() {
  const { me, refreshSidebar } = useApp()
  const [docs, setDocs] = useState<DocListItem[] | null>(null)
  const [confirm, setConfirm] = useState<number | null>(null)
  const [note, setNote] = useState('')
  const [error, setError] = useState('')

  const load = () => api.documents().then(setDocs).catch((e) => setError((e as Error).message))
  useEffect(() => {
    if (me?.is_lead) load()
  }, [me])

  if (me && !me.is_lead) return <div className="center-msg">Doküman listesi takım liderlerine açık.</div>
  if (!docs) return <div className="center-msg">{error || 'Yükleniyor…'}</div>

  const remove = async (d: DocListItem) => {
    setError('')
    try {
      const r = await api.deleteDocument(d.id)
      setNote(
        `"${d.title}" silindi.` +
          (r.kept_tasks ? ` Aktarılmış ${r.kept_tasks} görev kişilerin iş listesinde kalmaya devam ediyor.` : ''),
      )
      setConfirm(null)
      await load()
      refreshSidebar()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <div className="review-bg">
      <div className="page narrow" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div className="card-head">
          <div>
            <h1 style={{ margin: 0, fontSize: 24 }}>Dokümanlar</h1>
            <p style={{ margin: '4px 0 0', color: 'var(--muted)', fontSize: 14 }}>
              Silinen dokümanın bekleyen önerileri de silinir. Aktarılmış görevler kişilerde kalır.
            </p>
          </div>
          <Link to="/yukle" className="btn primary">Yeni doküman yükle</Link>
        </div>
        {note && <p className="inline-note" role="status">{note}</p>}
        {error && <div className="error" role="alert">{error}</div>}
        {docs.length === 0 && <div className="panel" style={{ padding: 20 }}>Henüz doküman yok.</div>}
        {docs.map((d) => (
          <div key={d.id} className="card">
            <div className="card-head">
              <div style={{ minWidth: 0 }}>
                <Link to={`/dokuman/${d.id}`} style={{ fontWeight: 600, fontSize: 15 }}>{d.title}</Link>
                <div style={{ fontSize: 13, color: 'var(--muted)' }}>
                  {TYPE_LABELS[d.doc_type] ?? d.doc_type} ·{' '}
                  {new Date(d.created_at).toLocaleDateString('tr-TR', { day: 'numeric', month: 'long', year: 'numeric' })} ·{' '}
                  {d.counts.pending} bekleyen, {d.counts.accepted} onaylı, {d.counts.active} aktarılmış
                </div>
              </div>
              {confirm === d.id ? (
                <div className="actions">
                  <span style={{ fontSize: 13, color: 'var(--warn-ink)' }}>Silinsin mi?</span>
                  <button type="button" className="btn small" onClick={() => setConfirm(null)}>Vazgeç</button>
                  <button type="button" className="btn small primary" onClick={() => remove(d)}>Evet, sil</button>
                </div>
              ) : (
                <button type="button" className="btn small" onClick={() => setConfirm(d.id)}>Sil</button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
