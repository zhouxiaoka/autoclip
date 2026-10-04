/**
 * Calm Premium app primitives — see DESIGN.md → App Layer.
 * Small building blocks used by the redone screens.
 */
import React from 'react'
import { createPortal } from 'react-dom'
import { ConfigProvider } from 'antd'
import './ac.css'

/* ---------- Segmented ---------- */
export interface SegmentedOption<T extends string> { value: T; label: React.ReactNode }
export function Segmented<T extends string>({
  value, onChange, options, size, ariaLabel, className, disabled,
}: { value: T; onChange: (v: T) => void; options: SegmentedOption<T>[]; size?: 'sm'; ariaLabel?: string; className?: string; disabled?: boolean }) {
  return (
    <div className={`ac-seg${size === 'sm' ? ' ac-seg--sm' : ''}${className ? ` ${className}` : ''}`} role="group" aria-label={ariaLabel}>
      {options.map((o) => (
        <button key={o.value} type="button" disabled={disabled} aria-pressed={o.value === value} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  )
}

/* ---------- Button ---------- */
type BtnVariant = 'default' | 'cta' | 'text' | 'danger'
export const Btn: React.FC<
  React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: BtnVariant; size?: 'sm'; loading?: boolean }
> = ({ variant = 'default', size, loading, className = '', children, disabled, ...rest }) => {
  const cls = ['ac-btn']
  if (variant === 'cta') cls.push('ac-btn--cta')
  if (variant === 'text') cls.push('ac-btn--text')
  if (variant === 'danger') cls.push('ac-btn--text', 'ac-btn--danger')
  if (size === 'sm') cls.push('ac-btn--sm')
  if (className) cls.push(className)
  return (
    <button type="button" className={cls.join(' ')} disabled={disabled || loading} {...rest}>
      {loading && <span className="spin" aria-hidden />}
      {children}
    </button>
  )
}

/* ---------- Section ---------- */
export const Section: React.FC<{
  title: React.ReactNode
  count?: number | string
  description?: React.ReactNode
  right?: React.ReactNode
  id?: string
  children?: React.ReactNode
}> = ({ title, count, description, right, id, children }) => (
  <section className="ac-section" id={id}>
    <div className="ac-section-head">
      <div>
        <h2 className="ac-h2">
          {title}
          {count !== undefined && <span className="count">{count}</span>}
        </h2>
        {description && <p className="ac-sub">{description}</p>}
      </div>
      {right && <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: '0 0 auto' }}>{right}</div>}
    </div>
    {children}
  </section>
)

/* ---------- Setting row ---------- */
export const Row: React.FC<{
  label: React.ReactNode
  hint?: React.ReactNode
  control?: React.ReactNode
  wide?: boolean
  stack?: boolean
  top?: boolean
  children?: React.ReactNode
}> = ({ label, hint, control, wide, stack, top, children }) => (
  <div className={`ac-row${stack ? ' ac-row--stack' : ''}${top ? ' ac-row--top' : ''}`}>
    <div className="ac-row-label">
      <b>{label}</b>
      {hint && <small>{hint}</small>}
    </div>
    {(control || children) && (
      <div className={`ac-row-control${wide ? ' ac-row-control--wide' : ''}`}>{control ?? children}</div>
    )}
  </div>
)

/* ---------- Status ---------- */
export const StatusDot: React.FC<{ tone: 'ok' | 'error' | 'accent' | 'muted'; label?: React.ReactNode }> = ({ tone, label }) => (
  <span className={`ac-status${tone === 'error' ? ' ac-status--error' : ''}`}>
    <i className={`ac-dot ac-dot--${tone}`} />
    {label}
  </span>
)

export const ProgressLine: React.FC<{ percent: number }> = ({ percent }) => (
  <div className="ac-line"><i style={{ width: `${Math.max(0, Math.min(100, percent))}%` }} /></div>
)

/* ---------- Dialog ---------- */
export const Dialog: React.FC<{
  open: boolean
  onClose: () => void
  title: React.ReactNode
  description?: React.ReactNode
  footer?: React.ReactNode
  children?: React.ReactNode
}> = ({ open, onClose, title, description, footer, children }) => {
  const dialogRef = React.useRef<HTMLDivElement>(null)
  const titleId = React.useId()
  const closeRef = React.useRef(onClose)
  closeRef.current = onClose
  React.useEffect(() => {
    if (!open) return
    const previousFocus = document.activeElement as HTMLElement | null
    const focusable = () => Array.from(dialogRef.current?.querySelectorAll<HTMLElement>(
      'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    ) || []).filter(element => element.getClientRects().length > 0)
    ;(focusable()[0] || dialogRef.current)?.focus()
    const onKey = (e: KeyboardEvent) => {
      const dropdownOpen = !!document.querySelector('.ant-select-dropdown:not(.ant-select-dropdown-hidden)')
      if (e.key === 'Escape' && !dropdownOpen) closeRef.current()
      if (e.key !== 'Tab' || dropdownOpen) return
      const controls = focusable()
      const first = controls[0]
      const last = controls[controls.length - 1]
      if (!first) { e.preventDefault(); dialogRef.current?.focus(); return }
      if (e.shiftKey && (document.activeElement === first || !dialogRef.current?.contains(document.activeElement))) {
        e.preventDefault(); last.focus()
      } else if (!e.shiftKey && (document.activeElement === last || !dialogRef.current?.contains(document.activeElement))) {
        e.preventDefault(); first.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
      if (previousFocus?.isConnected) previousFocus.focus()
    }
  }, [open])
  if (!open || typeof document === 'undefined') return null
  // Portal to <body>: callers often live inside transformed / hover-lifted cards,
  // which would otherwise trap the fixed backdrop in their stacking context.
  // AntD popups also portal to body; keep this dialog's menus above its 1200 backdrop.
  return createPortal(
    <ConfigProvider theme={{ token: { zIndexPopupBase: 1300 } }}>
      <div className="ac-dialog-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
        <div ref={dialogRef} className="ac-dialog" role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}>
          <h3 id={titleId}>{title}</h3>
          {description && <p>{description}</p>}
          <div style={{ marginTop: 18 }}>{children}</div>
          {footer && <div className="ac-dialog-foot">{footer}</div>}
        </div>
      </div>
    </ConfigProvider>,
    document.body
  )
}

/* ---------- Icons (inline, 1.5px stroke — no icon font) ---------- */
const I: React.FC<{ d: string; size?: number; stroke?: number }> = ({ d, size = 14, stroke = 1.6 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <path d={d} />
  </svg>
)
export const Icon = {
  Back: (p?: { size?: number }) => <I size={p?.size} d="M15 18l-6-6 6-6" />,
  Play: (p?: { size?: number }) => <I size={p?.size} d="M7 5v14l11-7z" />,
  Plus: (p?: { size?: number }) => <I size={p?.size} d="M12 5v14M5 12h14" />,
  Down: (p?: { size?: number }) => <I size={p?.size} d="M12 4v12m0 0l-5-5m5 5l5-5M4 20h16" />,
  Up: (p?: { size?: number }) => <I size={p?.size} stroke={2} d="M12 19V5m0 0l-6 6m6-6l6 6" />,
  Trash: (p?: { size?: number }) => <I size={p?.size} d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" />,
  Refresh: (p?: { size?: number }) => <I size={p?.size} d="M20 12a8 8 0 1 1-2.3-5.7M20 4v5h-5" />,
  Chat: (p?: { size?: number }) => <I size={p?.size} d="M21 12a8 8 0 0 1-8 8H6l-3 3V12a8 8 0 0 1 8-8h2a8 8 0 0 1 8 8z" />,
  Check: (p?: { size?: number }) => <I size={p?.size} d="M5 12l5 5L20 7" />,
  Close: (p?: { size?: number }) => <I size={p?.size} d="M6 6l12 12M18 6L6 18" />,
  External: (p?: { size?: number }) => <I size={p?.size} d="M14 4h6v6M20 4l-9 9M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5" />,
}

/* ---------- helpers ---------- */
export const parseTimecode = (t?: string): number => {
  if (!t) return 0
  const parts = t.replace(',', '.').split(':')
  if (parts.length !== 3) return 0
  return (parseInt(parts[0]) || 0) * 3600 + (parseInt(parts[1]) || 0) * 60 + (parseFloat(parts[2]) || 0)
}
export const fmtDuration = (sec: number): string => {
  if (!sec || sec <= 0) return '0:00'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}
export const fmtClock = (t?: string): string => (t ? t.replace(',', '.').substring(0, 8).replace(/^00:/, '') : '')
