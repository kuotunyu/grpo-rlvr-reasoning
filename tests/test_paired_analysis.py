import math

import pytest

from eval.analyze_paired import analyze, exact_mcnemar, validate_pairs


def _row(idx, *, strict, tokens=10):
    return {
        "idx": idx,
        "question": f"q{idx}",
        "gold": float(idx),
        "completion": f"<answer>{idx}</answer>",
        "n_tokens": tokens,
        "strict_correct": strict,
        "flexible_correct": strict,
        "soft_format": strict,
        "strict_format": strict,
    }


def test_exact_mcnemar_all_three_changes_favor_trained():
    base = [_row(i, strict=False) for i in range(3)]
    trained = [_row(i, strict=True) for i in range(3)]
    result = exact_mcnemar(base, trained, "strict_correct")
    assert result["base_only"] == 0
    assert result["trained_only"] == 3
    assert result["p_value"] == 0.25


def test_exact_mcnemar_no_discordant_pairs():
    base = [_row(0, strict=True)]
    trained = [_row(0, strict=True)]
    assert exact_mcnemar(base, trained, "strict_correct")["p_value"] == 1.0


def test_validate_pairs_rejects_different_questions():
    base = [_row(0, strict=True)]
    trained = [_row(0, strict=True)]
    trained[0]["question"] = "different"
    with pytest.raises(ValueError, match="Pair mismatch"):
        validate_pairs(base, trained)


def test_analyze_reports_paired_token_delta():
    base = [_row(0, strict=False, tokens=20), _row(1, strict=True, tokens=30)]
    trained = [_row(0, strict=True, tokens=15), _row(1, strict=True, tokens=25)]
    result = analyze(base, trained)
    token = result["token_delta_trained_minus_base"]
    assert token["mean"] == -5
    assert token["median"] == -5
    assert math.isclose(token["ci95_low"], -5)
    assert math.isclose(token["ci95_high"], -5)
    strict = result["metrics"]["strict_correct"]
    assert strict["base_rate"] == 0.5
    assert strict["trained_rate"] == 1.0
