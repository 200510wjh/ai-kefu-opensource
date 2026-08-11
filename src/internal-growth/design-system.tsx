import React from 'react';
import './design-tokens.css';

type Tone = 'neutral' | 'primary' | 'success' | 'warning' | 'danger';

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  disabled,
  onClick,
  type = 'button'
}: {
  children: React.ReactNode;
  variant?: 'primary' | 'secondary' | 'ghost';
  size?: 'sm' | 'md';
  disabled?: boolean;
  onClick?: () => void;
  type?: 'button' | 'submit';
}) {
  return (
    <button type={type} className={`igButton ${variant} ${size}`} disabled={disabled} onClick={onClick}>
      {children}
    </button>
  );
}

export function IconButton({
  label,
  children,
  disabled,
  onClick
}: {
  label: string;
  children: React.ReactNode;
  disabled?: boolean;
  onClick?: () => void;
}) {
  return (
    <button type="button" className="igIconButton" title={label} aria-label={label} disabled={disabled} onClick={onClick}>
      {children}
    </button>
  );
}

export function Panel({
  title,
  eyebrow,
  action,
  children,
  className = ''
}: {
  title: string;
  eyebrow?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`igPanel ${className}`}>
      <div className="igPanelHead">
        <div>
          {eyebrow && <p>{eyebrow}</p>}
          <h2>{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

export function MetricCard({
  label,
  value,
  icon,
  helper
}: {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  helper?: string;
}) {
  return (
    <div className="igMetricCard">
      <span>{icon}</span>
      <strong>{value}</strong>
      <b>{label}</b>
      {helper && <small>{helper}</small>}
    </div>
  );
}

export function StatusBadge({children, tone = 'neutral'}: {children: React.ReactNode; tone?: Tone}) {
  return <span className={`igStatusBadge ${tone}`}>{children}</span>;
}

export function SegmentedTabs<T extends string>({
  items,
  value,
  onChange
}: {
  items: Array<{value: T; label: string}>;
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div className="igSegmentedTabs">
      {items.map((item) => (
        <button type="button" key={item.value} className={item.value === value ? 'active' : ''} onClick={() => onChange(item.value)}>
          {item.label}
        </button>
      ))}
    </div>
  );
}

export function EmptyState({title, body}: {title: string; body?: string}) {
  return (
    <div className="igEmptyState">
      <strong>{title}</strong>
      {body && <span>{body}</span>}
    </div>
  );
}

export function FormField({
  label,
  children
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="igFormField">
      <span>{label}</span>
      {children}
    </label>
  );
}

export function Toolbar({children}: {children: React.ReactNode}) {
  return <div className="igToolbar">{children}</div>;
}

export function DataTable({children}: {children: React.ReactNode}) {
  return <div className="igDataTable">{children}</div>;
}
