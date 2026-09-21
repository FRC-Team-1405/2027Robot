import { useEffect, useState } from 'react';

interface Props {
  value: number;
  onCommit: (v: number) => void;
  min?: number;
  max?: number;
  step?: number;
  decimals?: number;
  label: string;
  className?: string;
}

/** A number box you can type in freely: it only commits (and clamps) on Enter or blur, so half-typed
 *  values like "3." never reach the plan. Escape puts the old value back. */
export function NumField({ value, onCommit, min, max, step = 0.1, decimals = 2, label, className }: Props) {
  const fmt = (v: number) => String(Number(v.toFixed(decimals)));
  const [text, setText] = useState(fmt(value));
  const [focused, setFocused] = useState(false);
  useEffect(() => {
    if (!focused) setText(fmt(value));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, focused]);

  const commit = () => {
    const v = Number(text);
    if (text.trim() === '' || !Number.isFinite(v)) {
      setText(fmt(value));
      return;
    }
    const clamped = Math.min(max ?? Infinity, Math.max(min ?? -Infinity, v));
    setText(fmt(clamped));
    if (clamped !== value) onCommit(clamped);
  };

  return (
    <input
      className={`num ${className ?? ''}`}
      type="text"
      inputMode="decimal"
      aria-label={label}
      value={text}
      data-step={step}
      onFocus={(e) => {
        setFocused(true);
        e.currentTarget.select();
      }}
      onBlur={() => {
        setFocused(false);
        commit();
      }}
      onChange={(e) => setText(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === 'Enter') e.currentTarget.blur();
        else if (e.key === 'Escape') {
          setText(fmt(value));
          e.currentTarget.blur();
        } else if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
          e.preventDefault();
          const v = Number(text);
          const next = (Number.isFinite(v) ? v : value) + (e.key === 'ArrowUp' ? step : -step) * (e.shiftKey ? 10 : 1);
          const clamped = Math.min(max ?? Infinity, Math.max(min ?? -Infinity, next));
          setText(fmt(clamped));
          onCommit(clamped);
        }
      }}
    />
  );
}
