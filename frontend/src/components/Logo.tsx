import { useApp } from '../context'
import { IconImage } from '../icons'

/** Kurum logosu: GA_ORG_LOGO_URL ayarlıysa görsel, değilse yer tutucu. */
export function Logo({ size }: { size: 'sm' | 'lg' }) {
  const { org } = useApp()
  if (org?.logo_url) return <img className={`logo-img ${size}`} src={org.logo_url} alt={org.name} />
  if (size === 'sm') return <div className="logo-slot sm" aria-hidden="true">LOGO</div>
  return (
    <div className="logo-slot lg" role="img" aria-label="Kurum logosu alanı">
      <IconImage size={22} />[KURUM LOGOSU]
    </div>
  )
}
