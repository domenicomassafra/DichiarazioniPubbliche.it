/**
 * Dichiarazioni Pubbliche — Design System v1 · FocusRing
 *
 * There is no focus ring *component* in this system: focus is a CSS contract
 * applied to every focusable element (see base.css `:focus-visible`). This
 * module exists for the cases CSS alone cannot express.
 *
 * USE IT WHEN
 * - a composite control contains several focusable children and the ring must
 *   wrap the whole group rather than one part (SegmentedControl, filter bar);
 * - an element is focusable programmatically but is not a form control.
 *
 * DO NOT USE IT TO
 * - add a second ring to something that already has `:focus-visible` — that
 *   is a double indicator, which is worse than none;
 * - focus something on mount without a real user action behind it.
 */

import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { cx } from "./shared";

export interface FocusRingProps {
  /** Wrap the group in a group ring when focus is inside it. */
  group?: boolean;
  className?: string;
  children?: ReactNode;
}

export function FocusRing({ group = true, className, children }: FocusRingProps) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!group) return;
    const node = ref.current;
    if (!node) return;
    const onFocusIn = () => node.setAttribute("data-focus-within", "true");
    const onFocusOut = (event: FocusEvent) => {
      // focusout fires before focus lands on the next element, so check the
      // relatedTarget: if it is still inside us, focus has not left.
      const next = event.relatedTarget as Node | null;
      if (!next || !node.contains(next)) {
        node.removeAttribute("data-focus-within");
      }
    };
    node.addEventListener("focusin", onFocusIn);
    node.addEventListener("focusout", onFocusOut);
    return () => {
      node.removeEventListener("focusin", onFocusIn);
      node.removeEventListener("focusout", onFocusOut);
    };
  }, [group]);

  return (
    <div
      ref={ref}
      data-focus-group={group ? "true" : undefined}
      className={cx("dp-focus-group", className)}
    >
      {children}
    </div>
  );
}

export default FocusRing;
