import { useState, type FormEvent, type KeyboardEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApp } from '../context'
import { IconArrowUp, IconClip } from '../icons'

interface Props {
  onSend: (text: string) => Promise<void> | void
  placeholder?: string
  rows?: number
  busy?: boolean
}

export function Composer({ onSend, placeholder = 'Bir soru sor ya da doküman ekle…', rows = 2, busy }: Props) {
  const [text, setText] = useState('')
  const { me } = useApp()
  const navigate = useNavigate()

  const submit = async (e?: FormEvent) => {
    e?.preventDefault()
    const t = text.trim()
    if (!t || busy) return
    setText('')
    await onSend(t)
  }
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <form className="composer" onSubmit={submit}>
      <label className="sr-only" htmlFor="composer-input">Mesaj</label>
      <textarea
        id="composer-input"
        rows={rows}
        placeholder={placeholder}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKey}
      />
      <div className="row">
        <div className="left">
          <button
            type="button"
            className="pill"
            onClick={() => navigate('/yukle')}
            disabled={!me?.is_lead}
            title={me?.is_lead ? 'Doküman yükle ve görev çıkar' : 'Doküman yükleme şimdilik takım liderlerine açık'}
          >
            <IconClip size={15} />
            Dosya ekle
          </button>
          <span className="pill flat">Kaynaklar: İş takibi · Paylaşılan dokümanlar</span>
        </div>
        <button type="submit" className="send" aria-label="Gönder" disabled={!text.trim() || busy}>
          <IconArrowUp size={18} />
        </button>
      </div>
    </form>
  )
}
