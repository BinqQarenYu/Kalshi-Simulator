---
name: Autonomous Self-Verification Loop Skill (ASVL) - Antigravity Edition
description: Autonomous end-to-end self-verification loop skill for goal-based task execution, automated testing, continuous evaluation, and definitive completion gates.
---

# Autonomous Self-Verification Loop Skill (ASVL) - Antigravity Edition

## 1. Goal-Based Input Architecture
Do not execute commands as a series of micro-tasks. Immediately convert every incoming request into a high-level Goal-Based structure:
- **Goal**: A clear, high-level description of the ultimate outcome.
- **Success Criteria**: A list of 3–5 specific, quantifiable, and testable outcomes required to satisfy the goal.
- **Context**: Relevant background, constraints, codebase state, and active workspace parameters.

## 2. Self-Verification & Testing Setup
Before modifying or creating any code, configure an automated mechanism to verify your work. Do not rely on human review.
- **Project-Specific Test Harness**: Adhere strictly to the project rules defined in `autonomousself.md`. Run `pytest tests/` for backend verification, and `npm run typecheck` + `npm run build` for frontend verification. Do not invent alternative test commands.
- **Continuous Evaluation Cycle**: Embed execution in a continuous loop:
  `Build ──> Verify ──> Fix ──> Re-Verify ──> Complete`
- **Strict Instruction**: Never ask the user to test or confirm if code works; execute the verification autonomously using available system tools. Review `autonomousself.md` for specific trading standard constraints during implementation.

## 3. Antigravity-Native Autonomy Rules
During execution, operate as a fully autonomous agent thread within the Antigravity engine without prompting for intermediate human approval:
- **End-to-End Task Execution**: Do not yield control, request mid-task approval, or return partial progress. Continuously chain internal agent steps, terminal commands, and tool calls until all success criteria are satisfied.
- **Antigravity Tooling & Sensible Defaults**: Independently select and invoke available platform capabilities (e.g., local shell execution, workspace search, file mutations). If environment details, configuration keys, or implementation variables are unspecified, apply industry-standard defaults without halting execution.
- **Autonomous Error Recovery**: If build steps fail, terminal commands error out, or verification loops detect regressions, inspect execution logs, resolve issues, and immediately re-trigger the verification loop.
- **System Blocker Escalation**: Yield execution control to the user ONLY if you hit an unrecoverable system boundary—such as missing external API credentials, missing system privileges, or an unresolvable platform blocker.

## 4. Definitive Completion Gates
Exit the autonomous loop and return control to the user ONLY when ALL completion conditions are met:

### Complete When:
- [ ] All success criteria from the goal are met and verified.
- [ ] You have actively executed and verified the work yourself (tests, terminal outputs, or simulations).
- [ ] No known bugs, compile warnings, or broken features remain.
- [ ] Code is clean, optimized, and fully documented.
- [ ] The deliverable is ready for immediate human deployment or use.

### Not Complete If:
- [ ] You assume or guess it works without running verification tools.
- [ ] Outstanding TODOs or placeholder comments remain in the codebase.
- [ ] You prompt the user for manual testing, verification, or validation help.

## 5. Execution Loop Reference Template
Process all implementation tasks using this internal step-by-step cycle:
1. **PLAN**: Break the goal into actionable, sequential steps and map dependencies.
2. **BUILD**: Implement code, logic, configurations, or scripts.
3. **VERIFY**: Run automated tests, shell checks, or diagnostic scripts.
4. **COMPARE**: Evaluate actual outputs against the success criteria checklist.
5. **FIX**: If gaps or errors exist, isolate the issue and loop back to Step 2 (BUILD).
6. **COMPLETE**: Once all criteria pass, document the changes and yield control with a fully verified deliverable.
