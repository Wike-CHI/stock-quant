# Golden Principles

Non-negotiable rules enforced across all agents and workflows. These encode the core insights from OpenAI (Codex), Anthropic (3-agent architecture), and LangChain (self-verify loops).

---

## 1. Spec Before Code

No implementation without a written specification in `docs/specs/`.

**Why**: Models lose coherence without a clear target. A spec anchors the Generator and gives the Evaluator something concrete to test against. (OpenAI)

**How to apply**: The Planner agent always writes a spec before any code is written. If you're tempted to "just start coding," write the spec first.

## 2. Testable Acceptance Criteria

Every feature must have machine-verifiable pass/fail criteria.

**Why**: Subjective criteria like "looks good" lead to the evaluator grading generously. Machine-verifiable criteria force precision. (Anthropic)

**How to apply**: Each acceptance criterion in a sprint contract must specify a verification method: unit test, Playwright E2E, console check, visual comparison, or build success.

## 3. One Sprint at a Time

The Generator implements one feature, then the Evaluator tests before moving on.

**Why**: Long-running tasks cause context drift and "context anxiety" (premature wrap-up). Decomposing into sprints keeps the agent coherent. (Anthropic)

**How to apply**: Each sprint contract defines a bounded scope. The Generator completes one sprint, the Evaluator grades it, then the next sprint begins.

## 4. Self-Verify First

The Generator must self-verify before the Evaluator runs.

**Why**: Models are biased toward their first plausible solution. Forcing a self-check catches obvious issues before wasting evaluator cycles. (LangChain)

**How to apply**: After implementing, the Generator must: (1) re-read the code, (2) verify it compiles/builds, (3) check against the spec, (4) run tests if available.

## 5. Loop Awareness

If a file is edited 5+ times without progress, stop and reassess.

**Why**: Models can enter "doom loops" — making small variations to the same broken approach. The loop detection hook prevents this waste. (LangChain)

**How to apply**: The loop-detector hook blocks edits after 5 attempts. When blocked, reconsider the approach entirely rather than tweaking the same code.

## 6. Context Budget

Agents read only what they need, not the entire codebase.

**Why**: Context is a scarce resource. A massive instruction file挤掉任务空间, causing the agent to miss key constraints or optimize for the wrong things. (OpenAI)

**How to apply**: The Planner reads only relevant existing code. The Generator reads only the spec and contract. The Evaluator reads only the contract and relevant source files.

## 7. Progressive Disclosure

Documentation follows a 3-level pattern: summary → details → references.

**Why**: This is the "map, not encyclopedia" principle. A small entry point with pointers to deeper sources keeps context lean while preserving access to depth. (OpenAI)

**How to apply**: CLAUDE.md is the map (<80 lines). docs/ contains the details. Specs and contracts contain task-specific depth.

## 8. Doc Freshness

After each sprint, verify documentation matches code.

**Why**: Stale docs are worse than no docs — they mislead agents into implementing against wrong assumptions. (OpenAI "doc gardening")

**How to apply**: The doc-gardener agent runs after sprint completion. It checks that code paths referenced in docs still exist, examples still compile, and new features have documentation.

## 9. Fail Loudly

Hooks and agents report problems explicitly rather than silently degrading.

**Why**: Silent failures accumulate into technical debt that's expensive to fix later. Better to surface issues immediately. (OpenAI)

**How to apply**: Hooks block with clear reasons. Agents produce structured failure reports. No silent fallbacks or "it probably works" assumptions.

## 10. Contract-Driven

Sprint contracts define "done" before implementation begins.

**Why**: Without agreed-upon completion criteria, the Generator and Evaluator have different definitions of success. Contracts align expectations before code is written. (Anthropic)

**How to apply**: Before each sprint, the Generator proposes what it will build and how success is verified. The Evaluator reviews the proposal. Both agree before any code is written.
