# SPDX-License-Identifier: LGPL-3.0-only
# Adapted from UnslothAI's Qwen2.5 3B GRPO notebook at revision
# ff0685ab2c1d604f5605ace8652aa42c1e6bb10b. Modified in 2026 to add robust
# numeric parsing, multiline-format handling, pure functions, and stable tests.

"""GSM8K GRPO(RLVR)訓練用:答案抽取 helpers + 4 個 reward functions。

此模組是整個專案的單一事實來源(single source of truth):
train_grpo_colab.ipynb(訓練)、eval/run_eval.py(評測)、tests/test_rewards.py(測試)
都 import 同一份 SYSTEM_PROMPT、抽取 regex 與獎勵函數。

設計約束:
- 純 stdlib(re / math),不 import torch/transformers —— 本機 CPU 即可跑 pytest。
- 無 print、無 I/O —— 訓練中的樣本記錄由 notebook 端的 wrapper 負責。
- 每個 reward function 符合 TRL GRPOTrainer(0.22–0.24)介面:
  以 keyword arguments 呼叫(prompts / completions / 資料集欄位,未知參數由
  **kwargs 吸收),回傳 len(completions) 個 float。
- trainer 端不變式:GRPOConfig 需維持 remove_unused_columns=False(預設值),
  且資料集的 gold 欄位必須命名為 `answer`,否則 correctness_reward 收不到標準答案。
"""

import math
import re

# 與 Unsloth 官方 GRPO 範例(源自 @willccbb gist)相同的 system prompt,
# 逐字保留 —— strict_format_reward 的 regex 與這個格式一一對應。
SYSTEM_PROMPT = """
Respond in the following format:
<reasoning>
...
</reasoning>
<answer>
...
</answer>
"""

# 獎勵值沿用 Unsloth 官方範例:correctness 2.0、其餘 0.5(滿分 3.5,
# 可驗證的 correctness 佔 57%,格式獎勵負責 cold-start 階段的 shaping)。
CORRECTNESS_SCORE = 2.0
STRICT_FORMAT_SCORE = 0.5
SOFT_FORMAT_SCORE = 0.5
NUMBER_ONLY_SCORE = 0.5

ANSWER_BLOCK_RE = re.compile(r"<answer>(.*?)</answer>", re.DOTALL)

# 數字 token:負號、千分位逗號、小數(含 ".5" 這種無前導零的寫法)。
# $/%/單位等雜訊不在 pattern 內,自然被略過。
NUMBER_RE = re.compile(r"-?(?:\d[\d,]*(?:\.\d+)?|\.\d+)")

# 完整 <reasoning>\n...\n</reasoning>\n<answer>\n...\n</answer> 結構,允許前後空白。
# 官方 gist 的版本沒有 re.DOTALL,`.*?` 跨不了換行,多行 reasoning(本專案要訓練的
# 目標行為)永遠不匹配 —— 此處刻意修正,tests 會 pin 住這個行為。
STRICT_FORMAT_RE = re.compile(
    r"\s*<reasoning>\n.*?\n</reasoning>\n<answer>\n.*?\n</answer>\s*", re.DOTALL
)

# 寬鬆版:兩組 tag 依序出現即可,前後可以有其他文字(partial credit)。
SOFT_FORMAT_RE = re.compile(r"<reasoning>.*?</reasoning>\s*<answer>.*?</answer>", re.DOTALL)

PURE_NUMBER_RE = re.compile(r"-?(?:\d[\d,]*(?:\.\d+)?|\.\d+)")


def _completion_text(completion):
    """把 TRL 的 conversational completion([{'role','content'}])或純字串統一成文字。

    tests 用純字串、GRPOTrainer 用 message list —— 過了這一層之後所有函數不再分支。
    """
    if isinstance(completion, str):
        return completion
    if isinstance(completion, list):
        if not completion:
            return ""
        last = completion[-1]
        if isinstance(last, dict):
            return last.get("content") or ""
    return str(completion)


def extract_answer_block(text):
    """取「最後一個」<answer>...</answer> 的內文(strip 後);沒有 tag 回傳 None。

    取最後一個是因為模型偶爾會複誦 system prompt 裡的格式範本,
    真正的作答在最後。
    """
    if not text:
        return None
    matches = ANSWER_BLOCK_RE.findall(text)
    return matches[-1].strip() if matches else None


def extract_final_number(text):
    """取文字中最後一個數字 token,正規化成 float;沒有數字回傳 None。

    處理千分位逗號(1,234)、小數、負號;$、%、單位等雜訊由 regex 自然略過。
    取「最後一個」與 lm-evaluation-harness 對 GSM8K 的 flexible-extract 慣例一致:
    像 "3 + 4 = 7" 這種算式,最後的數字才是結論。
    """
    if not text:
        return None
    matches = NUMBER_RE.findall(text)
    if not matches:
        return None
    try:
        return float(matches[-1].replace(",", ""))
    except ValueError:
        return None


def extract_gold_answer(answer_text):
    """從 GSM8K 的 answer 欄位取標準答案:'####' 之後的數字(去逗號)。

    也接受已經抽好的值("72"、72、72.0)—— 無論 dataset.map 是否先抽過都能用。
    """
    if answer_text is None:
        return None
    s = str(answer_text)
    if "####" in s:
        s = s.split("####")[-1]
    return extract_final_number(s)


def numbers_equal(a, b):
    """float 容差比對;任一邊是 None 回傳 False。

    不用字串等值比對:官方 demo 的 `r == a` 會把 "72.0" vs "72"、"$72"、"1,234"
    全都判錯,等於對格式正確、答案正確的 completion 注入獎勵雜訊。
    只用絕對容差(rel_tol=0):GSM8K 的數值在 float 下都是精確的,容差只需要
    吸收 72.0 vs 72 這種表示差;rel_tol 會讓 999999 vs 1000000 這種差 1 的
    大數被誤判為相等。
    """
    if a is None or b is None:
        return False
    return math.isclose(a, b, rel_tol=0.0, abs_tol=1e-6)


def correctness_reward(prompts=None, completions=None, answer=None, **kwargs):
    """答案正確 → CORRECTNESS_SCORE(2.0),否則 0。

    從最後一個 <answer> block 抽數字與 gold 比對;沒有 <answer> tag 一律 0 ——
    可驗證訊號與作答格式掛鉤,cold-start 階段由格式獎勵先把模型帶進格式。
    """
    completions = completions or []
    golds = answer if answer is not None else [None] * len(completions)
    scores = []
    for completion, gold in zip(completions, golds):
        try:
            block = extract_answer_block(_completion_text(completion))
            pred = extract_final_number(block) if block is not None else None
            ok = numbers_equal(pred, extract_gold_answer(gold))
        except Exception:
            ok = False
        scores.append(CORRECTNESS_SCORE if ok else 0.0)
    return scores


def strict_format_reward(completions=None, **kwargs):
    """完整符合 <reasoning>\\n...\\n</reasoning>\\n<answer>\\n...\\n</answer> → 0.5。"""
    scores = []
    for completion in completions or []:
        try:
            ok = STRICT_FORMAT_RE.fullmatch(_completion_text(completion)) is not None
        except Exception:
            ok = False
        scores.append(STRICT_FORMAT_SCORE if ok else 0.0)
    return scores


def soft_format_reward(completions=None, **kwargs):
    """兩組 tag 依序出現(前後允許其他文字)→ 0.5(partial credit)。"""
    scores = []
    for completion in completions or []:
        try:
            ok = SOFT_FORMAT_RE.search(_completion_text(completion)) is not None
        except Exception:
            ok = False
        scores.append(SOFT_FORMAT_SCORE if ok else 0.0)
    return scores


def number_only_reward(completions=None, **kwargs):
    """<answer> block 是純數字(允許負號/千分位/小數)→ 0.5。

    對應官方範例的 int_reward_func,但比 .isdigit() 寬 —— GSM8K 有非整數與
    帶千分位的答案。
    """
    scores = []
    for completion in completions or []:
        try:
            block = extract_answer_block(_completion_text(completion))
            ok = block is not None and PURE_NUMBER_RE.fullmatch(block.strip()) is not None
        except Exception:
            ok = False
        scores.append(NUMBER_ONLY_SCORE if ok else 0.0)
    return scores
