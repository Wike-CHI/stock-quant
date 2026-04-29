#!/usr/bin/env python3
"""
Context Injector Hook for Harness Engineering Framework.

UserPromptSubmit hook that injects project state context at the start of each session.

This implements the "Context Budget" and "Environment Context Injection" principles
from LangChain's research: agents perform better when they know about their environment,
current state, and active tasks.

Hook output format:
- {"systemMessage": "..."} to inject context without blocking
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def get_git_info():
    """Get current git branch and recent commits."""
    info = {}
    try:
        branch = subprocess.check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            stderr=subprocess.DEVNULL, timeout=5
        ).decode().strip()
        info['branch'] = branch
    except (subprocess.CalledProcessError, FileNotFoundError):
        info['branch'] = 'unknown (not a git repo)'

    try:
        recent = subprocess.check_output(
            ['git', 'log', '--oneline', '-5'],
            stderr=subprocess.DEVNULL, timeout=5
        ).decode().strip()
        info['recent_commits'] = recent
    except (subprocess.CalledProcessError, FileNotFoundError):
        info['recent_commits'] = ''

    return info


def get_project_state():
    """Scan for project state indicators."""
    state = {}
    cwd = Path.cwd()

    # Check for active specs
    specs_dir = cwd / 'docs' / 'specs'
    if specs_dir.exists():
        specs = list(specs_dir.glob('*.md'))
        if specs:
            state['active_specs'] = [s.name for s in sorted(specs, key=lambda x: x.stat().st_mtime, reverse=True)[:5]]

    # Check for active contracts
    contracts_dir = cwd / 'docs' / 'contracts'
    if contracts_dir.exists():
        contracts = [c for c in contracts_dir.glob('*.md') if c.name != 'TEMPLATE.md']
        if contracts:
            state['active_contracts'] = [c.name for c in sorted(contracts, key=lambda x: x.stat().st_mtime, reverse=True)[:5]]

    # Check for active plans
    plans_dir = cwd / 'docs' / 'plans'
    if plans_dir.exists():
        plans = list(plans_dir.glob('*.md'))
        if plans:
            state['active_plans'] = [p.name for p in sorted(plans, key=lambda x: x.stat().st_mtime, reverse=True)[:5]]

    return state


def main():
    parts = []

    # Git info
    git_info = get_git_info()
    if git_info.get('branch'):
        parts.append(f"Git branch: {git_info['branch']}")
    if git_info.get('recent_commits'):
        parts.append(f"Recent commits:\n{git_info['recent_commits']}")

    # Project state
    state = get_project_state()
    if state.get('active_specs'):
        parts.append(f"Active specs: {', '.join(state['active_specs'])}")
    if state.get('active_contracts'):
        parts.append(f"Active contracts: {', '.join(state['active_contracts'])}")
    if state.get('active_plans'):
        parts.append(f"Active plans: {', '.join(state['active_plans'])}")

    if not parts:
        print(json.dumps({}))
        return

    message = (
        "Project context:\n"
        + "\n".join(parts)
        + "\n\nUse this context to understand the current state. "
        + "Read relevant specs/contracts/plans as needed (context budget: only read what you need)."
    )

    print(json.dumps({"systemMessage": message}))


if __name__ == '__main__':
    main()
