/**
 * Dichiarazioni Pubbliche — Design System v1 · Button
 *
 * Three intents, one shape. Nothing is a pill.
 *
 * A11Y
 * - `type` defaults to "button". A button that submits a form by accident is
 *   the most common React a11y bug in a codebase this size.
 * - `busy` sets `aria-busy` AND leaves the label in place. A spinner that
 *   replaces the label destroys the accessible name mid-interaction, so the
 *   name changes only if the caller supplies a `busyLabel`.
 * - A `busy` button is `aria-disabled` rather than `disabled`, so it stays
 *   focusable and can still be discovered and explained by a screen reader. A
 *   truly `disabled` control is invisible to keyboard navigation, which is
 *   correct for a permanently unavailable action and wrong for a transient one.
 */

import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cx } from "./shared";

export type ButtonIntent = "primary" | "secondary" | "quiet";

export interface ButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className"> {
  intent?: ButtonIntent;
  /** Work is in flight. Announced, and the control stays focusable. */
  busy?: boolean;
  /** What to announce while busy. Omit to keep the original label. */
  busyLabel?: string;
  full?: boolean;
  className?: string;
  children?: ReactNode;
}

export function Button({
  intent = "secondary",
  busy = false,
  busyLabel,
  full = false,
  type = "button",
  disabled,
  className,
  children,
  ...rest
}: ButtonProps) {
  // A busy button must not be re-submittable, but must stay focusable.
  const isDisabled = disabled ?? false;
  const blocked = busy || isDisabled;

  return (
    <button
      type={type}
      disabled={isDisabled}
      aria-busy={busy || undefined}
      aria-disabled={blocked || undefined}
      data-intent={intent}
      data-busy={busy ? "true" : undefined}
      data-full={full ? "true" : undefined}
      className={cx("dp-button", className)}
      {...rest}
    >
      {busy ? <span className="dp-button__spinner" aria-hidden="true" /> : null}
      <span>{busy && busyLabel ? busyLabel : children}</span>
    </button>
  );
}

export default Button;
