"""Validate private blind reports and write one aggregate-only summary."""

import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path
from typing import cast

from finproof.evaluation.holdout import (
    HoldoutCandidateIdentity,
    HoldoutManifest,
    summarize_holdout,
)
from finproof.evaluation.load import LoadReport
from finproof.evaluation.runner import EvaluationReport


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--evaluation-report", type=Path, required=True)
    parser.add_argument("--load-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    manifest_bytes = cast(Path, args.manifest).read_bytes()
    candidate_bytes = cast(Path, args.candidate).read_bytes()
    evaluation_bytes = cast(Path, args.evaluation_report).read_bytes()
    load_bytes = cast(Path, args.load_report).read_bytes()
    summary = summarize_holdout(
        HoldoutManifest.model_validate_json(manifest_bytes, strict=True),
        HoldoutCandidateIdentity.model_validate_json(candidate_bytes, strict=True),
        EvaluationReport.model_validate_json(evaluation_bytes, strict=True),
        LoadReport.model_validate_json(load_bytes, strict=True),
        evaluation_sha256=sha256(evaluation_bytes).hexdigest(),
        load_sha256=sha256(load_bytes).hexdigest(),
    )
    output = cast(Path, args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    temporary.write_text(summary.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    sys.stdout.write(json.dumps({"output": str(output)}, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
