# Token/Credit Conservation & Anti-Redundancy Rules

## 1. Anti-Redundancy Protocol (Highest Priority)
- **Never read a file back after editing it.** The tool confirmation output is the source of truth. A verification round-trip costs more tokens than the reassurance is worth.
- **Never re-summarize artifact contents after creating them.** Point to the artifact. Don't parrot it.
- **Never re-explain what the user just said.** Act on the request directly.
- **Never spawn a subagent for work that can be done in the current context.** Subagent spawns re-inject the full system prompt, multiplying token cost.
- **Never re-search for information already in context.** If a grep result or file view is in the current conversation, reference it — don't re-fetch.

## 2. Batch-First Tool Calls (Highest Impact)
- **All independent tool calls MUST be batched into a single turn.** Parallel `grep_search` + `view_file` + `list_dir` in one block. Never chain them sequentially when there are no data dependencies.
- **Every `view_file` call MUST use `StartLine`/`EndLine`.** Use `grep_search` first to find the right line range. Never read a full 500-line file when you need 20 lines.
- **Cap unbounded output.** Use `git log -n 10`, `head -n 50`, pipe through `Select-Object -First N`. Never let a command dump thousands of lines into context.

## 3. Subagent Spawn Governance
- **Prefer direct work over subagent delegation** for simple tasks (quick lookups, single-file edits, targeted searches).
- **Use `flash` model** for research lookups and file reading — not `pro` or `inherit` — unless the task genuinely requires deep reasoning.
- **Check `manage_subagents list`** before spawning to avoid redundant subagents. Send follow-up messages to idle subagents instead of spawning new ones.
- **Kill idle subagents immediately** after they complete their task to free resources.

## 4. Minimal Output Protocol
- **Act, don't announce.** If intent maps to a tool call, execute it. Don't describe what you're about to do in a paragraph before doing it.
- **Narration is allowed ONLY for:** debugging chain-of-thought, architectural decisions, security-sensitive edits, and when the user explicitly asks for explanation.
- **Tables over prose.** When summarizing results, use compact markdown tables instead of multi-paragraph descriptions.
- **No filler.** Remove "Let me", "I'll now", "Sure!", "Great question!", and similar zero-information phrases.

## 5. Context Window Hygiene
- **Grep first, then targeted read.** Never bulk-read files to find a function. Use `grep_search` to locate the line, then `view_file` with a tight range.
- **Use `find_by_name` before `list_dir` recursion.** Pattern-matching is cheaper than recursive directory listing.
- **Scope searches with `Includes`.** Always filter by file extension or path glob to avoid scanning irrelevant files.
- **Prefer `MatchPerLine: false`** (file-name-only mode) when you only need to know which files contain a term, not every matching line.

## 6. Override Conditions
- Any rule is suspended when the user explicitly asks for detail, explanation, or step-by-step walkthrough.
- Rules 1 and 4 auto-suspend on complex tasks: debugging, multi-file refactors, security-sensitive edits, and architectural decisions. Accuracy trumps conservation when the stakes are high.
