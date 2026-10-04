/**
 * Dichiarazioni Pubbliche — Design System v1 · Disclosure
 *
 * A real `<details>`. Deliberately not a React-controlled accordion.
 *
 * WHY NATIVE
 * The registry lists GOV.UK Details and USWDS as the behavioral donors, and
 * both point at the same insight: the main job of a disclosure is to NOT be
 * misused, and native `<details>` gets keyboard operation, the
 * open/closed state announcement, in-page find, and the ability to be
 * link-targeted for free. A hand-rolled accordion that reimplements
 * `aria-expanded` and arrow-key roving focus is strictly worse here, and it is
 * exactly the component a template library would have supplied.
 *
 * PRODUCT INVARIANT — WHEN NOT TO USE IT
 * Primary rationale and primary sources are NEVER hidden behind a
 * disclosure to shorten a page. This component is for genuinely secondary
 * material: method notes, provenance identifiers, limitations, correction
 * history. That is a caller discipline, but `secondary` exists so the intent
 * is visible in the markup and reviewable.
 *
 * A11Y
 * - The summary is the control. It is focusable, toggles on Enter/Space, and
 *   the browser announces expanded/collapsed.
 * - The chevron is drawn from borders, not a glyph, and is `aria-hidden`, so
 *   it is not read as a character.
 * - `open` is controlled only on first render, then left to the browser, so
 *   React never fights the native toggle.
 */

import type { ReactNode } from "react";
import { useId } from "react";
import { cx } from "./shared";

export interface DisclosureProps {
  /** The summary text. Names what is inside. */
  summary: string;
  /** Secondary material only. Set false for anything a reader came to read. */
  secondary?: boolean;
  /** Initial open state. The reader can still close it. */
  defaultOpen?: boolean;
  children?: ReactNode;
  className?: string;
}

export function Disclosure({
  summary,
  secondary = true,
  defaultOpen = false,
  children,
  className
}: DisclosureProps) {
  const bodyId = useId();

  return (
    <details
      className={cx("dp-disclosure", className)}
      data-secondary={secondary ? "true" : "false"}
      open={defaultOpen}
    >
      <summary className="dp-disclosure__summary">
        <span>{summary}</span>
        <span className="dp-disclosure__chevron" aria-hidden="true" />
      </summary>
      <div id={bodyId} className="dp-disclosure__body">
        {children}
      </div>
    </details>
  );
}

export default Disclosure;
