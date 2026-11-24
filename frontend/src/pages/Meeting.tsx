import { Fragment, useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { useApp } from '../context'
import type { MeetingDetail } from '../types'
import { MEETING_STATUS } from './Meetings'

const SLICE_MS = 10_000 // her 10 sn'de bir parça yüklenir: tarayıcı kapanırsa en fazla 10 sn kaybolur

declare global {
  interface Window {
    JitsiMeetExternalAPI?: new (domain: string, options: Record<string, unknown>) => { dispose: () => void }
  }
}

/** Jitsi'nin gömme betiğini bir kez yükler. */
function loadJitsi(domain: string): Promise<void> {
  if (window.JitsiMeetExternalAPI) return Promise.resolve()
  return new Promise((resolve, reject) => {
    const s = document.createElement('script')
    s.src = `https://${domain}/external_api.js`
    s.async = true
    s.onload = () => resolve()
    s.onerror = () => reject(new Error(`Görüntülü görüşme sunucusuna ulaşılamadı (${domain})`))
    document.head.appendChild(s)
  })
}

/**
 * Katılımcının kendi mikrofonunu kaydeder ve parçaları sırayla sunucuya yükler.
 * Herkes yalnızca kendi sesini kaydettiği için "kim konuştu" bilgisi kesindir.
 */
function useMicRecorder(meetingId: number) {
  const [state, setState] = useState<'idle' | 'starting' | 'recording' | 'stopping'>('idle')
  const [uploaded, setUploaded] = useState(0)
  const [error, setError] = useState('')
  const rec = useRef<MediaRecorder | null>(null)
  const stream = useRef<MediaStream | null>(null)
  const queue = useRef<Promise<unknown>>(Promise.resolve())
  const seq = useRef(0)
  const rid = useRef<number | null>(null)

  const start = useCallback(async () => {
    setError('')
    setState('starting')
    try {
      const media = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      })
      const r = await api.startRecording(meetingId)
      rid.current = r.id
      seq.current = 0
      stream.current = media
      const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : ''
      const mr = new MediaRecorder(media, mime ? { mimeType: mime, audioBitsPerSecond: 32000 } : undefined)
      mr.ondataavailable = (e) => {
        if (!e.data.size || rid.current === null) return
        const n = seq.current++
        const id = rid.current
        // Parçalar sırayla yüklenir (webm akışı ancak sırayla birleşince çözülebilir)
        queue.current = queue.current
          .then(() => api.uploadChunk(id, n, e.data))
          .then(() => setUploaded((u) => u + e.data.size))
          .catch((err) => setError(`Kayıt parçası yüklenemedi: ${(err as Error).message}`))
      }
      mr.start(SLICE_MS)
      rec.current = mr
      setState('recording')
    } catch (e) {
      setError(
        (e as Error).name === 'NotAllowedError'
          ? 'Mikrofon izni verilmedi. Tarayıcının adres çubuğundan izin verin.'
          : (e as Error).message,
      )
      setState('idle')
    }
  }, [meetingId])

  /** Kaydı durdurur ve son parçanın da yüklenmesini bekler. */
  const stop = useCallback(async () => {
    const mr = rec.current
    if (!mr || mr.state === 'inactive') return
    setState('stopping')
    await new Promise<void>((resolve) => {
      mr.addEventListener('stop', () => resolve(), { once: true })
      mr.stop()
    })
    stream.current?.getTracks().forEach((t) => t.stop())
    await queue.current
    rec.current = null
    setState('idle')
  }, [])

  useEffect(() => () => {
    // sayfadan çıkılırsa kaydı kapat
    if (rec.current && rec.current.state !== 'inactive') rec.current.stop()
    stream.current?.getTracks().forEach((t) => t.stop())
  }, [])

  return { state, uploaded, error, start, stop }
}

/** Raporun basit markdown'ı: ##, -, **kalın**, _italik_. */
function md(text: string): ReactNode[] {
  const inline = (s: string) =>
    s.split(/(\*\*[^*]+\*\*|_[^_]+_)/g).map((p, i) =>
      p.startsWith('**') ? <strong key={i}>{p.slice(2, -2)}</strong> : p.startsWith('_') && p.endsWith('_') && p.length > 2 ? <em key={i}>{p.slice(1, -1)}</em> : <Fragment key={i}>{p}</Fragment>,
    )
  const out: ReactNode[] = []
  let items: string[] = []
  const flush = () => {
    if (items.length) out.push(<ul key={out.length}>{items.map((x, i) => <li key={i}>{inline(x)}</li>)}</ul>)
    items = []
  }
  for (const line of text.split('\n')) {
    const t = line.trim()
    if (t.startsWith('- ') || t.startsWith('* ')) {
      items.push(t.slice(2))
      continue
    }
    flush()
    if (!t) continue
    if (t.startsWith('# ')) out.push(<h2 key={out.length} style={{ margin: '0 0 4px', fontSize: 20 }}>{t.slice(2)}</h2>)
    else if (t.startsWith('## ')) out.push(<h3 key={out.length} style={{ margin: '14px 0 4px', fontSize: 15 }}>{t.slice(3)}</h3>)
    else out.push(<p key={out.length} style={{ margin: '4px 0' }}>{inline(t)}</p>)
  }
  flush()
  return out
}

export default function Meeting() {
  const { id } = useParams()
  const meetingId = Number(id)
  const { me } = useApp()
  const [m, setM] = useState<MeetingDetail | null>(null)
  const [error, setError] = useState('')
  const [consent, setConsent] = useState(false)
  const [ending, setEnding] = useState(false)
  const [tab, setTab] = useState<'report' | 'transcript'>('report')
  const jitsiRef = useRef<HTMLDivElement>(null)
  const rec = useMicRecorder(meetingId)

  const load = useCallback(() => api.meeting(meetingId).then(setM).catch((e) => setError((e as Error).message)), [meetingId])
  useEffect(() => {
    load()
  }, [load])

  // Canlı ya da işlenirken durumu izle (toplantıyı başkası bitirirse kayıt kapanır)
  useEffect(() => {
    if (!m || (m.status !== 'live' && m.status !== 'processing')) return
    const t = setInterval(load, m.status === 'live' ? 2500 : 3000)
    return () => clearInterval(t)
  }, [m?.status, load]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (m && m.status !== 'live' && rec.state === 'recording') rec.stop()
  }, [m?.status]) // eslint-disable-line react-hooks/exhaustive-deps

  // Jitsi görüşmesi
  useEffect(() => {
    if (!m || m.status !== 'live' || !m.jitsi_domain || !jitsiRef.current) return
    let api_: { dispose: () => void } | null = null
    let cancelled = false
    loadJitsi(m.jitsi_domain)
      .then(() => {
        if (cancelled || !window.JitsiMeetExternalAPI || !jitsiRef.current) return
        api_ = new window.JitsiMeetExternalAPI(m.jitsi_domain, {
          roomName: m.room,
          parentNode: jitsiRef.current,
          width: '100%',
          height: '100%',
          userInfo: { displayName: me?.name ?? '' },
          configOverwrite: { prejoinPageEnabled: false, disableDeepLinking: true },
        })
      })
      .catch((e) => setError((e as Error).message))
    return () => {
      cancelled = true
      api_?.dispose()
    }
  }, [m?.status, m?.jitsi_domain, m?.room, me?.name]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!m) return <div className="center-msg">{error || 'Yükleniyor…'}</div>

  const canEnd = !!me && (me.is_lead || me.id === m.created_by?.id)

  const end = async () => {
    setEnding(true)
    setError('')
    try {
      await rec.stop() // son parçalar yüklensin
      setM(await api.endMeeting(meetingId))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setEnding(false)
    }
  }

  const uploadFile = async (f: File) => {
    const form = new FormData()
    form.append('file', f)
    setError('')
    try {
      await api.uploadMeetingAudio(meetingId, form)
      load()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <div className="review-bg">
      <div className="page" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div className="card-head">
          <div>
            <Link to="/toplantilar" style={{ fontSize: 13, color: 'var(--muted)' }}>← Toplantılar</Link>
            <h1 style={{ margin: '2px 0 0', fontSize: 22 }}>{m.title}</h1>
            <div style={{ fontSize: 13, color: 'var(--muted)' }}>
              {m.participants.map((p) => p.name).join(', ')} · <b>{MEETING_STATUS[m.status]}</b>
            </div>
          </div>
          {m.status === 'live' && canEnd && (
            <button type="button" className="btn primary" onClick={end} disabled={ending}>
              {ending ? 'Kayıtlar gönderiliyor…' : 'Toplantıyı bitir ve raporla'}
            </button>
          )}
        </div>
        {error && <div className="error" role="alert">{error}</div>}

        {m.status === 'live' && (
          <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'stretch' }}>
            <div className="panel" style={{ flex: '3 1 560px', minHeight: 480, padding: 0, overflow: 'hidden', display: 'flex' }}>
              {m.jitsi_domain ? (
                <div ref={jitsiRef} style={{ flex: 1, minHeight: 480 }} />
              ) : (
                <div style={{ padding: 20, fontSize: 14, color: 'var(--muted)', alignSelf: 'center' }}>
                  Görüntülü görüşme sunucusu ayarlanmadı (<code>GA_JITSI_DOMAIN</code>). Toplantıyı odada yapıp
                  sağdaki kayıtla ya da hazır bir ses dosyasıyla devam edebilirsiniz.
                </div>
              )}
            </div>

            <aside className="panel" style={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column', gap: 12 }}>
              <h2 style={{ margin: 0 }}>Konuşma kaydı</h2>
              <p style={{ margin: 0, fontSize: 13, color: 'var(--ink-2)' }}>
                Görev çıkarmak için yalnızca <b>kendi mikrofonunuz</b> kaydedilir ve kurum sunucusunda yazıya dökülür.
                Ses dosyası, yazıya döküldükten sonra silinir.
              </p>
              {rec.state === 'idle' ? (
                <>
                  <label style={{ display: 'flex', gap: 8, fontSize: 13, alignItems: 'flex-start' }}>
                    <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
                    Konuşmalarımın bu toplantının raporu ve görev önerileri için yazıya dökülmesini kabul ediyorum.
                  </label>
                  <button type="button" className="btn primary" disabled={!consent} onClick={rec.start}>
                    ● Kaydı başlat
                  </button>
                </>
              ) : (
                <>
                  <p className="inline-note" role="status">
                    {rec.state === 'recording' ? '● Kayıt sürüyor' : rec.state === 'starting' ? 'Mikrofon açılıyor…' : 'Kayıt kapatılıyor…'}
                    {' · '}
                    {(rec.uploaded / 1024).toFixed(0)} KB gönderildi
                  </p>
                  {rec.state === 'recording' && (
                    <button type="button" className="btn" onClick={rec.stop}>Kaydı durdur</button>
                  )}
                </>
              )}
              {rec.error && <div className="error" role="alert">{rec.error}</div>}

              <div style={{ borderTop: '1px solid var(--line)', paddingTop: 10, fontSize: 13 }}>
                <b>Kayıt gönderenler</b>
                {m.recordings.length === 0 && <div style={{ color: 'var(--muted)' }}>Henüz kimse kayıt başlatmadı.</div>}
                {m.recordings.map((r) => (
                  <div key={r.id} style={{ color: 'var(--ink-2)' }}>
                    {r.speaker} · {(r.bytes / 1024).toFixed(0)} KB
                  </div>
                ))}
              </div>
              <label style={{ fontSize: 13, color: 'var(--muted)' }}>
                Hazır kayıt yükle (odadaki tek cihaz, Teams kaydı…):
                <input type="file" accept="audio/*,video/mp4,video/webm" onChange={(e) => e.target.files?.[0] && uploadFile(e.target.files[0])} />
              </label>
            </aside>
          </div>
        )}

        {m.status === 'processing' && (
          <div className="panel" role="status">
            <h2>Toplantı işleniyor</h2>
            <p style={{ margin: 0, fontSize: 14 }}>{m.progress || 'Sırada…'}</p>
            <p style={{ margin: '6px 0 0', fontSize: 13, color: 'var(--muted)' }}>
              CPU'da yazıya dökme, toplantı süresinin yaklaşık yarısı ile bir katı kadar sürer. Sayfadan ayrılabilirsiniz.
            </p>
          </div>
        )}

        {m.status === 'failed' && (
          <div className="panel">
            <h2>İşlenemedi</h2>
            <div className="error">{m.error}</div>
            {canEnd && (
              <button type="button" className="btn" style={{ marginTop: 10 }} onClick={() => api.retryMeeting(meetingId).then(setM)}>
                Yeniden dene
              </button>
            )}
          </div>
        )}

        {m.status === 'done' && (
          <>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <button type="button" className={`choice${tab === 'report' ? ' on' : ''}`} onClick={() => setTab('report')}>Rapor</button>
              <button type="button" className={`choice${tab === 'transcript' ? ' on' : ''}`} onClick={() => setTab('transcript')}>
                Döküm ({m.transcript.length})
              </button>
              <span style={{ flex: 1 }} />
              {m.document_id && me?.is_lead && (
                <Link className="btn primary" to={`/dokuman/${m.document_id}`}>Görev önerilerini incele ve onayla</Link>
              )}
            </div>
            {tab === 'report' ? (
              <article className="panel" style={{ fontSize: 14, lineHeight: 1.6 }}>{md(m.report)}</article>
            ) : (
              <article className="panel" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {m.transcript.map((u, i) => (
                  <div key={i} style={{ fontSize: 14, lineHeight: 1.55 }}>
                    <span style={{ color: 'var(--muted)', fontVariantNumeric: 'tabular-nums' }}>[{u.ts}]</span>{' '}
                    <b>{u.speaker}:</b> {u.text}
                  </div>
                ))}
              </article>
            )}
          </>
        )}
      </div>
    </div>
  )
}
