#!/usr/bin/env python3
"""
Pre-Completion Checklist Hook for Harness Engineering Framework.

PostToolUse hook that injects a verification reminder when a task is marked complete.

This implements the "Self-Verify First" golden principle from LangChain's research:
models are biased toward their first plausible solution. Forcing a verification
checklist before marking work done catches issues that would otherwise slip through.

Hook output format:
- {"systemMessage": "..."} to inject context without blocking
"""

import json
import sys


CHECKLIST = [
    "1. Code compiles/builds without errors?",
    "2. All tests pass (both existing and new)?",
    "3. All acceptance criteria from the contract are met?",
    "4. No debug artifacts left (console.log, TODO, temporary code)?",
    "5. Documentation updated if behavior changed?",
]


def main():
    # Read hook input from stdin
    try:
        input_data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        print(json.dumps({}))
        return

    # Check if this is a TaskUpdate with status=completed
    tool_name = input_data.get('tool_name', '')
    tool_input = input_data.get('tool_input', {})

    if tool_name != 'TaskUpdate':
        print(json.dumps({}))
        return

    status = tool_input.get('status', '')
    if status != 'completed':
        print(json.dumps({}))
        return

    # Inject pre-completion checklist
    message = (
        "Pre-completion checklist — verify ALL items before confirming done:\n"
        + "\n".join(CHECKLIST)
        + "\n\nIf any item fails, fix it before marking the task complete."
    )

    print(json.dumps({"systemMessage": message}))


if __name__ == '__main__':
    main()
