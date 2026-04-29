---
description: Build the most recent specification using the sprint workflow
argument-hint: Optional - specific spec file in docs/specs/ to build
---

# Build Feature

Implement a feature using the Generator-Evaluator cycle.

**Target**: $ARGUMENTS (if empty, use the most recent spec in `docs/specs/`)

## Process

### 1. Read Spec

Read the target specification from `docs/specs/`. If no argument provided, find the most recently modified spec file.

### 2. Sprint Contract

Check if a contract exists in `docs/contracts/` for this feature:
- If exists: Read it and proceed to build
- If not exists: Create a contract by negotiating between Generator and Evaluator perspectives:
  - What specific items are in scope for this sprint?
  - What acceptance criteria will be tested?
  - What verification methods will be used?

### 3. Build Cycle

Repeat up to 3 times:

1. **Build**: Invoke the generator agent to implement the sprint
2. **Self-verify**: Generator verifies its own work
3. **Evaluate**: Invoke the evaluator agent to test against the contract
4. **Grade**: Check if score >= 80/100
   - If PASS: Sprint complete
   - If FAIL: Feed failures back to generator for fixing

### 4. Max Iterations

If 3 iterations fail:
- Pause and report accumulated failures to user
- Suggest: simplify scope, break into smaller sprints, or manual intervention
- Do NOT continue iterating

### 5. Complete

If sprint passes:
- Update the contract's sprint log
- Ask user if they want to run the doc-gardener agent for freshness check
