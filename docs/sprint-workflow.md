# Sprint Workflow

Detailed description of the Plan-Build-Verify-Fix-Complete cycle.

---

## Overview

Each feature goes through a 6-phase sprint cycle. The cycle enforces the golden principles: spec before code, testable criteria, self-verify first, and contract-driven development.

## Phase 1: Plan

**Agent**: Planner
**Input**: 1-4 sentence description from user
**Output**: `docs/specs/<feature-name>.md`

The Planner agent:
1. Reads the brief description
2. Asks clarifying questions if ambiguous
3. Researches existing codebase patterns
4. Produces a structured spec containing:
   - Problem statement
   - User stories
   - Acceptance criteria (each must be machine-verifiable)
   - Component boundaries
   - Data flow
   - Error handling
   - Edge cases (minimum 3)
   - Dependencies

**Transition criteria**: Spec file written to `docs/specs/` and reviewed by user.

## Phase 2: Contract Negotiation

**Agents**: Generator + Evaluator
**Output**: `docs/contracts/<feature-name>.md`

Before any code is written:
1. The Generator proposes what it will build and how success will be verified
2. The Evaluator reviews the proposal to ensure:
   - Criteria are truly testable (not subjective)
   - Scope is bounded (not open-ended)
   - Verification methods are specified for each criterion
3. Both iterate until agreement
4. User approves the final contract

**Transition criteria**: Contract agreed by Generator, Evaluator, and User.

## Phase 3: Build

**Agent**: Generator
**Input**: Spec + Contract
**Output**: Source code changes + sprint report

The Generator:
1. Reads only the spec file and relevant existing code (context budget)
2. Implements ONE sprint (bounded by contract scope)
3. After implementing, runs self-verification:
   - Re-read the code
   - Verify it compiles/builds
   - Check against acceptance criteria
   - Run existing tests
4. Writes a brief sprint report (what was done, what was verified, what needs attention)

**Transition criteria**: Generator declares sprint complete with self-verification results.

## Phase 4: Verify

**Agent**: Evaluator
**Input**: Contract + Source code + Running application
**Output**: Grade report (0-100 scale)

The Evaluator uses a four-layer testing strategy:
1. **Unit level**: Read source code, verify logic correctness
2. **Integration level**: Use Playwright MCP for E2E testing
3. **Visual level**: Use zai-mcp-server for UI screenshot comparison (if applicable)
4. **Console level**: Use Chrome DevTools for errors, warnings, network issues

For each acceptance criterion:
- PASS: Criterion met, evidence documented
- FAIL: Criterion not met, specific failure details, reproduction steps, suggested fix

**Scoring**: Score = (passed criteria / total criteria) * 100
**Threshold**: 80/100

**Transition criteria**:
- Score >= 80: Proceed to Phase 6 (Complete)
- Score < 80: Proceed to Phase 5 (Fix)

## Phase 5: Fix Loop

**Agent**: Generator (with Evaluator feedback)
**Max iterations**: 3

1. Evaluator's failure report is fed to the Generator
2. Generator analyzes each failure, identifies root cause
3. Generator implements fixes
4. Generator self-verifies fixes
5. Return to Phase 4 (Verify)

**If 3 iterations fail**:
- Pause the sprint
- Report accumulated failures to user
- Suggest: (a) simplify the scope, (b) break into smaller sprints, (c) manual intervention
- Do NOT continue iterating — context is likely polluted

**Context reset guidance**: If the Generator has been working for a long time and shows signs of context anxiety (premature wrap-up, repetitive mistakes), consider:
- Summarizing progress to a file
- Starting a fresh session
- Having the new session read the spec, contract, and sprint log from files

## Phase 6: Complete

**Agent**: Doc Gardener (automatic)
**Output**: Updated documentation

1. Doc Gardener audits documentation freshness:
   - Code paths in docs still exist
   - New code has corresponding docs
   - Examples are current
2. Sprint log is recorded in the contract file
3. Tasks are marked complete
4. Sprint summary is produced:
   - What was built
   - Final evaluator score
   - Iterations used
   - Any remaining issues or tech debt noted

## Context Reset vs Compaction

| Strategy | When to Use | Pros | Cons |
|----------|-------------|------|------|
| **Compaction** | Normal operation, short sprints | Preserves continuity | Doesn't eliminate context anxiety |
| **Context Reset** | Long sessions, 3+ fix iterations, context anxiety | Clean slate, fresh attention | Requires handoff artifact to be thorough |

**Handoff artifact** (written to file before reset):
- Current sprint contract status
- What's been implemented
- What's still failing
- Next steps
- Key decisions made

The handoff artifact IS the spec + contract + sprint log files — this is why we persist them to disk rather than keeping them only in context.
