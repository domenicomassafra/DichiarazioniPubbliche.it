/**
 * Dichiarazioni Pubbliche — Design System v1 · machine-readable tokens
 *
 * This file is the typed mirror of `web/src/styles/tokens.css`. It exists so
 * React islands can read the design system's real values (a density lookup, a
 * contrast-verified status step, a motion duration) without hardcoding a
 * literal and breaking the "no literals outside tokens.css" contract.
 *
 * THE MIRROR IS A CONTRACT, NOT A CONVENIENCE.
 * - Every value here must equal its CSS custom property. If you change one,
 *   change both. `npm run check` cannot catch a drift, so review does.
 * - Nothing here invents a value the CSS does not have.
 * - Nothing here encodes product logic. A finding state is a *label plus a
 *   color step*; which label the public projection allows is owned by the
 *   backend policy, never by this file.
 *
 * Consumed by: components/design/**, and any island that needs a real value.
 */

/* ---------------------------------------------------------------------------
 * Density
 * ------------------------------------------------------------------------- */

/** The two densities. They share one language and differ only in rhythm. */
export type Density = "public" | "studio";

export interface DensityTokens {
  readonly name: Density;
  readonly rowPadY: string;
  readonly rowPadX: string;
  readonly rowMin: string;
  readonly blockGap: string;
  readonly sectionGap: string;
  readonly bandGap: string;
  readonly controlMin: string;
  readonly cellPadY: string;
  readonly typeBody: string;
  readonly typeLabel: string;
  readonly typeMeta: string;
  readonly measure: string;
}

/**
 * `density["studio"].controlMin` is 2rem (32px), below the 2.75rem touch
 * floor. This is the one documented exception in the system: Studio is
 * desktop-first and pointer-driven, and 32px is the density-appropriate
 * minimum for a mouse. It is NOT a licence to ship 32px touch targets on
 * Public, and it must be re-validated before any Studio surface is exposed
 * to a touch-primary device.
 */
export const density = {
  public: {
    name: "public",
    rowPadY: "1rem",
    rowPadX: "1rem",
    rowMin: "3.75rem",
    blockGap: "1.5rem",
    sectionGap: "4rem",
    bandGap: "7.5rem",
    controlMin: "2.75rem",
    cellPadY: "0.75rem",
    typeBody: "var(--text-body)",
    typeLabel: "var(--text-label)",
    typeMeta: "var(--text-meta)",
    measure: "var(--measure-prose)"
  },
  studio: {
    name: "studio",
    rowPadY: "0.5rem",
    rowPadX: "0.75rem",
    rowMin: "2.5rem",
    blockGap: "0.75rem",
    sectionGap: "2rem",
    bandGap: "3rem",
    controlMin: "2rem",
    cellPadY: "0.5rem",
    typeBody: "var(--text-body-quiet)",
    typeLabel: "var(--text-meta)",
    typeMeta: "var(--text-meta)",
    measure: "var(--measure-data)"
  }
} as const satisfies Record<Density, DensityTokens>;

/* ---------------------------------------------------------------------------
 * Finding states
 * ------------------------------------------------------------------------- */

/**
 * The four written finding states.
 *
 * PRODUCT INVARIANT: these describe the relation between a claim and the
 * evidence about it. They are never a verdict about a person, a party, or an
 * entity, and no component may color an identity with them.
 *
 * `unresolved` is a first-class state, not an absence. It is never rendered
 * as an empty slot.
 */
export type FindingState = "supported" | "contradicted" | "imprecise" | "unresolved";

export interface FindingScale {
  /** The only step permitted to render status TEXT. All clear 4.5:1 on paper-0. */
  readonly text: string;
  /** Marks, hairlines, and non-text UI. All clear 3:1 on paper-0. */
  readonly mark: string;
  /** Resting background. Never carries text alone. */
  readonly ground: string;
  /** The inverse-ground step, for use on ink-inverse only. */
  readonly onInverse: string;
  /** Ink to use when text sits on `ground`. Clears 4.5:1 on `ground`. */
  readonly onGround: string;
  /** Measured contrast of `text` on --paper-0. */
  readonly ratioOnPaper: number;
}

export const finding = {
  supported: {
    text: "var(--support-700)",
    mark: "var(--support-600)",
    ground: "var(--support-100)",
    onInverse: "var(--support-200)",
    onGround: "var(--support-on)",
    ratioOnPaper: 7.3
  },
  contradicted: {
    text: "var(--contradict-700)",
    mark: "var(--contradict-600)",
    ground: "var(--contradict-100)",
    onInverse: "var(--contradict-200)",
    onGround: "var(--contradict-on)",
    ratioOnPaper: 8.04
  },
  imprecise: {
    text: "var(--imprecise-700)",
    mark: "var(--imprecise-600)",
    ground: "var(--imprecise-100)",
    onInverse: "var(--imprecise-200)",
    onGround: "var(--imprecise-on)",
    ratioOnPaper: 7.6
  },
  unresolved: {
    text: "var(--unresolved-700)",
    mark: "var(--unresolved-600)",
    ground: "var(--unresolved-100)",
    onInverse: "var(--unresolved-200)",
    onGround: "var(--unresolved-on)",
    ratioOnPaper: 7.66
  }
} as const satisfies Record<FindingState, FindingScale>;

/**
 * The rendered label for a finding state.
 *
 * These are the product's own Italian words. They are text-first by
 * construction: a state with no word is not rendered at all.
 */
export const findingLabel = {
  supported: "Sostenuta",
  contradicted: "Contradetta",
  imprecise: "Imprecisa",
  unresolved: "Non risolta"
} as const satisfies Record<FindingState, string>;

/**
 * PRODUCT INVARIANT: there is deliberately no `neutral`, `error`, or
 * `success` finding state. A state that meant "the system failed" is a UI
 * state (ErrorState), never a finding about a claim. Keeping the two vocabularies
 * separate is what stops a provider failure from being rendered as a verdict.
 */
export const findingStates = Object.keys(finding) as readonly FindingState[];

/* ---------------------------------------------------------------------------
 * Color
 * ------------------------------------------------------------------------- */

export const color = {
  paper: {
    ground: "var(--paper-0)",
    band: "var(--paper-1)",
    well: "var(--paper-2)",
    selected: "var(--paper-selected)",
    raised: "var(--paper-raised)",
    inverse: "var(--ink-inverse)"
  },
  ink: {
    primary: "var(--ink-900)",
    secondary: "var(--ink-700)",
    tertiary: "var(--ink-500)"
  },
  /** Selection and focus share this hue, deliberately. */
  cobalt: {
    accent: "var(--cobalt-600)",
    action: "var(--cobalt-700)",
    active: "var(--cobalt-800)",
    focus: "var(--focus-ring-color)"
  },
  /** Content separators. Not control edges — see the 1.4.11 note in tokens.css. */
  rule: {
    hairline: "var(--rule-hairline)",
    strong: "var(--rule-hairline-strong)",
    control: "var(--rule-control)",
    ink: "var(--rule-ink)"
  }
} as const;

/**
 * Measured contrast, for documentation and for a runtime assertion in dev.
 * Ratios are against `--paper-0` unless the key says otherwise.
 *
 * These are the numbers quoted in docs/ux/design-system-v1.md. If a palette
 * value changes, these change with it — the table is generated from the CSS,
 * not maintained beside it.
 */
export const contrast = {
  "ink-900/paper-0": 16.67,
  "ink-700/paper-0": 10.1,
  "ink-500/paper-0": 6.56,
  "ink-900/paper-1": 15.19,
  "ink-700/paper-1": 9.21,
  "ink-500/paper-1": 5.98,
  "cobalt-600/paper-0": 5.65,
  "cobalt-700/paper-0": 7.61,
  "cobalt-800/paper-0": 9.68,
  "rule-control/paper-0": 3.83,
  "rule-control/paper-1": 3.49,
  "ink-900/ink-inverse": 16.67,
  "cobalt-200/ink-inverse": 10.58
} as const;

export type ContrastKey = keyof typeof contrast;

/** WCAG 2.1 thresholds used throughout the system. */
export const contrastThreshold = {
  /** 1.4.3 — body text. */
  body: 4.5,
  /** 1.4.3 — large text (>= 24px, or >= 18.66px bold). */
  large: 3,
  /** 1.4.11 — non-text UI: control borders, state marks, focus. */
  nonText: 3
} as const;

/* ---------------------------------------------------------------------------
 * Type
 * ------------------------------------------------------------------------- */

export type TypefaceRole = "claim" | "ui" | "data";

export const typeface = {
  /** Every claim, answer and title. The voice of the record. */
  claim: "var(--font-claim)",
  /** Navigation, controls, labels, structure. The voice of the interface. */
  ui: "var(--font-ui)",
  /** Time, identifiers, tabular measurement ONLY. Never as "technical" texture. */
  data: "var(--font-data)"
} as const satisfies Record<TypefaceRole, string>;

export interface TypeStep {
  readonly size: string;
  readonly leading: string;
  readonly role: TypefaceRole;
}

export const typeScale = {
  display: { size: "var(--text-display)", leading: "var(--leading-display)", role: "claim" },
  title: { size: "var(--text-title)", leading: "var(--leading-title)", role: "claim" },
  headline: { size: "var(--text-headline)", leading: "var(--leading-headline)", role: "claim" },
  subhead: { size: "var(--text-subhead)", leading: "var(--leading-subhead)", role: "claim" },
  lede: { size: "var(--text-lede)", leading: "var(--leading-lede)", role: "ui" },
  body: { size: "var(--text-body)", leading: "var(--leading-body)", role: "ui" },
  bodyQuiet: { size: "var(--text-body-quiet)", leading: "var(--leading-body-quiet)", role: "ui" },
  label: { size: "var(--text-label)", leading: "var(--leading-label)", role: "ui" },
  meta: { size: "var(--text-meta)", leading: "var(--leading-meta)", role: "ui" }
} as const satisfies Record<string, TypeStep>;

/** The metadata floor is 13px. 11px gray micro-metadata is banned. */
export const typeFloor = {
  metadata: "0.8125rem",
  trackingDisplay: "-0.022em",
  trackingHeading: "-0.014em"
} as const;

/** 65–75ch for prose; 34ch for a checked statement, which is read not scanned. */
export const measure = {
  claim: "var(--measure-claim)",
  prose: "var(--measure-prose)",
  brief: "var(--measure-brief)",
  data: "var(--measure-data)"
} as const;

/* ---------------------------------------------------------------------------
 * Space, geometry, layout
 * ------------------------------------------------------------------------- */

export const space = {
  1: "0.25rem",
  2: "0.5rem",
  3: "0.75rem",
  4: "1rem",
  5: "1.5rem",
  6: "2rem",
  7: "3rem",
  8: "4rem",
  9: "5rem",
  10: "7.5rem",
  11: "10rem"
} as const;

export const geometry = {
  /**
   * Radii stay 0–3px. The visual world is editorial and printed; universal
   * 12–24px rounding is the single clearest template tell, and it is banned.
   */
  mark: "var(--radius-mark)",
  control: "var(--radius-control)",
  /**
   * There is no `pill`. An earlier draft exposed one; no component used it,
   * so it was cut under the DP-412 deletion test. See tokens.css § 10.
   */
  /** WCAG 2.2 AA floor for a standalone control. */
  targetMin: "var(--target-min)"
} as const;

export const layout = {
  shell: "var(--width-shell)",
  reading: "var(--width-reading)",
  rail: "var(--width-rail)",
  document: "var(--width-document)",
  studioShell: "var(--width-studio-shell)",
  columns: 12,
  gutter: "var(--grid-gutter)"
} as const;

/* ---------------------------------------------------------------------------
 * Motion
 * ------------------------------------------------------------------------- */

export const motion = {
  fast: "var(--duration-fast)",
  standard: "var(--duration-standard)",
  slow: "var(--duration-slow)",
  easeEnter: "var(--ease-enter)",
  easeExit: "var(--ease-exit)",
  easeMove: "var(--ease-move)"
} as const;

export const motionDurationMs = {
  fast: 120,
  standard: 180,
  slow: 260
} as const;

/* ---------------------------------------------------------------------------
 * Elevation
 * ------------------------------------------------------------------------- */

/**
 * The system has no shadow scale. Depth is a change of ground plus a hairline.
 * `overlay` exists only because a dialog must separate from any content beneath.
 */
export const elevation = {
  none: "var(--elevation-none)",
  hairline: "var(--elevation-hairline)",
  hairlineSelected: "var(--elevation-hairline-selected)",
  overlay: "var(--elevation-overlay)"
} as const;

/* ---------------------------------------------------------------------------
 * Aggregated view
 * ------------------------------------------------------------------------- */

export const tokens = {
  color,
  contrast,
  contrastThreshold,
  density,
  elevation,
  finding,
  findingLabel,
  findingStates,
  geometry,
  layout,
  measure,
  motion,
  motionDurationMs,
  space,
  typeface,
  typeFloor,
  typeScale
} as const;

export type Tokens = typeof tokens;

export default tokens;
