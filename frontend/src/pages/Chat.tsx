import { Fragment, useEffect, useRef, useState, type ReactNode } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { Composer } from '../components/Composer'
import { Logo } from '../components/Logo'
import { useApp } from '../context'
import { IconCheckBox, IconFile } from '../icons'
import type { Block, ChatMessage, Conversation } from '../types'

/** **kalın** işaretini destekleyen basit metin biçimlendirme. */
function rich(text: string): ReactNode[] {
  return text.split('\n\n').map((para, i) => (
    <p key={i}>
      {para.split(/(\*\*[^*]+\*\*)/g).map((part, j) =>
        part.startsWith('**') && part.endsWith('**') ? <strong key={j}>{part.slice(2, -2)}</strong> : <Fragment key={j}>{part}</Fragment>,
      )}
    </p>
  ))
}

function BlockView({ block }: { block: Block }) {
  if (block.type === 'tasks') {
    return (
      <>
        {block.items.map((t) => (
          <article className="card taskcard" key={t.id}>
            <div className="card-head">
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                <span className="keytag">{t.key}</span>
                <h3 className="oneline">{t.title}</h3>
              </div>
              <span className={`badge ${t.tone}`}>{t.tag}</span>
            </div>
            <div className="meta-row">
              <span>Teslim: <b>{t.due}</b></span>
              <span>Atayan: {t.assigned_by}</span>
            </div>
            {t.note && <p className="note">{t.note}</p>}
            <div className="actions">
              <Link className="btn small" to={`/gorev/${t.id}`}>Görevi aç</Link>
            </div>
          </article>
        ))}
      </>
    )
  }
  return (
    <>
      {block.items.map((d) => (
        <div className="card" key={d.id} style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
          <span style={{ color: 'var(--muted)' }}><IconFile size={22} /></span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 14, fontWeight: 600 }}>{d.title}</div>
            <div className="meta-row">
              <span>{d.shared_by} paylaştı</span>
              <span>{new Date(d.at).toLocaleString('tr-TR', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })}</span>
              {d.related && <span>{d.related} ile ilişkili</span>}
            </div>
          </div>
          <Link className="btn small" to={`/dokuman/${d.id}`}>Aç</Link>
        </div>
      ))}
    </>
  )
}

const FOLLOW_UPS = ['Bu hafta neler teslim edilecek?', 'Benimle paylaşılan dokümanlar neler?']

export default function Chat() {
  const { id } = useParams()
  const convId = Number(id)
  const { refreshSidebar } = useApp()
  const [conv, setConv] = useState<Conversation | null>(null)
  const [msgs, setMsgs] = useState<ChatMessage[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  // Akış sırasında: gönderilen soru ve o ana kadar gelen cevap parçaları
  const [live, setLive] = useState<{ q: string; a: string } | null>(null)
  const end = useRef<HTMLDivElement>(null)
  const location = useLocation()
  const navigate = useNavigate()
  const startedFor = useRef<number | null>(null)

  const send = async (text: string) => {
    setBusy(true)
    setError('')
    setLive({ q: text, a: '' })
    try {
      const saved = await api.streamMessage(convId, text, (piece) =>
        setLive((l) => (l ? { ...l, a: l.a + piece } : l)),
      )
      setMsgs((m) => [...m, ...saved])
      refreshSidebar()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLive(null)
      setBusy(false)
    }
  }

  useEffect(() => {
    setError('')
    const pending = (location.state as { pending?: string } | null)?.pending
    api.messages(convId).then((r) => {
      setConv(r.conversation)
      setMsgs(r.messages)
      // Ana sayfadan gelen ilk soru: bir kez gönder, sayfa yenilenince tekrar gönderme
      if (pending && r.messages.length === 0 && startedFor.current !== convId) {
        startedFor.current = convId
        navigate(location.pathname, { replace: true, state: null })
        send(pending)
      }
    }).catch((e) => setError((e as Error).message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [convId])

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [msgs.length, live?.a.length])

  const last = msgs[msgs.length - 1]
  return (
    <>
      <header className="topbar">
        <h1>{conv?.title ?? 'Sohbet'}</h1>
        <Logo size="sm" />
      </header>
      <div className="thread">
        <div className="thread-inner">
          {msgs.map((m) =>
            m.role === 'user' ? (
              <div className="bubble-user" key={m.id}>{m.text}</div>
            ) : (
              <div className="bot" key={m.id}>
                <div className="bot-icon" aria-hidden="true"><IconCheckBox /></div>
                <div className="bot-body">
                  {rich(m.text)}
                  {m.blocks.map((b, i) => <BlockView key={i} block={b} />)}
                  {m.sources.length > 0 && <p className="sources">Kaynaklar: {m.sources.join(' · ')}</p>}
                </div>
              </div>
            ),
          )}
          {live && (
            <>
              <div className="bubble-user">{live.q}</div>
              <div className="bot">
                <div className="bot-icon" aria-hidden="true"><IconCheckBox /></div>
                <div className="bot-body" aria-live="polite">
                  {live.a ? rich(live.a + ' ▍') : <p className="sources">Kayıtlar taranıyor, model düşünüyor…</p>}
                </div>
              </div>
            </>
          )}
          {error && <div className="error" role="alert">{error}</div>}
          {last?.role === 'assistant' && !busy && (
            <div className="choices">
              {FOLLOW_UPS.map((f) => (
                <button key={f} type="button" className="choice" onClick={() => send(f)}>{f}</button>
              ))}
            </div>
          )}
          <div ref={end} />
        </div>
      </div>
      <div className="composer-dock">
        <Composer onSend={send} busy={busy} placeholder="Devam et…" rows={1} />
      </div>
    </>
  )
}
