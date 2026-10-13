import './Button.css'

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  disabled = false,
  loading = false,
  onClick,
  type = 'button',
  id,
  className = '',
  ...rest
}) {
  return (
    <button
      type={type}
      id={id}
      className={`btn btn-${variant} btn-${size} ${className} ${loading ? 'loading' : ''}`}
      disabled={disabled || loading}
      onClick={onClick}
      {...rest}
    >
      {loading ? <span className="btn-spinner" aria-hidden="true" /> : null}
      {children}
    </button>
  )
}
