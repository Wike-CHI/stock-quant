---
description: Run the evaluator agent against current code state
argument-hint: Optional - specific contract or spec to evaluate against
---

# Quality Assurance

Run a full evaluation cycle against the current implementation.

**Target**: $ARGUMENTS (if empty, evaluate against all contracts in `docs/contracts/`)

## Process

### 1. Select Target

- If argument provided: Evaluate against the specified contract/spec
- If no argument: List all contracts in `docs/contracts/` and ask user to choose, or evaluate the most recent one

### 2. Invoke Evaluator

Launch the evaluator agent, which will:
1. Read the sprint contract criteria
2. Test with Playwright MCP (E2E browser testing)
3. Inspect with Chrome DevTools (console errors, network, performance)
4. Visual check with screenshots (if UI is involved)
5. Read and verify source code logic

### 3. Grade Report

The evaluator produces a structured report with:
- Per-criterion pass/fail status
- Overall score (0-100)
- Specific failure details with reproduction steps and suggested fixes

### 4. Next Steps

If score < 80:
- Offer to invoke `/build` to enter the fix loop
- Show the specific failures that need addressing

If score >= 80:
- Report success
- Offer to run doc-gardener for freshness check
