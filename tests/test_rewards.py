"""rewards.py 的單元測試 —— 本機 CPU 執行,只需 pytest。

覆蓋:答對/答錯、格式壞掉、千分位逗號、小數、負號、單位雜訊、多數字混雜、
多個 <answer> block、空 completion、conversational vs 純字串兩種輸入形狀、
batch 行為、未知 kwargs 相容(TRL 版本間參數漂移)。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rewards import (  # noqa: E402
    CORRECTNESS_SCORE,
    NUMBER_ONLY_SCORE,
    SOFT_FORMAT_SCORE,
    STRICT_FORMAT_SCORE,
    correctness_reward,
    extract_answer_block,
    extract_final_number,
    extract_gold_answer,
    number_only_reward,
    numbers_equal,
    soft_format_reward,
    strict_format_reward,
)

# ---------------------------------------------------------------- fixtures

GOOD = (
    "<reasoning>\n"
    "Natalia sold 48/2 = 24 clips in May.\n"
    "48 + 24 = 72 clips altogether.\n"
    "</reasoning>\n"
    "<answer>\n72\n</answer>"
)
WRONG = GOOD.replace("<answer>\n72\n</answer>", "<answer>\n71\n</answer>")
COMMA = "<reasoning>\n12 x 103 = 1,236 minus 2.\n</reasoning>\n<answer>\n1,234\n</answer>"
INLINE = "<reasoning>x</reasoning><answer>7</answer>"
NO_TAG_CORRECT = "Let me think. 48 + 24 = 72. The answer is 72"


def conv(*texts):
    """包成 TRL conversational 形狀:每個 completion 是一則 assistant 訊息。"""
    return [[{"role": "assistant", "content": t}] for t in texts]


# ---------------------------------------------------------- 抽取 helpers


class TestExtractGoldAnswer:
    def test_gsm8k_raw_answer(self):
        raw = "Natalia sold 48/2 = <<48/2=24>>24 clips in May.\n#### 72"
        assert extract_gold_answer(raw) == 72.0

    def test_comma_after_hash(self):
        assert extract_gold_answer("#### 1,080") == 1080.0

    def test_no_marker_no_number(self):
        assert extract_gold_answer("no marker here") is None

    def test_already_extracted(self):
        assert extract_gold_answer("72") == 72.0
        assert extract_gold_answer(72) == 72.0
        assert extract_gold_answer(None) is None


class TestExtractAnswerBlock:
    def test_strips_whitespace(self):
        assert extract_answer_block("<answer>  72  </answer>") == "72"

    def test_missing_tag(self):
        assert extract_answer_block("no tags at all") is None
        assert extract_answer_block("") is None

    def test_multiple_blocks_takes_last(self):
        text = "<answer>1</answer> then really: <answer>2</answer>"
        assert extract_answer_block(text) == "2"

    def test_multiline_block(self):
        assert extract_answer_block("<answer>\n72\n</answer>") == "72"


class TestExtractFinalNumber:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("$1,234.50", 1234.5),
            ("-5 degrees", -5.0),
            ("50%", 50.0),
            ("3 + 4 = 7", 7.0),  # 多個數字取最後一個
            ("72 clips", 72.0),
            ("0.5", 0.5),
            (".5", 0.5),  # 無前導零的小數(regression:曾被誤讀成 5.0)
            ("forty-two", None),
            ("", None),
            (None, None),
        ],
    )
    def test_extraction(self, text, expected):
        assert extract_final_number(text) == expected


class TestNumbersEqual:
    def test_equal(self):
        assert numbers_equal(72.0, 72.0)

    def test_tolerance(self):
        assert numbers_equal(18.0, 18.000000001)

    def test_not_equal(self):
        assert not numbers_equal(18.0, 18.1)

    def test_large_integers_off_by_one_not_equal(self):
        # regression:rel_tol=1e-6 曾讓 >=1e6 的差 1 被判相等
        assert not numbers_equal(999999.0, 1000000.0)
        assert not numbers_equal(2000001.0, 2000000.0)

    def test_none(self):
        assert not numbers_equal(None, 5.0)
        assert not numbers_equal(5.0, None)
        assert not numbers_equal(None, None)


# ------------------------------------------------------ correctness_reward


class TestCorrectnessReward:
    def test_correct_conversational(self):
        assert correctness_reward(
            prompts=conv("Q"), completions=conv(GOOD), answer=["72"]
        ) == [CORRECTNESS_SCORE]

    def test_correct_plain_string(self):
        assert correctness_reward(completions=[GOOD], answer=["72"]) == [CORRECTNESS_SCORE]

    def test_wrong_answer(self):
        assert correctness_reward(completions=conv(WRONG), answer=["72"]) == [0.0]

    def test_comma_number(self):
        assert correctness_reward(completions=conv(COMMA), answer=["1234"]) == [
            CORRECTNESS_SCORE
        ]

    def test_decimal_vs_int(self):
        c = "<reasoning>\nx\n</reasoning>\n<answer>72.0</answer>"
        assert correctness_reward(completions=conv(c), answer=["72"]) == [CORRECTNESS_SCORE]

    @pytest.mark.parametrize(
        ("block", "gold"),
        [("72 clips", "72"), ("$18", "18"), ("-5", "-5")],
    )
    def test_unit_noise_and_negative(self, block, gold):
        c = f"<reasoning>\nx\n</reasoning>\n<answer>{block}</answer>"
        assert correctness_reward(completions=conv(c), answer=[gold]) == [CORRECTNESS_SCORE]

    def test_leading_dot_decimal(self):
        # regression:".5" 曾被讀成 5.0 → 對 gold "5" 給出假陽性 2.0
        c = "<reasoning>\nx\n</reasoning>\n<answer>.5</answer>"
        assert correctness_reward(completions=conv(c), answer=["5"]) == [0.0]
        assert correctness_reward(completions=conv(c), answer=["0.5"]) == [CORRECTNESS_SCORE]

    def test_raw_gold_with_hash_marker(self):
        raw_gold = "Natalia ... altogether.\n#### 72"
        assert correctness_reward(completions=conv(GOOD), answer=[raw_gold]) == [
            CORRECTNESS_SCORE
        ]

    def test_missing_answer_tag_gets_zero_even_if_number_correct(self):
        # pin 住 strict 語意:correctness 必須從 <answer> block 抽,沒 tag 不給分
        assert correctness_reward(completions=conv(NO_TAG_CORRECT), answer=["72"]) == [0.0]

    def test_mixed_batch(self):
        out = correctness_reward(
            completions=conv(GOOD, WRONG, COMMA), answer=["72", "72", "1234"]
        )
        assert out == [CORRECTNESS_SCORE, 0.0, CORRECTNESS_SCORE]
        assert len(out) == 3


# ---------------------------------------------------- strict_format_reward


class TestStrictFormatReward:
    def test_multiline_reasoning_matches(self):
        # pin 住 DOTALL 修正:多行 reasoning 必須拿到 strict 分
        assert strict_format_reward(completions=conv(GOOD)) == [STRICT_FORMAT_SCORE]

    def test_trailing_newline_tolerated(self):
        assert strict_format_reward(completions=conv(GOOD + "\n")) == [STRICT_FORMAT_SCORE]

    def test_inline_tags_fail(self):
        assert strict_format_reward(completions=conv(INLINE)) == [0.0]

    def test_preamble_fails(self):
        assert strict_format_reward(completions=conv("Sure! " + GOOD)) == [0.0]

    def test_trailing_junk_fails(self):
        assert strict_format_reward(completions=conv(GOOD + " extra")) == [0.0]


# ------------------------------------------------------ soft_format_reward


class TestSoftFormatReward:
    def test_inline_tags_pass(self):
        assert soft_format_reward(completions=conv(INLINE)) == [SOFT_FORMAT_SCORE]

    def test_surrounding_noise_passes(self):
        noisy = "Sure! " + INLINE + " Hope that helps."
        assert soft_format_reward(completions=conv(noisy)) == [SOFT_FORMAT_SCORE]

    def test_strict_example_also_passes(self):
        assert soft_format_reward(completions=conv(GOOD)) == [SOFT_FORMAT_SCORE]

    def test_missing_close_tag_fails(self):
        assert soft_format_reward(completions=conv("<reasoning>x</reasoning><answer>7")) == [0.0]

    def test_wrong_order_fails(self):
        swapped = "<answer>\n5\n</answer>\n<reasoning>\nx\n</reasoning>"
        assert soft_format_reward(completions=conv(swapped)) == [0.0]


# ----------------------------------------------------- number_only_reward


class TestNumberOnlyReward:
    @pytest.mark.parametrize("block", ["72", "1,234", "-5", "3.14", ".5"])
    def test_pure_numbers_pass(self, block):
        c = f"<reasoning>\nx\n</reasoning>\n<answer>\n{block}\n</answer>"
        assert number_only_reward(completions=conv(c)) == [NUMBER_ONLY_SCORE]

    @pytest.mark.parametrize("block", ["72 clips", "$18", "about 72"])
    def test_non_pure_blocks_fail(self, block):
        c = f"<reasoning>\nx\n</reasoning>\n<answer>{block}</answer>"
        assert number_only_reward(completions=conv(c)) == [0.0]

    def test_missing_tag_fails(self):
        assert number_only_reward(completions=conv(NO_TAG_CORRECT)) == [0.0]


# ----------------------------------------------------------- edge / batch

ALL_FORMAT_FUNCS = [strict_format_reward, soft_format_reward, number_only_reward]


class TestEdgeCases:
    def test_empty_completion_all_zero_no_exception(self):
        for fn in ALL_FORMAT_FUNCS:
            assert fn(completions=conv("")) == [0.0]
        assert correctness_reward(completions=conv(""), answer=["72"]) == [0.0]

    def test_unknown_kwargs_tolerated(self):
        # TRL 0.22↔0.24↔1.x 會多傳 completions_ids / trainer_state / 未來欄位
        extra = {
            "completions_ids": [[1, 2]],
            "trainer_state": object(),
            "some_future_column": ["x"],
        }
        for fn in ALL_FORMAT_FUNCS:
            assert fn(completions=conv(GOOD), **extra) == [pytest.approx(0.5)]
        assert correctness_reward(
            prompts=conv("Q"), completions=conv(GOOD), answer=["72"], **extra
        ) == [CORRECTNESS_SCORE]

    def test_conversational_and_string_shapes_agree(self):
        texts = [GOOD, WRONG, "", NO_TAG_CORRECT]
        answers = ["72", "72", "72", "72"]
        for fn in ALL_FORMAT_FUNCS:
            assert fn(completions=conv(*texts)) == fn(completions=list(texts))
        assert correctness_reward(
            completions=conv(*texts), answer=answers
        ) == correctness_reward(completions=list(texts), answer=answers)

    def test_batch_shape_and_types(self):
        texts = [GOOD, WRONG, "", NO_TAG_CORRECT]
        for fn in ALL_FORMAT_FUNCS:
            out = fn(completions=conv(*texts))
            assert len(out) == 4
            assert all(isinstance(x, float) for x in out)
        out = correctness_reward(completions=conv(*texts), answer=["72"] * 4)
        assert len(out) == 4
        assert all(isinstance(x, float) for x in out)

    def test_total_reward_budget(self):
        # 一個完美 completion 的滿分是 3.5(2.0 + 0.5 + 0.5 + 0.5)
        perfect = GOOD
        total = (
            correctness_reward(completions=conv(perfect), answer=["72"])[0]
            + strict_format_reward(completions=conv(perfect))[0]
            + soft_format_reward(completions=conv(perfect))[0]
            + number_only_reward(completions=conv(perfect))[0]
        )
        assert total == pytest.approx(3.5)
