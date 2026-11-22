const LABELS = { 3: 'Yüksek güven', 2: 'Orta güven', 1: 'Düşük güven' } as const

export function Confidence({ level, label = true }: { level: 1 | 2 | 3; label?: boolean }) {
  return (
    <span className={`conf l${level}`}>
      <span className="bars" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
      {label ? LABELS[level] : <span className="sr-only">{LABELS[level]}</span>}
    </span>
  )
}
