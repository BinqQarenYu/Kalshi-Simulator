## 2025-05-18 - Accessible Custom Toggle Switches and Step Controls
**Learning:** Custom styled pill buttons used as switches lack native accessibility state unless explicitly provided with `role="switch"`, `aria-checked`, and `aria-labelledby`/`aria-label`. Additionally, compact step buttons (`-1¢`, `+1¢`) need explicit `aria-label` attributes and focus-visible rings for keyboard-only navigation.
**Action:** When building custom toggle controls or step buttons in trading panels, always include `role="switch"`, `aria-checked`, explicit `aria-label` text, and `focus-visible:ring-*` styles.
