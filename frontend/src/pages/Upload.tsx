import { useState, type DragEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useApp } from '../context'
import { IconLock, IconUpload } from '../icons'

const TYPES = [
  { id: 'meeting', label: 'Toplantı notu', hint: 'Kararlar ve aksiyon maddeleri' },
  { id: 'analysis', label: 'Analiz dokümanı', hint: 'Gereksinimler ve kapsam' },
  { id: 'spec', label: 'Şartname', hint: 'Teknik maddeler ve teslimatlar' },
]

export default function Upload() {
  const { me, org } = useApp()
  const navigate = useNavigate()
  const [file, setFile] = useState<File | null>(null)
  const [text, setText] = useState('')
  const [docType, setDocType] = useState('meeting')
  const [sprint, setSprint] = useState('Sprint 14')
  const [over, setOver] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  if (me && !me.is_lead) {
    return <div className="center-msg">Doküman yükleyip görev çıkarma şimdilik takım liderlerine açık.</div>
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setOver(false)
    const f = e.dataTransfer.files[0]
    if (f) setFile(f)
  }

  const submit = async () => {
    setError('')
    if (!file && !text.trim()) {
      setError('Bir dosya seçin ya da metni yapıştırın.')
      return
    }
    setBusy(true)
    try {
      const form = new FormData()
      if (file) form.append('file', file)
      else form.append('text', text)
      form.append('doc_type', docType)
      form.append('sprint', sprint)
      const doc = await api.uploadDocument(form)
      await api.extract(doc.id)
      navigate(`/dokuman/${doc.id}`)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="review-bg">
      <div className="page narrow">
        <ol className="steps" aria-label="Adımlar">
          <li className="on">1 · Doküman yükle</li>
          <li>2 · Görevleri incele ve onayla</li>
          <li>3 · Aktar</li>
        </ol>
        <h1 style={{ margin: 0, fontSize: 28 }}>Hangi dokümandan görev çıkaralım?</h1>
        <p style={{ margin: '6px 0 24px', color: 'var(--muted)', fontSize: 16 }}>
          Sistem görevleri çıkarır ve her biri için kişi önerir; son kararı siz verirsiniz.
        </p>

        <div className="cols">
          <div style={{ flex: '3 1 520px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 20 }}>
            <label
              className={`drop${over ? ' over' : ''}`}
              onDragOver={(e) => { e.preventDefault(); setOver(true) }}
              onDragLeave={() => setOver(false)}
              onDrop={onDrop}
            >
              <span style={{ color: 'var(--accent)' }}><IconUpload size={36} /></span>
              <b>{file ? file.name : 'Dosyayı buraya bırakın ya da seçin'}</b>
              <span style={{ fontSize: 14, color: 'var(--muted)' }}>PDF, DOCX, TXT, MD · en fazla 10 MB</span>
              <input type="file" accept=".pdf,.docx,.txt,.md" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </label>

            <label className="field">
              …ya da metni yapıştırın
              <textarea rows={5} value={text} onChange={(e) => setText(e.target.value)} disabled={!!file} />
            </label>

            <fieldset className="panel" style={{ margin: 0 }}>
              <legend style={{ fontSize: 14, fontWeight: 600, padding: '0 6px' }}>Doküman türü</legend>
              <div className="typepick">
                {TYPES.map((t) => (
                  <button key={t.id} type="button" className={docType === t.id ? 'on' : ''} onClick={() => setDocType(t.id)} aria-pressed={docType === t.id}>
                    <b>{t.label}</b>
                    <small>{t.hint}</small>
                  </button>
                ))}
              </div>
            </fieldset>

            <label className="field">
              Hedef sprint
              <input value={sprint} onChange={(e) => setSprint(e.target.value)} />
            </label>

            {error && <div className="error" role="alert">{error}</div>}
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
              <button type="button" className="btn" onClick={() => navigate('/dokuman/1')}>Örnek planlama notunu aç</button>
              <button type="button" className="btn primary" onClick={submit} disabled={busy}>
                {busy ? 'Görevler çıkarılıyor…' : 'Görevleri çıkar →'}
              </button>
            </div>
          </div>

          <aside style={{ flex: '2 1 320px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 16 }}>
            <section className="panel">
              <h2>Sistem ne yapar?</h2>
              <ul>
                <li>Dokümandaki işleri görev olarak çıkarır</li>
                <li>Uzmanlık, geçmiş işler ve iş yüküne göre kişi önerir</li>
                <li>Her görevi dokümandaki kaynağına bağlar</li>
                <li>Emin olmadığı görevleri açıkça işaretler</li>
              </ul>
            </section>
            <section className="panel">
              <h2>Ne yapamaz?</h2>
              <ul>
                <li>Ekip içi dinamikleri ve kişisel tercihleri bilmez</li>
                <li>İzin bilgisini yalnızca takvim bağlıysa görür</li>
                <li>Onayınız olmadan kimseye görev atamaz</li>
              </ul>
            </section>
            <section className="panel" style={{ background: '#eef1f5', border: 0 }}>
              <h2 style={{ display: 'flex', alignItems: 'center', gap: 8 }}><IconLock /> Veri nerede işleniyor?</h2>
              <p style={{ margin: 0, fontSize: 14, lineHeight: 1.6 }}>
                Doküman kurum içindeki sunucuda işlenir, dış API çağrısı yapılmaz. Model: <b>{org?.model_label}</b>
              </p>
            </section>
          </aside>
        </div>
      </div>
    </div>
  )
}
