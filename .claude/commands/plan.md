---
description: Create a feature specification from a brief description
argument-hint: Feature description (1-4 sentences)
---

# Plan Feature

Create a feature specification from: $ARGUMENTS

## Process

1. Invoke the planner agent with the description above
2. The planner will:
   - Ask clarifying questions if the description is ambiguous
   - Research existing codebase patterns
   - Produce a structured spec in `docs/specs/<feature-name>.md`
   - Create sprint tasks with dependencies via TaskCreate
3. Present the spec to the user for review
4. If approved, the user can proceed with `/build` or `/sprint`

**Do NOT begin implementation.** This command only produces a plan and specification.

## Spec Structure

The spec will include:
- Problem statement
- User stories
- Machine-verifiable acceptance criteria
- Component boundaries
- Data flow
- Error handling
- Edge cases (minimum 3)
- Dependencies
