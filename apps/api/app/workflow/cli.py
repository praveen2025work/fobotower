"""Workflow command line.

    python -m app.workflow.cli validate   check the workflow YAML
    python -m app.workflow.cli show       print the steps, pauses and settings

Run from apps/api. Point FOBO_WORKFLOW_PATH at a copy to try an edit without
changing the checked-in file. Restart the API after editing: the workflow is
read once per process.
"""

import sys

from pydantic import ValidationError

from app.workflow.config import errors_of, read_workflow, workflow_path


def _validate() -> int:
    path = workflow_path()
    try:
        wf = read_workflow(path)
    except (ValidationError, ValueError) as exc:
        print(f"INVALID  {path}")
        for line in errors_of(exc):
            print(f"  - {line}")
        return 1
    print(f"VALID    {path}")
    print(f"  workflow {wf.name} v{wf.version}: {' -> '.join(wf.steps)}")
    print(f"  pauses for a person before: {', '.join(wf.pause_before)}")
    print(f"  reasoner: {wf.settings.reason.reasoner}")
    return 0


def _show() -> int:
    from app.workflow.registry import STEPS

    if _validate() != 0:
        return 1
    wf = read_workflow()
    print()
    for i, name in enumerate(wf.steps, 1):
        s = STEPS[name]
        tags = []
        if name in wf.pause_before:
            tags.append("PAUSE")
        if s.required_because:
            tags.append("required")
        if s.can_escalate:
            tags.append("can escalate")
        print(f"  {i}. {name:9} {s.label:16} {'[' + ', '.join(tags) + ']' if tags else ''}")
    print("\n  settings:")
    for section, values in wf.settings.model_dump(by_alias=True).items():
        print(f"    {section}: " + ", ".join(f"{k}={v}" for k, v in values.items()))
    return 0


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "validate"
    if cmd == "validate":
        return _validate()
    if cmd == "show":
        return _show()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
