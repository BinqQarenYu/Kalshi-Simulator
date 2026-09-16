# Palette's Journal — Institutional WebCLOB FinTech Design & Ergonomics

## 🏛️ Executive Scope Directive: "Scoop More Sand" (Macro-UX Overhauls vs Micro-Patches)
- **Zero Teaspoon Anti-Pattern**: Never open a PR that merely adds a single `aria-label` or one focus ring to a single button. Micro-patches create PR clutter and fragment component design.
- **Full Component & View Sweeps**: When tasked with a component or panel, execute a comprehensive, aggressive visual and ergonomic overhaul:
  1. **Visual Hierarchy & Layout Density**: Institutional dark WebCLOB theme (`bg-slate-950`, `bg-slate-900/80`, `border-slate-800`), crisp panel cards, high-density Bloomberg-terminal grid spacing (`gap-1.5`, `p-2`, `text-xs`).
  2. **Glanceable Telemetry**: Strict `font-mono tabular-nums` for all financial figures, strike prices, countdown timers, PnL percentages, and neural probabilities.
  3. **Cohesive Interactive States**: Seamless hover, focus-visible rings (`focus-visible:ring-2 focus-visible:ring-cyan-500/50`), active press, and disabled styling across *every* interactive element in the file.
  4. **Microstructure Color System**: Emerald (`#10b981`) for YES/Win, Crimson (`#f43f5e`) for NO/Loss, Amber (`#f59e0b`) for Quarantine/Wait, Cyan/Indigo (`#06b6d4`/`#6366f1`) for Dual-Brain ONNX inference.
  5. **Zero-Lag Reactivity**: High-performance CSS transforms and transitions (`transition-all duration-150`) that run smoothly at 60fps without triggering DOM thrashing.
  6. **Complete Domain Polish**: Always elevate the entire component (header, body metrics, buttons, empty states, tooltips) in a single unified PR.

---

## 📜 Architectural Learnings & Micro-UX Log

**Learning:** Hardware-style hold-to-activate controls (such as the 1.5-second hold-to-arm emergency kill switch in BabyBotConsole) that only handle mouse or touch events (`onMouseDown`/`onTouchStart`) are completely unusable for keyboard-only users and screen reader navigation. Supplying `onKeyDown` and `onKeyUp` listeners for `Space` and `Enter` keys (with `e.preventDefault()` and `!e.repeat` guards), adding `onBlur` safety cleanup, explicit descriptive `aria-label` instructions, and `focus-visible:ring-2` focus outlines ensures emergency safety controls remain fully accessible to all users.
**Action:** When implementing hold-to-activate or long-press controls, always wire `onKeyDown` and `onKeyUp` listeners for `Space` and `Enter`, add `onBlur` state reset, provide explicit `aria-label` instructions on how to trigger the hold action via keyboard, and include `focus-visible:ring-2` styling.

## 2026-09-18 - Regulatory Compliance Modal Tab Navigation & Action Controls Accessibility
**Learning:** Multi-section modal navigation tabs (such as Active Guardrails, Legal Handbook, and CFTC Audit Trail in ComplianceModal) require explicit `role="tablist"` container markup, `role="tab"`, `id`, `aria-selected`, `aria-controls`, and `focus-visible:ring-2` styling. Linking tabs to content panels marked with `role="tabpanel"` and `aria-labelledby` ensures screen reader users can discover and navigate regulatory compliance views cleanly.
**Action:** Always structure modal section tabs with `role="tablist"`, `role="tab"`, `id`, `aria-selected`, `aria-controls`, `focus-visible:ring-2`, and link them directly to `role="tabpanel"` containers with matching `aria-labelledby` IDs.

## 2026-09-14 - Summary Metric Filter Cards & Modal Close Controls Accessibility
**Learning:** Interactive summary cards that double as quick filters (such as "Today's Report" and "Total Live Report" cards in report modals) implemented as `<div>` containers are non-focusable and invisible to screen reader tab orders unless converted to semantic `<button type="button">` controls with explicit `aria-label` and `focus-visible:ring-2` styling.
**Action:** Always wrap interactive summary/metric filter cards in semantic `<button type="button">` elements, provide descriptive `aria-label` text, add `focus-visible:ring-2` outlines, and apply `text-left` to preserve card alignment.

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

## 2026-09-10 - Header Action Controls Keyboard Accessibility and ARIA Labels
**Learning:** Top navigation action controls combining icon graphics and text (e.g., Emergency Stop, Test Bot, Reports, Capital Reset, and Integrity Verification) often lack explicit `type="button"`, explicit `aria-label` descriptions, and color-matched focus ring indicators (`focus-visible:ring-2`), creating ambiguous screen reader context and low contrast during keyboard tab navigation.
**Action:** Always supply explicit `type="button"`, descriptive `aria-label` attributes, and theme-matched `focus-visible:ring-2` focus rings on top navigation header action controls.

## 2026-09-12 - Portfolio Account Switcher Tabs & ARIA Tabpanel Linking
**Learning:** Tab switches that toggle portfolio views (such as Paper Account vs Live Exchange Account) require proper `role="tablist"` container wrapping, `role="tab"`, `aria-selected`, `aria-controls`, and `focus-visible:ring-2` keyboard focus rings. Linking tab buttons directly to their respective content panels using `id`, `role="tabpanel"`, and `aria-labelledby` ensures screen reader users can seamlessly discover and navigate account views.
**Action:** Always structure account view toggles with `role="tablist"`, `role="tab"`, `aria-selected`, `aria-controls`, `focus-visible:ring-2`, and wrap panel bodies with `role="tabpanel"` and `aria-labelledby`.

## 2026-09-16 - Quick Action Trade Pill Buttons Accessibility
**Learning:** Compact quick-action pill buttons in banner toolbars (e.g., "Up 4.6¢" / "Down 95.4¢") often omit `type="button"`, explicit `aria-label`, and `title` tooltip attributes, causing screen readers to announce abbreviated text without market contract context during quick trading interactions.
**Action:** Always supply explicit `type="button"`, descriptive `aria-label` (e.g. `aria-label="Quick trade UP contract at 4.6¢"`), and matching `title` tooltips on quick action pill buttons.

## 2026-09-20 - Quantitative Strategy Dropdown Menu & Real-Time Telemetry Accessibility
**Learning:** Custom strategy selection dropdown menus require explicit keyboard `Escape` dismissal handlers, `aria-controls` container linking, `type="button"` and `aria-label` attributes on option items, and `font-mono tabular-nums` for real-time probability/EV metrics to prevent layout thrashing and preserve screen reader accessibility during high-frequency telemetry updates.
**Action:** Always wire `Escape` key handlers on custom dropdown menus, link dropdown buttons with `aria-controls`, add explicit `aria-label` text to options, and format live numeric readouts with `font-mono tabular-nums`.

## 2026-09-22 - Streaming Trade Tape Telemetry & Scroll Region Accessibility
**Learning:** Continuous streaming data views (such as real-time exchange trade tape prints) require `tabIndex={0}`, `role="region"`, explicit `aria-label`, and `focus-visible:ring-2` focus outlines on their scroll containers so keyboard-only users can focus and navigate historical prints. Formatting numerical trade figures with `tabular-nums` prevents layout jitter during high-frequency streaming updates, while providing a glanceable telemetry summary header gives instant terminal awareness.
**Action:** Always wrap scrollable streaming data containers in `tabIndex={0}` regions with `aria-label` and `focus-visible:ring-2` outlines, apply `tabular-nums` to financial data columns, and include a glanceable telemetry summary bar above the table.
