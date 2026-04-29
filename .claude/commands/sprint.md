---
description: Execute a full Plan-Build-Verify sprint from a brief description
argument-hint: Feature description (1-4 sentences)
---

# Full Sprint

Execute the complete Plan -> Build -> Verify cycle for: $ARGUMENTS

## Sprint Phases

### Phase 1: Plan

Invoke the planner agent with the description. The planner will:
- Clarify ambiguities (ask the user questions first)
- Research the codebase
- Produce a spec in `docs/specs/<feature-name>.md`
- Create sprint tasks

**Gate**: User must approve the spec before proceeding.

### Phase 2: Contract Negotiation

Generate a sprint contract in `docs/contracts/<feature-name>.md`:
- Extract acceptance criteria from the spec
- Define scope (In Scope / Out of Scope)
- Specify verification methods for each criterion
- Set threshold: 80/100
- Set max iterations: 3

Present the contract to the user for approval.

**Gate**: User must approve the contract before proceeding.

### Phase 3: Build

Invoke the generator agent:
- Reads spec + contract
- Implements one sprint
- Self-verifies (re-read code, check build, verify against criteria)

### Phase 4: Verify

Invoke the evaluator agent:
- Reads contract
- Tests via four-layer strategy (unit, integration, visual, console)
- Grades each acceptance criterion
- Calculates score

### Phase 5: Fix Loop

If score < threshold (max 3 iterations):
1. Feed evaluator's failure report to generator
2. Generator analyzes root cause and fixes
3. Generator self-verifies fixes
4. Return to Phase 4

If 3 iterations fail:
- **STOP**. Do not continue.
- Report all accumulated failures to user
- Suggest: simplify scope, break into smaller sprints, manual intervention
- The context is likely polluted — a fresh session may help

### Phase 6: Complete

If sprint passes:
1. Update contract sprint log with final results
2. Mark tasks as completed
3. Invoke doc-gardener agent for freshness check
4. Produce sprint summary:
   - Feature built
   - Final evaluator score
   - Iterations used
   - Remaining issues or tech debt
   - Time to next sprint recommendation
