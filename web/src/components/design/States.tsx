/**
 * Dichiarazioni Pubbliche — Design System v1 · Skeleton, EmptyState, ErrorState
 *
 * The three states every data-bearing region must be able to be in. They are
 * grouped because they share one rule: a state teaches the interface, it
 * never fills silence.
 *
 * A11Y
 * - Skeleton is `aria-hidden` and `aria-busy` on the region, so a screen
 *   reader is told "loading" once rather than reading placeholder bars.
 * - Empty and Error are real content with real text, and the error is a live
 *   region so it is announced when it appears after an async failure.
 */

import type { ReactNode } from "react";
import { cx } from "./shared";

/* ---------------------------------------------------------------------------
 * Skeleton
 * ------------------------------------------------------------------------- */

export interface SkeletonProps {
  /** How many text lines to reserve. Matches the real content's box. */
  lines?: 1 | 2 | 3;
  /** Reserve a block of this width, e.g. a 40%-wide date. */
  width?: string;
  className?: string;
}

export function Skeleton({ lines = 1, width, className }: SkeletonProps) {
  return (
    <div
      className={cx("dp-skeleton", className)}
      data-lines={lines > 1 ? String(lines) : undefined}
      style={width ? { inlineSize: width } : undefined}
      aria-hidden="true"
    />
  );
}

export interface SkeletonRegionProps {
  /** Announced once, e.g. "Caricamento delle verifiche". */
  label: string;
  children: ReactNode;
  className?: string;
}

/** Wraps skeletons in a busy region. Skeletons alone are not announced. */
export function SkeletonRegion({ label, children, className }: SkeletonRegionProps) {
  return (
    <div className={cx("dp-skeleton-region", className)} aria-busy="true" aria-label={label}>
      {children}
    </div>
  );
}

/* ---------------------------------------------------------------------------
 * EmptyState
 * ------------------------------------------------------------------------- */

export interface EmptyStateProps {
  title: string;
  /** What would be here, and what to do. Never just "no results". */
  body: string;
  actions?: ReactNode;
  className?: string;
}

export function EmptyState({ title, body, actions, className }: EmptyStateProps) {
  return (
    <div className="dp-state" data-state="empty" className={className}>
      <p className="dp-state__title">{title}</p>
      <p className="dp-state__body">{body}</p>
      {actions ? <div className="dp-state__actions">{actions}</div> : null}
    </div>
  );
}

/* ---------------------------------------------------------------------------
 * ErrorState
 * ------------------------------------------------------------------------- */

/**
 * PRODUCT INVARIANT
 * An error here is a SYSTEM state: a provider failed, a fetch was blocked, a
 * projection is missing. It is never a finding about a claim, and it is
 * rendered in the `unresolved`/`contradict` palette steps only as a
 * left rule and a heading — never as a filled block, and never with a
 * finding-state word. A reader must never be able to mistake "the system
 * could not load this" for "this claim is false".
 *
 * `blocked` is the distinct, non-alarming variant: a provider is unavailable
 * or a gate refused, which is a normal, expected state of this product.
 */
export interface ErrorStateProps {
  title: string;
  /** Names the problem AND the recovery. */
  body: string;
  /** `blocked` for a normal refusal; `error` for an unexpected failure. */
  variant?: "error" | "blocked";
  actions?: ReactNode;
  className?: string;
}

export function ErrorState({
  title,
  body,
  variant = "error",
  actions,
  className
}: ErrorStateProps) {
  return (
    <div
      className={cx("dp-state", className)}
      data-state={variant}
      // A failure that arrives asynchronously must be announced.
      role={variant === "error" ? "alert" : "status"}
    >
      <p className="dp-state__title">{title}</p>
      <p className="dp-state__body">{body}</p>
      {actions ? <div className="dp-state__actions">{actions}</div> : null}
    </div>
  );
}
