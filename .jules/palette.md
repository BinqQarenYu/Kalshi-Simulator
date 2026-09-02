# Palette's Journal - Micro-UX & Accessibility Learnings

## 2026-08-30 - Custom Switch Toggles & Associated Screen Reader Labels
**Learning:** Custom visual toggle switches implemented as `<button>` elements inside form panels are often missing standard screen reader roles and label associations, rendering them invisible or ambiguous to assistive technologies.
**Action:** Always link custom switch buttons to a `<label>` element via `htmlFor`/`id`, apply `role="switch"`, `aria-checked`, explicit `aria-label`, and add `focus-visible:ring-2` keyboard focus styles.
## 2025-05-18 - Accessible Custom Toggle Switches and Step Controls
**Learning:** Custom styled pill buttons used as switches lack native accessibility state unless explicitly provided with `role="switch"`, `aria-checked`, and `aria-labelledby`/`aria-label`. Additionally, compact step buttons (`-1¢`, `+1¢`) need explicit `aria-label` attributes and focus-visible rings for keyboard-only navigation.
**Action:** When building custom toggle controls or step buttons in trading panels, always include `role="switch"`, `aria-checked`, explicit `aria-label` text, and `focus-visible:ring-*` styles.
