/**
 * Dichiarazioni Pubbliche — Design System v1 · Surface
 *
 * The system's only container primitive.
 *
 * DESIGN INTENT
 * A card is a decision, not a default. `Surface` therefore has five named
 * grounds and a separate `bounded` opt-in, so "this needs a card" is a
 * visible choice in the markup rather than a default that everything inherits.
 *
 * STATE MATRIX
 *   default      ground, no border
 *   selected     selected ground + the Segno (see `showSign`)
 *   bounded      raised ground + control-grade hairline
 *   inverse      ink ground; only for the one high-emphasis band
 *
 * A11Y
 * `as` lets a consumer pick the correct element instead of wrapping a
 * `div` around a heading, which would break the document outline. Surface
 * renders no semantics of its own and never sets a role.
 */

import type { ElementType, ReactNode } from "react";
import { cx } from "./shared";

export type SurfaceVariant = "ground" | "band" | "well" | "raised" | "inverse";

export interface SurfaceProps {
  /** Which ground this surface sits on. */
  variant?: SurfaceVariant;
  /**
   * Draw a control-grade hairline. Legal only for a genuinely self-contained
   * object: a sheet, a dialog, one bounded evidence object. Not for a list.
   */
  bounded?: boolean;
  /** Selection state. Paints the selected ground and, with showSign, the Segno. */
  selected?: boolean;
  /**
   * Draw the Segno — the 2px cobalt rail at the leading edge.
   * This is the system's one brand gesture, and it is always cobalt, never a
   * finding-state hue: a selection cue that borrowed verdict color would let
   * a reader confuse "you are here" with a verdict.
   */
  showSign?: boolean;
  as?: ElementType;
  className?: string;
  children?: ReactNode;
  [key: `data-${string}`]: unknown;
}

export function Surface({
  variant = "ground",
  bounded = false,
  selected = false,
  showSign = true,
  as: Tag = "div",
  className,
  children,
  ...rest
}: SurfaceProps) {
  return (
    <Tag
      data-variant={variant}
      data-bounded={bounded ? "true" : undefined}
      data-selected={selected ? "true" : undefined}
      data-sign={showSign && selected ? "true" : undefined}
      className={cx("dp-surface", className)}
      {...rest}
    >
      {children}
    </Tag>
  );
}

export default Surface;
