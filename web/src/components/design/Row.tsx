/**
 * Dichiarazioni Pubbliche — Design System v1 · Row
 *
 * The primary repeated object: `ClaimRow`, `SourceRow`, `TranscriptLine`,
 * `ClaimQueueRow` and `EvidenceReviewRow` are all this component with
 * different cells. It is a row, never a card.
 *
 * DESIGN INTENT
 * A record is a list of dated statements. Rendering that as a stack of rounded
 * cards is the single change that turns a public record into a template, so
 * the row is deliberately a hairline and a reading order. Density decides its
 * rhythm; nothing else does.
 *
 * A11Y — the whole-row-link problem
 * The entire row is the hit target, but the accessible name must be the claim
 * and the link must stay copyable and middle-clickable. The solution is a
 * real anchor containing the claim text, stretched over the row with
 * `::after`. The anchor's name is the claim; the row is only its hit area.
 *
 * `as="li"` is the default so a list of records is a real list and a screen
 * reader can say "list, 12 items". Wrapping rows in a bare div throws that
 * away.
 */

import type { ReactNode } from "react";
import { cx } from "./shared";

export interface RowProps {
  /** The checked statement. This is the row's accessible name and its voice. */
  claim: ReactNode;
  /** Destination of the row link. Omit to render a non-interactive row. */
  href?: string;
  /** Time, origin, and other secondary facts. Never an 11px gray crutch. */
  meta?: ReactNode;
  /** Leading cell: a date, a timestamp, an ordinal. */
  lead?: ReactNode;
  /** Trailing cell: usually a StatusText. */
  status?: ReactNode;
  /** Row-level action, e.g. "Apri la fonte". */
  action?: ReactNode;
  /** This row is the current selection. Paints the Segno. */
  selected?: boolean;
  /** Allow the row itself to be focusable (button-rows in Studio). */
  onSelect?: () => void;
  as?: "li" | "div" | "article";
  className?: string;
  children?: ReactNode;
}

export function Row({
  claim,
  href,
  meta,
  lead,
  status,
  action,
  selected = false,
  onSelect,
  as = "li",
  className,
  children
}: RowProps) {
  // A row is either a link or a button-row, never both, and never neither
  // unless the caller explicitly renders its own cell content.
  const interactive = Boolean(href) || Boolean(onSelect);
  const Tag = as;

  const body = (
    <>
      {lead ? <div className="dp-row__lead">{lead}</div> : null}
      <div className="dp-row__main">
        {href ? (
          <a href={href} className="dp-row__claim-link">
            <span className="dp-row__claim">{claim}</span>
          </a>
        ) : (
          <span className="dp-row__claim">{claim}</span>
        )}
        {meta ? <div className="dp-row__meta">{meta}</div> : null}
        {children}
      </div>
      {status ? <div className="dp-row__status">{status}</div> : null}
      {action ? (
        <div className="dp-row__action">
          {/* The action is a real control, not a glyph: the arrow glyph that
              used to sit here repeated the link and added nothing. */}
          <span className="dp-row__action-text">{action}</span>
        </div>
      ) : null}
    </>
  );

  if (onSelect) {
    return (
      <button
        type="button"
        className={cx("dp-row", className)}
        data-selected={selected ? "true" : undefined}
        data-interactive="true"
        aria-current={selected ? "true" : undefined}
        onClick={onSelect}
      >
        {body}
      </button>
    );
  }

  return (
    <Tag
      className={cx("dp-row", className)}
      data-selected={selected ? "true" : undefined}
      data-interactive={interactive ? "true" : "false"}
    >
      {body}
    </Tag>
  );
}

export default Row;
