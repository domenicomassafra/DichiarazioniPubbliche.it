/**
 * Dichiarazioni Pubbliche — Design System v1 · VisuallyHidden
 *
 * Hides content visually while keeping it in the accessibility tree.
 *
 * A11Y
 * Uses `clip-path` rather than the legacy `clip: rect()` + off-screen inset
 * pair, because the modern form needs no `top/left` and cannot scroll a
 * focused element into view by accident. The element stays focusable on
 * purpose: a visually hidden link that receives focus must reveal itself,
 * which is why `dp-skip-link` in primitives.css animates into place.
 */

import type { ElementType, ReactNode } from "react";

export interface VisuallyHiddenProps {
  as?: ElementType;
  children?: ReactNode;
  /**
   * When the hidden content becomes visible on focus (a skip link), this
   * adds the class that reveals it.
   */
  revealOnFocusClassName?: string;
}

export function VisuallyHidden({
  as: Tag = "span",
  children,
  revealOnFocusClassName
}: VisuallyHiddenProps) {
  return (
    <Tag className="dp-visually-hidden" data-reveal-on-focus={revealOnFocusClassName}>
      {children}
    </Tag>
  );
}

export default VisuallyHidden;
