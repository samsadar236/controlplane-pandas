import React, { forwardRef } from 'react'

// ===========================================================================
// Button
// ===========================================================================
export const Button = forwardRef(function Button(
  { variant = 'secondary', size = 'md', className = '', children, disabled, ...rest }, ref
) {
  const base =
    'inline-flex items-center justify-center gap-1.5 font-medium rounded-lg transition-all duration-200 ' +
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6b52c6]/30 ' +
    'disabled:opacity-40 disabled:cursor-not-allowed select-none whitespace-nowrap cursor-pointer'
  const variants = {
    primary:   'btn-primary',
    secondary: 'btn-ghost',
    ghost:     'bg-transparent text-gray-500 hover:text-[#6b52c6] hover:bg-gray-100',
    danger:    'btn-ghost text-red-500 border-red-200 hover:bg-red-50 hover:border-red-400',
    success:   'bg-green-500 text-white font-semibold hover:bg-green-600',
    link:      'text-[#6b52c6] hover:text-[#5843a8] underline-offset-2 hover:underline',
  }
  const sizes = {
    sm: 'h-8 px-3 text-[13px]',
    md: 'h-10 px-4 text-sm',
    lg: 'h-11 px-5 text-[15px]',
    icon: 'h-9 w-9 text-sm',
  }
  return (
    <button
      ref={ref}
      disabled={disabled}
      className={`${base} ${variants[variant]} ${sizes[size]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  )
})

// ===========================================================================
// Card / Surface
// ===========================================================================
export function Card({ className = '', children, ...rest }) {
  return (
    <div
      className={`go-card ${className}`}
      {...rest}
    >
      {children}
    </div>
  )
}

export function CardHeader({ title, description, action, className = '' }) {
  return (
    <div className={`flex items-start justify-between gap-4 px-5 py-4 border-b border-gray-100 ${className}`}>
      <div>
        <h3 className="text-[16px] font-semibold text-gray-900">{title}</h3>
        {description && <p className="mt-0.5 text-[12px] text-gray-500">{description}</p>}
      </div>
      {action}
    </div>
  )
}

export function CardBody({ className = '', children }) {
  return <div className={`px-5 py-4 ${className}`}>{children}</div>
}

// ===========================================================================
// Input + TextArea
// ===========================================================================
export const Input = forwardRef(function Input({ className = '', invalid, ...rest }, ref) {
  return (
    <input
      ref={ref}
      className={`block w-full h-10 px-3 text-sm text-gray-800 bg-white border rounded-md transition-all duration-200 placeholder:text-gray-400 outline-none
        ${invalid ? 'border-red-400 focus:ring-red-200 focus:border-red-400' : 'border-gray-300 focus:ring-[#6b52c6]/15 focus:border-[#6b52c6]'}
        focus:ring-2 ${className}`}
      {...rest}
    />
  )
})

export const TextArea = forwardRef(function TextArea({ className = '', rows = 3, invalid, ...rest }, ref) {
  return (
    <textarea
      ref={ref}
      rows={rows}
      className={`block w-full px-3 py-2.5 text-sm text-gray-800 bg-white border rounded-md transition-all duration-200 resize-y placeholder:text-gray-400 outline-none
        ${invalid ? 'border-red-400 focus:ring-red-200 focus:border-red-400' : 'border-gray-300 focus:ring-[#6b52c6]/15 focus:border-[#6b52c6]'}
        focus:ring-2 ${className}`}
      {...rest}
    />
  )
})

export function Select({ className = '', children, ...rest }) {
  return (
    <select
      className={`block w-full h-10 px-3 text-sm text-gray-800 bg-white border border-gray-300 rounded-md transition-all duration-200 outline-none
        focus:ring-2 focus:ring-[#6b52c6]/15 focus:border-[#6b52c6] cursor-pointer ${className}`}
      {...rest}
    >
      {children}
    </select>
  )
}

// ===========================================================================
// Field — label + control + hint pattern
// ===========================================================================
export function Field({ label, hint, error, required, children, className = '' }) {
  return (
    <label className={`block ${className}`}>
      {label && (
        <div className="mb-1.5 flex items-baseline gap-1">
          <span className="text-[12px] font-medium text-gray-600">{label}</span>
          {required && <span className="text-red-500 text-[11px]">*</span>}
        </div>
      )}
      {children}
      {error
        ? <p className="mt-1 text-[11px] text-red-500">{error}</p>
        : hint && <p className="mt-1 text-[11px] text-gray-400">{hint}</p>}
    </label>
  )
}

// ===========================================================================
// Badge / Pill
// ===========================================================================
export function Badge({ variant = 'neutral', children, className = '', ...rest }) {
  const variants = {
    neutral: 'bg-gray-100 text-gray-600 border-gray-200',
    brand:   'bg-[#f3f0ff] text-[#6b52c6] border-[#ddd6fe]',
    success: 'bg-green-50 text-green-700 border-green-200',
    warning: 'bg-amber-50 text-amber-700 border-amber-200',
    danger:  'bg-red-50 text-red-600 border-red-200',
    info:    'bg-blue-50 text-blue-600 border-blue-200',
  }
  return (
    <span className={`inline-flex items-center gap-1 px-2 h-5 rounded-full border text-[10px] uppercase tracking-widest font-medium ${variants[variant]} ${className}`} {...rest}>
      {children}
    </span>
  )
}

// ===========================================================================
// Stat — used in the audit metrics row
// ===========================================================================
export function Stat({ label, value, hint, accent }) {
  return (
    <div className="go-card p-5">
      <div className="text-[11px] uppercase tracking-[0.2em] text-gray-500">{label}</div>
      <div className={`mt-1 font-display text-[28px] ${accent || 'text-[#6b52c6]'}`}>{value}</div>
      {hint && <div className="mt-0.5 text-[11px] text-gray-400">{hint}</div>}
    </div>
  )
}

// ===========================================================================
// Empty state
// ===========================================================================
export function EmptyState({ title, description, action, icon }) {
  return (
    <div className="bg-white rounded-2xl w-full max-w-4xl mx-auto p-16 text-center card-shadow border border-gray-100 flex flex-col items-center justify-center min-h-[350px]">
      {icon && <div className="mx-auto mb-3 h-10 w-10 text-gray-300">{icon}</div>}
      <h2 className="text-2xl font-bold text-gray-900 mb-3">{title}</h2>
      {description && <p className="text-gray-600 text-base mb-8 max-w-md mx-auto leading-relaxed">{description}</p>}
      {action && <div>{action}</div>}
    </div>
  )
}

// ===========================================================================
// PageHeader
// ===========================================================================
export function PageHeader({ title, description, actions, step }) {
  return (
    <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-8">
      <div className="max-w-md">
        {step && <div className="text-[12px] font-medium text-[#6b52c6] mb-1">{step}</div>}
        <h1 className="text-3xl font-bold text-gray-900 mb-2">{title}</h1>
        {description && <p className="text-gray-600 text-sm leading-relaxed">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-3 shrink-0">{actions}</div>}
    </div>
  )
}

// ===========================================================================
// Keyboard hint chip
// ===========================================================================
export function Kbd({ children }) {
  return (
    <kbd className="inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded border border-gray-300 bg-gray-50 text-[11px] text-gray-500 font-medium">
      {children}
    </kbd>
  )
}
