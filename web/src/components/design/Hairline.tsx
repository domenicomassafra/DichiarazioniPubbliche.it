/**
 * Dichiarazioni Pubbliche — Design System v1 · Hairline
 *
 * The system's only separator, and its entire elevation system.
 *
 * DESIGN INTENT
 * The world has no shadows. Depth is a change of ground plus a hairline, so
 * a rule is load-bearing: it groups content or it states a real boundary. This
 * component exposes exactly the three weights that each have a named job, so
 * a rule cannot become decoration.
 *
 * A11Y
 * Purely decorative rules are `aria-hidden`. A rule that is the only boundary
 * of an interactive object is not this component's job: use `rule-control`
 * as a border on the control, because 1.4.11 exempts decorative separators
 * and does not exempt a control's only edge.
 */

import type { ReactNode } from "react";
import { cx } from "./shared";

export type HairlineWeight = "hairline" | "strong" | "ink" | "control";

export interface HairlineProps {
  /**
   * - `hairline`  1px content separator (1.54:1 — decorative, 1.4.11 exempt)
   * - `strong`   1px emphasised separator (2.05:1)
   * - `ink`      2px structural rule, for a top-level band boundary
   * - `control`  1px control-grade rule (3.83:1) — use on a control's edge
   */
  weight?: HairlineWeight;
  orientation?: "horizontal" | "vertical";
  className?: string;
  children?: ReactNode;
}

export function Hairline({
  weight = "hairline",
  orientation = "horizontal",
  className,
  children
}: HairlineProps) {
  return (
    <div
      role="presentation"
      aria-hidden={children ? undefined : true}
      data-weight={weight}
      data-orientation={orientation}
      className={cx("dp-hairline", className)}
    >
      {children}
    </div>
  );
}

export default Hairline;
