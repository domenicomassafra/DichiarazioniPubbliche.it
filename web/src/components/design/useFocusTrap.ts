/**
 * Dichiarazioni Pubbliche — Design System v1 · focus utilities
 *
 * The two behaviors the system must never get wrong, written once:
 * trapping focus inside an overlay, and returning it to the invoker on close.
 *
 * WHY THIS EXISTS RATHER THAN A LIBRARY
 * `docs/ux/design-source-registry-v1.md` lists Radix as the ADAPT donor for
 * dialog focus semantics. We did not adopt it: the only dialog behavior this
 * product needs is the native `<dialog>`'s `showModal()`, which already traps
 * focus, makes the rest of the document inert, handles Escape, and stacks in
 * the top layer. What the platform does NOT do is restore focus to the
 * element that opened it — so that half is ours, and it is small enough that
 * vendoring a primitive library for it would cost more than it saves.
 *
 * If a future surface needs a menu, a popover, or a combobox, this is the
 * file to extend, and the deletion test in DP-412 applies again.
 */

import { useEffect, useRef, type RefObject } from "react";

/**
 * Restores focus to the previously focused element when `active` goes false.
 *
 * Use on the element that mounts the dialog, not inside the dialog: the
 * invoker may unmount while the dialog is open, and in that case there is
 * nothing to restore to and the browser falls back to `<body>`, which is the
 * correct outcome.
 */
export function useRestoreFocus(active: boolean) {
  // The invoker is whatever element happened to hold focus, so it is a plain
  // HTMLElement by construction. Typing it as a caller-chosen subtype would
  // be a lie the compiler would then have to be lied to about.
  const invokerRef = useRef<HTMLElement | null>(null);
  const hadFocusRef = useRef(false);

  useEffect(() => {
    if (active) {
      // Only capture an invoker if focus is really on an element. On a touch
      // trigger the "active" element can be `<body>`, and restoring focus to
      // `<body>` would silently drop the user at the top of the document.
      const activeEl = document.activeElement as HTMLElement | null;
      if (activeEl && activeEl !== document.body) {
        invokerRef.current = activeEl;
        hadFocusRef.current = true;
      }
    } else if (hadFocusRef.current && invokerRef.current) {
      const invoker = invokerRef.current;
      // Wait a frame: the dialog may still be closing and would steal focus
      // back on its own teardown.
      const id = requestAnimationFrame(() => {
        if (document.contains(invoker)) {
          invoker.focus();
        } else {
          document.querySelector<HTMLElement>("[data-dialog-return-focus]")?.focus();
        }
      });
      hadFocusRef.current = false;
      return () => cancelAnimationFrame(id);
    }
    return undefined;
  }, [active]);
}

/**
 * Moves focus into an overlay once it opens, onto the element the caller
 * nominates, falling back to the overlay itself.
 *
 * Native `showModal()` focuses the first focusable descendant, which is
 * usually a heading or a close button in an unhelpful order. Naming the
 * initial focus point explicitly is what makes an overlay predictable.
 */
export function useInitialFocus<T extends HTMLElement>(
  active: boolean,
  ref: RefObject<T | null>
) {
  useEffect(() => {
    if (!active || !ref.current) return;
    const node = ref.current;
    const target =
      node.querySelector<HTMLElement>("[data-autofocus]") ??
      node.querySelector<HTMLElement>("[data-overlay-close]") ??
      node;
    // rAF so the element is laid out and can actually receive focus.
    const id = requestAnimationFrame(() => target.focus());
    return () => cancelAnimationFrame(id);
  }, [active, ref]);
}

/**
 * The selectors a focus trap has to consider. Exported so a test can assert
 * the trap's scope without reaching into private state.
 */
export const FOCUSABLE_SELECTOR = [
  "a[href]",
  "area[href]",
  "button:not([disabled])",
  "input:not([disabled]):not([type='hidden'])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "iframe",
  "object",
  "embed",
  "audio[controls]",
  "video[controls]",
  "[contenteditable]:not([contenteditable='false'])",
  "[tabindex]:not([tabindex='-1'])"
].join(",");
