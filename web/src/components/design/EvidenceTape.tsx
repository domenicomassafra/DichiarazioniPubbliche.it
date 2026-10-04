/**
 * Dichiarazioni Pubbliche — Design System v1 · EvidenceTape
 *
 * The signature temporal component. This is the one place in the system
 * where chronology is allowed to be the visual argument, and it earns that
 * only when chronology changes what a reader understands.
 *
 * PRODUCT INVARIANTS
 * - IT IS A NAVIGATION RAIL, NOT A CAUSAL GRAPH. A mark is a dated event
 *   (a media timestamp, a publication, a review, a correction). It never
 *   asserts that one event caused another, and connecting marks with lines
 *   would assert exactly that.
 * - MARKS ARE NEUTRAL UNTIL SELECTED. A chronology that color-codes every
 *   mark turns a timeline into a verdict dashboard and lets a reader infer
 *   an outcome distribution. Only the selected mark is cobalt, and only then
 *   is its finding state exposed — locally, in the detail pane, never as a
 *   color spread across the rail.
 * - AN `unresolved` MARK IS NOT A GAP. Every mark renders. A date the
 *   projection could not supply renders as "Data non disponibile", never as
 *   an empty tick.
 *
 * A11Y
 * - A real `<ol>`: the marks are events in sequence, and a screen reader
 *   should say "list, 7 items".
 * - Each mark is a button with a name that includes the date and the event,
 *   so the rail is usable without seeing the labels.
 * - The selected mark is `aria-current`, which is the announced position cue;
 *   the filled dot is its visual counterpart.
 * - Keyboard: real buttons, so Tab and Enter work with no custom handling.
 */

import type { ReactNode } from "react";
import { cx } from "./shared";

export interface TapeMark {
  /** Stable id, used as the React key and as the selection value. */
  id: string;
  /** Short label on the rail: a timecode, a date, "oggi". */
  label: string;
  /**
   * The full accessible name, e.g. "Pubblicazione del 4 marzo 2026".
   * Required: the short label alone is often ambiguous out of context.
   */
  accessibleLabel: string;
  /** Selected mark. Exactly one at most. */
  current?: boolean;
}

export interface EvidenceTapeProps {
  /** Names the rail, e.g. "Cronologia del contenuto". */
  label: string;
  marks: TapeMark[];
  onSelect: (id: string) => void;
  /** Optional content rendered after the rail, e.g. a legend of event types. */
  children?: ReactNode;
  className?: string;
}

export function EvidenceTape({
  label,
  marks,
  onSelect,
  children,
  className
}: EvidenceTapeProps) {
  // A rail with one mark carries no chronology. Rendering it would be a
  // decorative timeline, which the non-goals ban.
  if (marks.length < 2) return null;

  return (
    <div className={cx("dp-tape", className)}>
      <h3 className="dp-label" id={`${label}-tape-heading`}>
        {label}
      </h3>
      <ol className="dp-tape__track" aria-labelledby={`${label}-tape-heading`}>
        {marks.map((mark) => (
          <li key={mark.id}>
            <button
              type="button"
              className="dp-tape__mark"
              aria-current={mark.current ? "true" : undefined}
              aria-label={mark.accessibleLabel}
              onClick={() => onSelect(mark.id)}
            >
              <span className="dp-tape__dot" aria-hidden="true" />
              <span className="dp-tape__label" aria-hidden="true">
                {mark.label}
              </span>
            </button>
          </li>
        ))}
      </ol>
      {children}
    </div>
  );
}

export default EvidenceTape;
