"""The red-line suite itself is a required, unconditionally blocking PR check."""
from pathlib import Path

import yaml

from scripts import quality_gate


ROOT = Path(__file__).resolve().parents[3]


def test_required_ci_step_blocks_every_pull_request():
    workflow = yaml.load((ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)
    assert "pull_request" in workflow["on"]
    job = workflow["jobs"]["backend"]
    assert "if" not in job
    assert job.get("continue-on-error", "false") == "false"
    steps = [step for step in job["steps"] if step.get("name") == "Required red-line contracts (RL)"]
    assert len(steps) == 1, "RL must have a named blocking step on every PR"
    step = steps[0]
    assert "if" not in step
    assert step.get("continue-on-error", "false") == "false"
    assert step["run"] == "python scripts/quality_gate.py --group redline --report quality/redline.json"
    checks = quality_gate.checks("redline", "python")
    assert {name for name, _, _ in checks} == {"redline_backend", "redline_frontend"}
    commands = {name: command for name, command, _ in checks}
    assert "backend/tests/redline" in commands["redline_backend"]
    assert "-m" in commands["redline_backend"] and "pytest" in commands["redline_backend"]
    # #273: the redline frontend tests load the same strict setup as `npm test`.
    assert commands["redline_frontend"][:4] == ["node", "--require", "./frontend/tests/setup.cjs", "--test"]
    expected = {str(path.relative_to(ROOT)) for path in (ROOT / "frontend/tests").glob("redline-*.test.cjs")}
    assert expected and set(commands["redline_frontend"][4:]) == expected
