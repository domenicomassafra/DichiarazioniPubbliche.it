/**
 * Dichiarazioni Pubbliche — Design System v1 · primitive barrel
 *
 * The single import surface for the shared design-system components.
 *
 * The inventory is a CEILING, not a quota (DP-412). Before adding a component
 * here, apply the deletion test: name the user or operator decision it
 * supports, and reject anything created only to match a mockup rectangle. A
 * component that can be served by a row, a heading, a list, or a native
 * disclosure does not belong in this file.
 *
 * Styles: the CSS lives in web/src/styles/{tokens,base,primitives,legacy}.css
 * and is loaded once by web/src/styles/global.css. Importing CSS per component
 * would defeat the layer order.
 */

export { Button } from "./Button";
export type { ButtonIntent, ButtonProps } from "./Button";

export { Dialog } from "./Dialog";
export type { DialogProps, DialogVariant } from "./Dialog";

export { Disclosure } from "./Disclosure";
export type { DisclosureProps } from "./Disclosure";

export { EvidenceTape } from "./EvidenceTape";
export type { EvidenceTapeProps, TapeMark } from "./EvidenceTape";

export { FocusRing } from "./FocusRing";
export type { FocusRingProps } from "./FocusRing";

export { Hairline } from "./Hairline";
export type { HairlineProps, HairlineWeight } from "./Hairline";

export { Row } from "./Row";
export type { RowProps } from "./Row";

export { SectionIndex } from "./SectionIndex";
export type { RailEntry, SectionIndexProps } from "./SectionIndex";

export { SegmentedControl } from "./SegmentedControl";
export type { SegmentedControlProps, SegmentedOption } from "./SegmentedControl";

export { ErrorState, EmptyState, Skeleton, SkeletonRegion } from "./States";
export type {
  EmptyStateProps,
  ErrorStateProps,
  SkeletonProps,
  SkeletonRegionProps
} from "./States";

export { StatusText } from "./StatusText";
export type { StatusTextProps } from "./StatusText";

export { Surface } from "./Surface";
export type { SurfaceProps, SurfaceVariant } from "./Surface";

export { TextField } from "./TextField";
export type { TextFieldProps } from "./TextField";

export { VisuallyHidden } from "./VisuallyHidden";
export type { VisuallyHiddenProps } from "./VisuallyHidden";

export { cx, densityAttr } from "./shared";
export type { Density, FindingState } from "./shared";
