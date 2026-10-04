/**
 * Dichiarazioni Pubbliche — Design System v1 · SegmentedControl
 *
 * A real `radiogroup`. This is the component where getting the keyboard model
 * right matters most, because a tab strip that is a row of buttons is a
 * classic silent accessibility failure: it looks right, reads wrong, and
 * arrow keys do nothing.
 *
 * A11Y — the model we implement
 * - `role="radiogroup"` with an accessible name.
 * - Each option is `role="radio"` with `aria-checked`. Because these are real
 *   `<input type="radio">` elements, Tab enters the group once and the arrow
 *   keys move between options, which is the expected behavior for radios.
 * - The set is wrapped in a `<fieldset>` with a `<legend>` when `label` is
 *   given, so the group has a name in the form controls list and not only to
 *   assistive tech.
 * - A visually hidden input per option means the value participates in a
 *   plain form POST, which is what the public filter forms need.
 * - The selected option is underlined with the Segno AND carries
 *   `aria-checked`; neither cue carries the state alone.
 *
 * WHY NOT TABS
 * The registry nominates Radix Tabs and warns (GOV.UK) against misusing
 * tabs. These options change a *value*, not a panel, so radios are the
 * correct role. Reserve tabs for switching same-page panels.
 */

import { useId, type ReactNode } from "react";
import { cx } from "./shared";

export interface SegmentedOption {
  value: string;
  label: string;
  /** A count of results in this option, e.g. "12". Not a score. */
  count?: number;
  disabled?: boolean;
  /** Optional adornment. Must be decorative or already labelled. */
  adornment?: ReactNode;
}

export interface SegmentedControlProps {
  /** Names the group. Rendered as a visually hidden legend. */
  label: string;
  options: SegmentedOption[];
  value: string;
  onChange: (value: string) => void;
  /** Shared `name` for the underlying inputs, so the group posts as one field. */
  name: string;
  className?: string;
}

export function SegmentedControl({
  label,
  options,
  value,
  onChange,
  name,
  className
}: SegmentedControlProps) {
  const groupId = useId();
  // An empty selection is a real state (no filter chosen), so the group must
  // be able to hold it. We do not default to the first option.
  const selected = options.find((option) => option.value === value);

  return (
    <fieldset
      className={cx("dp-fieldset-reset", className)}
      style={{ border: 0, margin: 0, padding: 0, minInlineSize: 0 }}
    >
      <legend className="dp-visually-hidden" id={groupId}>
        {label}
      </legend>
      <div className="dp-segmented" role="radiogroup" aria-labelledby={groupId}>
        {options.map((option) => {
          const isChecked = option.value === value;
          return (
            <label
              key={option.value}
              className="dp-segmented__option"
              data-checked={isChecked ? "true" : undefined}
            >
              <input
                type="radio"
                className="dp-visually-hidden"
                name={name}
                value={option.value}
                checked={isChecked}
                disabled={option.disabled}
                onChange={() => onChange(option.value)}
              />
              {/* The input is visually hidden but focusable and is a child of
                  the label, so the label's own text is its accessible name.
                  That text is NOT aria-hidden: hiding it would strip the
                  name and announce an unlabelled radio. The focus ring is
                  painted on the label via :focus-within, below. */}
              <span>{option.label}</span>
              {option.count !== undefined ? (
                <span className="dp-segmented__count" aria-hidden="true">
                  {option.count}
                </span>
              ) : null}
              {option.adornment}
            </label>
          );
        })}
      </div>
      {/* A live region so a change is announced with the new option's name,
          which a bare aria-checked flip does not do on its own. */}
      <span className="dp-visually-hidden" role="status">
        {selected ? `${label}: ${selected.label} selezionato` : `${label}: nessuna selezione`}
      </span>
    </fieldset>
  );
}

export default SegmentedControl;
