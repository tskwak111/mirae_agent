import json
from pathlib import Path

from finproof.cli.main import _parser, _run_main
from finproof.evaluation.runner import EvaluationMode


def test_parser_accepts_canonical_evaluate_command() -> None:
    args = _parser().parse_args(
        [
            "evaluate",
            "--suite",
            "canonical",
            "--output",
            "artifacts/evaluation/canonical.json",
        ]
    )

    assert vars(args) == {
        "command": "evaluate",
        "suite": "canonical",
        "output": Path("artifacts/evaluation/canonical.json"),
        "mode": EvaluationMode.END_TO_END,
    }


def test_evaluate_dispatches_exact_suite_mode_and_output(
    tmp_path: Path,
    capsys: object,
) -> None:
    output = tmp_path / "report.json"
    calls: list[tuple[str, Path, EvaluationMode]] = []

    def evaluator(suite: str, destination: Path, mode: EvaluationMode) -> None:
        calls.append((suite, destination, mode))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps({"suite": suite}) + "\n", encoding="utf-8")

    assert (
        _run_main(
            [
                "evaluate",
                "--suite",
                "canonical",
                "--output",
                str(output),
                "--mode",
                "plan-only",
            ],
            evaluator=evaluator,
        )
        == 0
    )
    assert calls == [("canonical", output, EvaluationMode.PLAN_ONLY)]
    assert json.loads(output.read_text(encoding="utf-8")) == {"suite": "canonical"}
