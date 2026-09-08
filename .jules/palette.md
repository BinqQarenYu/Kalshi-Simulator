# Palette's Journal - Micro-UX & Accessibility Learnings

## 2026-09-03 - Safety Confirmation Switch Controls and Modal Close Buttons
**Learning:** Safety toggles in high-stakes modal dialogs (like live trade order dry-run mode) require explicit `role="switch"`, `aria-checked`, and `aria-labelledby` linking to their visual title so screen reader users can verify critical state before confirming financial transactions.
**Action:** In modal confirmation dialogs, link switch buttons to heading text with `id`/`aria-labelledby`, ensure `aria-checked` reflects boolean state, add `focus-visible:ring-2` focus rings, and provide `aria-label` to modal close buttons.

## 2026-08-30 - Custom Switch Toggles & Associated Screen Reader Labels
**Learning:** Custom visual toggle switches implemented as `<button>` elements inside form panels are often missing standard screen reader roles and label associations, rendering them invisible or ambiguous to assistive technologies.
**Action:** Always link custom switch buttons to a `<label>` element via `htmlFor`/`id`, apply `role="switch"`, `aria-checked`, explicit `aria-label`, and add `focus-visible:ring-2` keyboard focus styles.
## 2025-05-18 - Accessible Custom Toggle Switches and Step Controls
**Learning:** Custom styled pill buttons used as switches lack native accessibility state unless explicitly provided with `role="switch"`, `aria-checked`, and `aria-labelledby`/`aria-label`. Additionally, compact step buttons (`-1¢`, `+1¢`) need explicit `aria-label` attributes and focus-visible rings for keyboard-only navigation.
**Action:** When building custom toggle controls or step buttons in trading panels, always include `role="switch"`, `aria-checked`, explicit `aria-label` text, and `focus-visible:ring-*` styles.

## 2026-08-31 - Icon-Only Action Buttons & Modal Dismiss Controls
**Learning:** Icon-only action controls (such as mute/unmute audio toggles and modal close `✕` buttons) lack accessible names by default, preventing screen reader users from identifying their function.
**Action:** Always complement icon-only buttons with explicit `aria-label` attributes, dynamic state attributes (`aria-pressed`), and `focus-visible:ring-2` keyboard focus rings.

## 2026-09-04 - Segmented View Mode Toggles & Metric Emphasis
**Learning:** Segmented toggle button groups (such as `$` vs `%` price view mode) need explicit `role="group"`, `aria-label`, `type="button"`, and dynamic `aria-pressed` state attributes so assistive technology users understand the available selection group and current active filter state. In addition, changing view modes should dynamically adjust visual emphasis on the selected metric.
**Action:** Wrap button toggle pairs in a `role="group"` element with a clear `aria-label`, supply `aria-pressed` and `focus-visible:ring-2` focus rings on each button, and wire state changes to dynamically highlight the active metric.

## 2026-09-07 - Order Book Ladder Keyboard Navigation and Filter Controls
**Learning:** Interactive list/table rows (like order book price levels) implemented as `<div>` elements are invisible to keyboard tab order and screen reader action queues unless marked with `role="button"`, `tabIndex={0}`, explicit `aria-label`, and `onKeyDown` handlers for `Enter`/`Space`.
**Action:** When converting interactive container elements (e.g. order book price rows) into accessible controls, add `role="button"`, `tabIndex={0}`, descriptive `aria-label`, `onKeyDown` keyboard event listeners, `focus-visible:ring-*` focus outlines, and sound feedback (`soundFX.playClickSound()`).
