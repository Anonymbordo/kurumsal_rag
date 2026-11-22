import { Fragment, useEffect, useRef, useState, type ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
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
          <article className="card" key={t.id}>
            <div className="card-head">
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <span className="keytag">{t.key}</span>
                <h3>{t.title}</h3>
              </div>
              <span className={`badge ${t.tone}`}>{t.tag}</span>
            </div>
            <div className="meta-row">
              <span>Atayan: {t.assigned_by}</span>
              <span>Teslim: {t.due}</span>
              <span>Kaynak: {t.source}</span>
            </div>
            {t.note && <p className="note">{t.note}</p>}
            {t.document_id && (
              <div className="actions">
                <Link className="btn small" to={`/dokuman/${t.document_id}`}>Kaynağı aç</Link>
              </div>
            )}
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
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setError('')
    api.messages(convId).then((r) => {
      setConv(r.conversation)
      setMsgs(r.messages)
    }).catch((e) => setError((e as Error).message))
  }, [convId])

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [msgs.length])

  const send = async (text: string) => {
    setBusy(true)
    setError('')
    try {
      const r = await api.send(convId, text)
      setMsgs((m) => [...m, ...r.messages])
      refreshSidebar()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

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
          {busy && <p className="sources" aria-live="polite">Yanıt hazırlanıyor…</p>}
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
