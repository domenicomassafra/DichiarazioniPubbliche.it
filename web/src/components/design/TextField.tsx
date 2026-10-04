/**
 * Dichiarazioni Pubbliche — Design System v1 · TextField
 *
 * The `SearchField` from the UX-v2 grammar, and every other single-purpose
 * text input in the product.
 *
 * PRODUCT BOUNDARY — THIS SEARCHES THE RECORD
 * The public search queries already-published public records. It is not a
 * prompt composer and it must never start a new analysis. The component
 * therefore has no `onAsk`, no model selector, and no streaming affordance;
 * if a future need appears it is a different product surface, not a prop
 * added here.
 *
 * A11Y
 * - A real `<form>` with a real submit button, so Enter works without a
 *   keydown handler and a screen reader announces a search landmark.
 * - The label is visually hidden but present. A placeholder is never the
 *   only name: placeholders vanish on focus and on input.
 * - `aria-describedby` wires the error message, and `aria-invalid` marks the
 *   field, so the error is announced rather than merely drawn.
 * - The magnifier is `aria-hidden`; the accessible name comes from the label.
 */

import { useId, type FormEvent, type ReactNode } from "react";
import { cx } from "./shared";

export interface TextFieldProps {
  /** Visually hidden. The field's accessible name. */
  label: string;
  name: string;
  value: string;
  onChange: (value: string) => void;
  onSubmit?: () => void;
  placeholder?: string;
  /** Names the problem and the recovery. Never a bare "invalid". */
  error?: string;
  /** Help text, announced with the field. */
  hint?: string;
  /** Right-hand control. A submit button by default. */
  action?: ReactNode;
  className?: string;
}

export function TextField({
  label,
  name,
  value,
  onChange,
  onSubmit,
  placeholder,
  error,
  hint,
  action,
  className
}: TextFieldProps) {
  const inputId = useId();
  const errorId = `${inputId}-error`;
  const hintId = `${inputId}-hint`;

  const describedBy =
    [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ") || undefined;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSubmit?.();
  };

  return (
    <form className={cx("dp-field-group", className)} role="search" onSubmit={handleSubmit}>
      <label className="dp-visually-hidden" htmlFor={inputId}>
        {label}
      </label>
      <div className="dp-field" data-invalid={error ? "true" : undefined}>
        <svg
          className="dp-field__icon"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          aria-hidden="true"
        >
          <circle cx="7" cy="7" r="4.5" />
          <path d="M10.5 10.5 L14 14" strokeLinecap="square" />
        </svg>
        <input
          id={inputId}
          className="dp-field__input"
          type="search"
          name={name}
          value={value}
          placeholder={placeholder}
          aria-describedby={describedBy}
          aria-invalid={error ? true : undefined}
          onChange={(event) => onChange(event.target.value)}
        />
        {action ?? (
          <button type="submit" className="dp-field__submit">
            Cerca
          </button>
        )}
      </div>
      {hint && !error ? (
        <p id={hintId} className="dp-field__hint">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="dp-field__error" role="alert">
          {error}
        </p>
      ) : null}
    </form>
  );
}

export default TextField;
