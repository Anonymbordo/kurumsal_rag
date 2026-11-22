import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { Composer } from '../components/Composer'
import { Logo } from '../components/Logo'
import { useApp } from '../context'

const SUGGESTIONS = [
  { q: 'Bugün bana verilen görevler ne?', d: 'Atamaların ve teslim tarihleri' },
  { q: 'Benimle paylaşılan dokümanlar neler?', d: 'Son 7 günde gelen dosyalar' },
  { q: 'Bu hafta neler teslim edilecek?', d: 'Önümüzdeki 7 gündeki teslimlerin' },
]

export default function Home() {
  const { me, refreshSidebar } = useApp()
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const start = async (text: string) => {
    setBusy(true)
    setError('')
    try {
      const r = await api.startConversation(text)
      refreshSidebar()
      navigate(`/c/${r.conversation.id}`)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const first = me?.name.split(' ')[0]
  return (
    <main className="home">
      <Logo size="lg" />
      <div>
        <h1>Merhaba{first ? ` ${first}` : ''}, bugün neye bakalım?</h1>
        <p className="sub">Görevlerini, seninle paylaşılan dokümanları ve teslim tarihlerini sorabilirsin.</p>
      </div>
      <Composer onSend={start} busy={busy} />
      {error && <div className="error" role="alert">{error}</div>}
      <div className="suggestions">
        {SUGGESTIONS.map((s) => (
          <button key={s.q} type="button" className="suggestion" onClick={() => start(s.q)} disabled={busy}>
            <b>{s.q}</b>
            <span>{s.d}</span>
          </button>
        ))}
        {me?.is_lead && (
          <Link to="/yukle" className="suggestion">
            <b>Toplantı notundan görev çıkar</b>
            <span>Takım liderleri için · öneri + onay akışı</span>
          </Link>
        )}
      </div>
    </main>
  )
}
