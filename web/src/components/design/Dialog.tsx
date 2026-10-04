/**
 * Dichiarazioni Pubbliche — Design System v1 · Dialog / Sheet
 *
 * One component, two presentations. A Sheet is a Dialog docked to an edge —
 * the mobile form of the same object, not a second component with its own
 * focus logic. The registry's `FilterSheet`, source-detail sheet, bounded
 * evidence preview and Studio confirmation all resolve to this.
 *
 * WHY NATIVE <dialog>
 * `showModal()` gives, without a dependency: focus containment, inertness of
 * the rest of the document, Escape dismissal, top-layer stacking above every
 * z-index, and correct behavior in browsers that do not support `inert`.
 * The registry nominates Radix as the donor; we did not adopt it because the
 * only thing left to implement is focus restoration, which `useRestoreFocus`
 * does in ~20 lines. See the note in useFocusTrap.ts.
 *
 * A11Y
 * - `aria-labelledby` points at the visible title. An unnamed dialog is a
 *   dialog a screen reader cannot describe, so the title is required.
 * - Initial focus lands on `data-autofocus` if present, else the close
 *   button. It is never left on `<body>`.
 * - Focus returns to the invoker on close.
 * - A backdrop click closes only when the click started on the backdrop, so a
 *   text selection dragged out of the content does not dismiss the dialog.
 * - `aria-modal` comes from `showModal()`; we do not set it by hand.
 *
 * A MODAL IS NOT A DEFAULT
 * Never use this for normal public reading. A Fact-check's method notes are a
 * `Disclosure`. A sheet that appears because a user tapped a filter is fine;
 * a dialog that appears to make a choice more important than it is is a
 * failure.
 */

import { useEffect, useRef, type MouseEvent, type ReactNode } from "react";
import { cx } from "./shared";
import { useInitialFocus, useRestoreFocus } from "./useFocusTrap";

export type DialogVariant = "dialog" | "sheet";

export interface DialogProps {
  /** Controlled visibility. */
  open: boolean;
  onClose: () => void;
  /** The visible title. Required — it is the dialog's accessible name. */
  title: string;
  /** `sheet` docks to an edge and is the mobile presentation. */
  variant?: DialogVariant;
  /** Where to put initial focus. Omit to focus the close button. */
  initialFocus?: "close" | "body";
  /** Footer actions, right-aligned and sticky. */
  footer?: ReactNode;
  children?: ReactNode;
  className?: string;
}

const FOCUSABLE_IN_OVERLAY =
  'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function Dialog({
  open,
  onClose,
  title,
  variant = "dialog",
  initialFocus = "close",
  footer,
  children,
  className
}: DialogProps) {
  const dialogRef = useRef<HTMLDialogElement | null>(null);
  const pointerDownInsideRef = useRef(false);

  // These two own behavior; the local ref owns the element they need.
  useRestoreFocus(open);
  useInitialFocus<HTMLDialogElement>(open, dialogRef);

  useEffect(() => {
    const node = dialogRef.current;
    if (!node) return;
    if (open && !node.open) {
      if (typeof node.showModal === "function") {
        node.showModal();
      } else {
        // Very old engines: `open` alone gives no trap or inertness. We do not
        // ship a polyfill; we fail visibly in dev rather than silently ship an
        // inaccessible modal.
        if (import.meta.env.DEV) {
          console.warn(
            "[dichiarazioni-pubbliche] <dialog> modal is unsupported; the overlay will not trap focus."
          );
        }
        node.setAttribute("open", "");
      }
    } else if (!open && node.open) {
      if (typeof node.close === "function") node.close();
      else node.removeAttribute("open");
    }
  }, [open]);

  // A native `cancel` fires on Escape. Route it through onClose so the parent
  // stays the single source of truth and the dialog can never be dismissed
  // without the parent learning about it.
  useEffect(() => {
    const node = dialogRef.current;
    if (!node) return;
    const onCancel = (event: Event) => {
      event.preventDefault();
      onClose();
    };
    node.addEventListener("cancel", onCancel);
    return () => node.removeEventListener("cancel", onCancel);
  }, [onClose]);

  // Move focus to the nominated target once open. `useInitialFocus` handles
  // the fallback ordering; this only applies the explicit `initialFocus` case.
  useEffect(() => {
    if (!open) return;
    const node = dialogRef.current;
    if (!node) return;
    if (initialFocus === "body") {
      const id = requestAnimationFrame(() => node.focus());
      return () => cancelAnimationFrame(id);
    }
    const id = requestAnimationFrame(() => {
      const preferred = node.querySelector<HTMLElement>("[data-autofocus]");
      if (preferred) {
        preferred.focus();
        return;
      }
      const close = node.querySelector<HTMLElement>("[data-overlay-close]");
      if (close) {
        close.focus();
        return;
      }
      const first = node.querySelector<HTMLElement>(FOCUSABLE_IN_OVERLAY);
      (first ?? node).focus();
    });
    return () => cancelAnimationFrame(id);
  }, [open, initialFocus]);

  const onPointerDown = (event: MouseEvent<HTMLDialogElement>) => {
    // Record where the press began. A click that starts inside the content and
    // ends on the backdrop is a text selection, not a dismissal.
    pointerDownInsideRef.current = event.target !== event.currentTarget;
  };

  const onClick = (event: MouseEvent<HTMLDialogElement>) => {
    if (event.target === event.currentTarget && !pointerDownInsideRef.current) {
      onClose();
    }
    pointerDownInsideRef.current = false;
  };

  return (
    <dialog
      ref={dialogRef}
      className={cx("dp-overlay", variant === "sheet" && "dp-sheet", className)}
      onPointerDown={onPointerDown}
      onClick={onClick}
    >
      <header className="dp-overlay__header">
        <h2 className="dp-overlay__title">{title}</h2>
        <button
          type="button"
          className="dp-button"
          data-intent="quiet"
          data-overlay-close
          onClick={onClose}
        >
          Chiudi
        </button>
      </header>
      <div className="dp-overlay__body">{children}</div>
      {footer ? <footer className="dp-overlay__footer">{footer}</footer> : null}
    </dialog>
  );
}

export default Dialog;
