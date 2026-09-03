from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_latest_official_rules_are_versioned_without_rewriting_history() -> None:
    decisions = (ROOT / "docs/10_DECISION_LOG.md").read_text(encoding="utf-8")
    notice = (
        ROOT / "source_material/official_notices/2026-08-24-data-refresh-and-runtime-rules.md"
    ).read_text(encoding="utf-8")
    normalized_decisions = decisions.lower()

    assert "| D-006 | 2026-08-07 | FROZEN | current = 2026-07-11 snapshot" in decisions
    assert "2026-08-24 | OFFICIAL_OVERRIDE" in decisions
    assert "domestic/public=2026-08-22" in decisions
    assert "overseas=2026-08-23" in decisions
    assert "du_er_1d" in normalized_decisions
    assert "never annualized" in normalized_decisions
    assert "code-table meanings are not queried or guessed" in normalized_decisions
    assert "zero or missing value is omitted or reported unavailable" in normalized_decisions
    assert "buyable_quantity is invalid" in normalized_decisions
    assert "ended or delisted evidence excludes a product" in normalized_decisions
    assert "HCX is mandatory for intent analysis and final answer wording" in decisions
    assert "295-second outer deadline" in decisions
    assert "A-005" in decisions
    assert "clean parent candidate commit" in decisions
    assert "[데이터 관련 공지]" in notice
    assert "[해외 ETF 1년 수익률 Q&A]" in notice
