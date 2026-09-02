# Palette's Journal - Micro-UX & Accessibility Learnings

## 2026-08-30 - Custom Switch Toggles & Associated Screen Reader Labels
**Learning:** Custom visual toggle switches implemented as `<button>` elements inside form panels are often missing standard screen reader roles and label associations, rendering them invisible or ambiguous to assistive technologies.
**Action:** Always link custom switch buttons to a `<label>` element via `htmlFor`/`id`, apply `role="switch"`, `aria-checked`, explicit `aria-label`, and add `focus-visible:ring-2` keyboard focus styles.
