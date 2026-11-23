import { useEffect, useState } from 'react'
import { api } from '../api'
import { useApp } from '../context'
import { IconLock, IconUpload } from '../icons'
import type { LabelPreview } from '../types'

type Label = 'task' | 'not_task' | 'ambiguous' | null
const OPTIONS: { id: Exclude<Label, null>; text: string }[] = [
  { id: 'task', text: 'Görev' },
  { id: 'not_task', text: 'Değil' },
  { id: 'ambiguous', text: 'Belirsiz' },
]

export default function Labeling() {
  const { me } = useApp()
  const [file, setFile] = useState<File | null>(null)
  const [text, setText] = useState('')
  const [split, setSplit] = useState<'train' | 'test'>('train')
  const [names, setNames] = useState('')
  const [anon, setAnon] = useState(true)
  const [preview, setPreview] = useState<LabelPreview | null>(null)
  const [labels, setLabels] = useState<Label[]>([])
  const [title, setTitle] = useState('')
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [stats, setStats] = useState<{ train_sentences: number; test_documents: number } | null>(null)

  useEffect(() => {
    if (me?.is_lead) api.labelStats().then(setStats)
  }, [me, msg])

  if (me && !me.is_lead) return <div className="center-msg">Veri etiketleme şimdilik takım liderlerine açık.</div>

  const load = async () => {
    setError('')
    setMsg('')
    if (!file && !text.trim()) return setError('Bir dosya seçin ya da metin yapıştırın.')
    setBusy(true)
    try {
      const form = new FormData()
      if (file) form.append('file', file)
      else form.append('text', text)
      form.append('split', split)
      form.append('names', names)
      form.append('do_anonymize', String(anon))
      const p = await api.labelPreview(form)
      setPreview(p)
      setTitle(p.title)
      // Eğitimde modelin tahmini ön-doldurulur (hız); testte boş başlar (kör etiketleme).
      setLabels(p.sentences.map((_, i) => (p.suggestions ? (p.suggestions[i] >= 0.5 ? 'task' : 'not_task') : null)))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const save = async () => {
    if (!preview) return
    if (labels.some((l) => l === null)) return setError('Her cümleyi etiketleyin (emin değilseniz "Belirsiz").')
    setBusy(true)
    setError('')
    try {
      const r = await api.labelSave({ title, split, text: preview.text, sentences: preview.sentences, labels: labels as string[] })
      setMsg(`Kaydedildi: ${r.saved} · ${r.sentences} cümle, ${r.tasks} görev.`)
      setPreview(null)
      setFile(null)
      setText('')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const done = labels.filter((l) => l !== null).length
  return (
    <div className="review-bg">
      <div className="page narrow">
        <h1 style={{ margin: 0, fontSize: 26 }}>Veri etiketleme</h1>
        <p style={{ margin: '6px 0 20px', color: 'var(--muted)', fontSize: 15 }}>
          Gerçek dokümanları modelin eğitim ya da test verisine dönüştürün. Mevcut veri:{' '}
          <b>{stats?.train_sentences ?? '…'}</b> eğitim cümlesi, <b>{stats?.test_documents ?? '…'}</b> test dokümanı.
        </p>

        {!preview && (
          <div className="cols">
            <div style={{ flex: '3 1 520px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 16 }}>
              <label className="drop">
                <span style={{ color: 'var(--accent)' }}><IconUpload size={32} /></span>
                <b>{file ? file.name : 'Doküman seçin'}</b>
                <span style={{ fontSize: 13, color: 'var(--muted)' }}>PDF, DOCX, TXT, MD</span>
                <input type="file" accept=".pdf,.docx,.txt,.md" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
              </label>
              <label className="field">
                …ya da metni yapıştırın
                <textarea rows={4} value={text} onChange={(e) => setText(e.target.value)} disabled={!!file} />
              </label>
              <fieldset className="panel" style={{ margin: 0 }}>
                <legend style={{ fontSize: 14, fontWeight: 600, padding: '0 6px' }}>Nereye eklensin?</legend>
                <div className="typepick">
                  <button type="button" className={split === 'train' ? 'on' : ''} aria-pressed={split === 'train'} onClick={() => setSplit('train')}>
                    <b>Eğitim verisi</b>
                    <small>Modelin tahmini ön-doldurulur, siz düzeltirsiniz</small>
                  </button>
                  <button type="button" className={split === 'test' ? 'on' : ''} aria-pressed={split === 'test'} onClick={() => setSplit('test')}>
                    <b>Test verisi (kör)</b>
                    <small>Model tahmini gösterilmez; yalnızca ölçüm için</small>
                  </button>
                </div>
              </fieldset>
              {error && <div className="error" role="alert">{error}</div>}
              {msg && <div className="note" role="status">{msg}</div>}
              <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <button type="button" className="btn primary" onClick={load} disabled={busy}>
                  {busy ? 'Hazırlanıyor…' : 'Cümlelere ayır →'}
                </button>
              </div>
            </div>
            <aside className="panel" style={{ flex: '2 1 300px', minWidth: 0 }}>
              <h2 style={{ display: 'flex', alignItems: 'center', gap: 8 }}><IconLock /> KVKK: anonimleştirme</h2>
              <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 14, marginBottom: 12 }}>
                <input type="checkbox" checked={anon} onChange={(e) => setAnon(e.target.checked)} />
                E-posta, telefon, TCKN ve IBAN'ı maskele
              </label>
              <label className="field">
                Maskelenecek kişi adları
                <textarea rows={4} placeholder={'Her satıra bir ad\nAhmet Yılmaz\nZeynep Kaya'} value={names} onChange={(e) => setNames(e.target.value)} />
              </label>
              <p style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.5, margin: '10px 0 0' }}>
                Adlar "Kişi-1", "Kişi-2" olarak değiştirilir. Kural tabanlıdır: kaydetmeden önce metni gözle kontrol edin.
              </p>
            </aside>
          </div>
        )}

        {preview && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div className="panel summary">
              <label className="field" style={{ flex: '1 1 260px' }}>
                Doküman adı
                <input value={title} onChange={(e) => setTitle(e.target.value)} />
              </label>
              <div style={{ fontSize: 14, color: 'var(--muted)' }}>
                {split === 'test' ? 'Test (kör)' : 'Eğitim'} · {done}/{labels.length} etiketlendi
                {Object.keys(preview.anonymized).length > 0 &&
                  ' · maskelenen: ' + Object.entries(preview.anonymized).map(([k, v]) => `${k} ${v}`).join(', ')}
              </div>
            </div>
            {preview.sentences.map((s, i) => (
              <div key={i} className="card" style={{ flexDirection: 'row', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                <span className="num" aria-hidden="true">{i + 1}</span>
                <span style={{ flex: '1 1 320px', minWidth: 0, fontSize: 14, lineHeight: 1.5 }}>{s}</span>
                {preview.suggestions && (
                  <span className="ws-chip" title="Modelin görev olasılığı">%{Math.round(preview.suggestions[i] * 100)}</span>
                )}
                <div className="choices" role="radiogroup" aria-label={`Cümle ${i + 1} etiketi`}>
                  {OPTIONS.map((o) => (
                    <button
                      key={o.id}
                      type="button"
                      role="radio"
                      aria-checked={labels[i] === o.id}
                      className={`choice${labels[i] === o.id ? ' on' : ''}`}
                      onClick={() => setLabels((ls) => ls.map((l, j) => (j === i ? o.id : l)))}
                    >
                      {o.text}
                    </button>
                  ))}
                </div>
              </div>
            ))}
            {error && <div className="error" role="alert">{error}</div>}
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
              <button type="button" className="btn" onClick={() => setPreview(null)}>Vazgeç</button>
              <button type="button" className="btn primary" onClick={save} disabled={busy}>
                Kaydet ({split === 'test' ? 'test verisine' : 'eğitim verisine'})
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
