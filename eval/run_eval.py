"""GSM8K 評測:base 模型 vs GRPO 訓練後模型的對照報告。

在 Colab 或本機 GPU(如 RTX 4090)皆可執行;判分邏輯全部 reuse rewards.py ——
與訓練時同一份 regex 與數字比對,單一判分來源。

用法(訓練完成後):
    python eval/run_eval.py --trained-model steven0226/qwen2.5-3b-grpo-gsm8k
    # 或兩台機器分開跑、之後合併報告:
    python eval/run_eval.py --models base
    python eval/run_eval.py --models trained --trained-model .../qwen2.5-3b-grpo-gsm8k
    # 或評測還沒 merge 的 LoRA checkpoint:
    python eval/run_eval.py --models trained --adapter /path/to/checkpoint-1000

輸出:
    results/eval_generations_{base,trained}.jsonl   逐題完整記錄(可稽核)
    results/eval_metrics_{base,trained}.json        彙總指標(供報告合併)
    results/eval_report.md                          對照表
"""

import argparse
import datetime
import gc
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rewards import (  # noqa: E402  (純 stdlib,不需要 GPU 環境)
    SOFT_FORMAT_RE,
    STRICT_FORMAT_RE,
    SYSTEM_PROMPT,
    extract_answer_block,
    extract_final_number,
    extract_gold_answer,
    numbers_equal,
)

RESULTS_DIR = ROOT / "results"


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base-model", default="Qwen/Qwen2.5-3B-Instruct")
    p.add_argument("--trained-model", default=None,
                   help="merged 模型的 HF repo id;省略時嘗試用 HF token 的 whoami 推得 "
                        "<user>/qwen2.5-3b-grpo-gsm8k")
    p.add_argument("--adapter", default=None,
                   help="LoRA adapter 路徑或 repo id;指定時 trained = base + adapter"
                        "(可直接評 Drive 上的 checkpoint,不必先 merge)")
    p.add_argument("--models", choices=["both", "base", "trained"], default="both")
    p.add_argument("--num-questions", type=int, default=200)
    p.add_argument("--max-new-tokens", type=int, default=768)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--dtype", choices=["auto", "bf16", "fp16", "fp32"], default="auto")
    p.add_argument("--load-in-4bit", action="store_true",
                   help="小 VRAM 的逃生門(數字會與 16bit 略有差異,報告中會註記)")
    p.add_argument("--out", default=str(RESULTS_DIR / "eval_report.md"))
    args = p.parse_args()
    if args.num_questions <= 0:
        p.error("--num-questions 必須 > 0")
    return args


def resolve_trained_repo(args):
    if args.trained_model:
        return args.trained_model
    try:
        from huggingface_hub import whoami

        user = whoami()["name"]
        repo = f"{user}/qwen2.5-3b-grpo-gsm8k"
        print(f"[info] --trained-model 未指定,依 whoami 推得:{repo}")
        return repo
    except Exception as e:
        raise SystemExit(
            "--trained-model 未指定且無法從 HF token 推得 username;"
            f"請明確指定 --trained-model(原因:{e})"
        )


def pick_dtype(name):
    import torch

    if name == "auto":
        if torch.cuda.is_available() and torch.cuda.is_bf16_supported():
            return torch.bfloat16
        return torch.float16
    return {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}[name]


def load_model(model_id, adapter, dtype, load_in_4bit):
    import torch  # noqa: F401
    from transformers import AutoModelForCausalLM, AutoTokenizer

    kwargs = {"torch_dtype": dtype, "device_map": "auto"}
    if load_in_4bit:
        from transformers import BitsAndBytesConfig

        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_compute_dtype=dtype
        )
    model = AutoModelForCausalLM.from_pretrained(model_id, **kwargs)
    if adapter:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, adapter)
    model.eval()

    tokenizer = AutoTokenizer.from_pretrained(model_id)
    tokenizer.padding_side = "left"  # decoder-only 的 batch 生成必須左 padding
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    return model, tokenizer


def load_questions(n):
    from datasets import load_dataset

    # 唯一允許接觸 gsm8k test split 的地方(訓練管線零接觸)
    ds = load_dataset("openai/gsm8k", "main", split="test").select(range(n))
    return [(x["question"], x["answer"]) for x in ds]


def grade(text, gold_raw):
    gold = extract_gold_answer(gold_raw)
    block = extract_answer_block(text)
    strict_correct = block is not None and numbers_equal(extract_final_number(block), gold)
    # flexible = 全文最後一個數字(lm-eval-harness flexible-extract 慣例),
    # 與 tag 完全無關 —— 對不吐 tag 的 base 模型才公平
    flexible_correct = numbers_equal(extract_final_number(text), gold)
    return {
        "strict_correct": bool(strict_correct),
        "flexible_correct": bool(flexible_correct),
        "soft_format": SOFT_FORMAT_RE.search(text) is not None,
        "strict_format": STRICT_FORMAT_RE.fullmatch(text) is not None,
    }


def evaluate_model(tag, model_id, adapter, questions, args):
    import torch

    dtype = pick_dtype(args.dtype)
    label = f"{model_id}" + (f" + adapter {adapter}" if adapter else "")
    print(f"\n===== 評測 [{tag}] {label}(dtype={dtype},greedy,"
          f"max_new_tokens={args.max_new_tokens})=====")
    model, tokenizer = load_model(model_id, adapter, dtype, args.load_in_4bit)
    eos_id = tokenizer.eos_token_id

    records = []
    for start in range(0, len(questions), args.batch_size):
        batch = questions[start : start + args.batch_size]
        prompts = [
            tokenizer.apply_chat_template(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": q},
                ],
                tokenize=False,
                add_generation_prompt=True,
            )
            for q, _ in batch
        ]
        enc = tokenizer(prompts, return_tensors="pt", padding=True).to(model.device)
        with torch.no_grad():
            out = model.generate(
                **enc,
                max_new_tokens=args.max_new_tokens,
                do_sample=False,           # greedy,完全 deterministic
                temperature=None,
                top_p=None,
                top_k=None,
                pad_token_id=eos_id,
            )
        gen = out[:, enc["input_ids"].shape[1] :]
        for i, (q, gold_raw) in enumerate(batch):
            row = gen[i].tolist()
            # 真實生成長度:數到第一個 EOS(pad=eos,提早結束的序列後面全是 padding)
            n_tokens = row.index(eos_id) if eos_id in row else len(row)
            text = tokenizer.decode(row, skip_special_tokens=True)
            rec = {"idx": start + i, "question": q, "gold": extract_gold_answer(gold_raw),
                   "completion": text, "n_tokens": n_tokens}
            rec.update(grade(text, gold_raw))
            records.append(rec)
        done = min(start + args.batch_size, len(questions))
        acc = sum(r["flexible_correct"] for r in records) / len(records)
        print(f"  {done}/{len(questions)}  flexible acc(累計)={acc:.1%}")

    n = len(records)
    metrics = {
        "tag": tag,
        "model": label,
        "num_questions": n,
        "strict_accuracy": sum(r["strict_correct"] for r in records) / n,
        "flexible_accuracy": sum(r["flexible_correct"] for r in records) / n,
        "soft_format_rate": sum(r["soft_format"] for r in records) / n,
        "strict_format_rate": sum(r["strict_format"] for r in records) / n,
        "mean_output_tokens": sum(r["n_tokens"] for r in records) / n,
        "max_new_tokens": args.max_new_tokens,
        "dtype": str(dtype),
        "load_in_4bit": bool(args.load_in_4bit),
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    gen_path = RESULTS_DIR / f"eval_generations_{tag}.jsonl"
    with open(gen_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(RESULTS_DIR / f"eval_metrics_{tag}.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    print(f"[saved] {gen_path}")

    # 依序評測:徹底釋放再載下一個模型,不讓兩個 3B 同時駐留
    del model
    gc.collect()
    torch.cuda.empty_cache()
    return metrics


def fmt_pct(x):
    return f"{x:.1%}"


def build_report(out_path, num_questions):
    """從 results/eval_metrics_*.json 組報告 —— base/trained 可以分次、分機器跑。"""
    loaded = {}
    for tag in ("base", "trained"):
        p = RESULTS_DIR / f"eval_metrics_{tag}.json"
        if p.exists():
            loaded[tag] = json.loads(p.read_text(encoding="utf-8"))

    # 一致性檢查:分次/分機器跑的兩份 metrics 必須同題數、同解碼長度才能比 Δ
    comparable = True
    warn = None
    if "base" in loaded and "trained" in loaded:
        diffs = [
            k for k in ("num_questions", "max_new_tokens")
            if loaded["base"].get(k) != loaded["trained"].get(k)
        ]
        if diffs:
            comparable = False
            warn = (
                f"> ⚠️ base 與 trained 的評測設定不一致({', '.join(diffs)}:"
                f"base={[loaded['base'].get(k) for k in diffs]},"
                f"trained={[loaded['trained'].get(k) for k in diffs]}),"
                "Δ 欄不予計算 —— 請用相同參數重跑其中一邊。"
            )

    def cell(tag, key, is_pct=True):
        if tag not in loaded:
            return "— pending —"
        v = loaded[tag][key]
        return fmt_pct(v) if is_pct else f"{v:.0f}"

    def delta(key, is_pct=True):
        if "base" not in loaded or "trained" not in loaded or not comparable:
            return "—"
        d = loaded["trained"][key] - loaded["base"][key]
        return (f"{d:+.1%}" if is_pct else f"{d:+.0f}")

    rows = [
        ("Strict accuracy(`<answer>` 內數字正確)", "strict_accuracy", True),
        ("Flexible accuracy(全文最後一個數字)", "flexible_accuracy", True),
        ("格式遵循率(soft:tag 依序出現)", "soft_format_rate", True),
        ("格式遵循率(strict:完整結構)", "strict_format_rate", True),
        ("平均輸出 tokens(至第一個 EOS)", "mean_output_tokens", False),
    ]
    env = loaded.get("trained") or loaded.get("base") or {}
    nq = env.get("num_questions", num_questions)  # 以 metrics 檔記錄的題數為準
    lines = [
        "# GSM8K 評測報告 — base vs GRPO 訓練後",
        "",
        f"- 資料:`openai/gsm8k`(main)test split 前 {nq} 題(訓練管線零接觸,只在本評測使用)",
        f"- 解碼:greedy(`do_sample=False`),max_new_tokens={env.get('max_new_tokens', '?')}",
        f"- 環境:{env.get('gpu', '?')} / dtype={env.get('dtype', '?')} / 產生於 {env.get('timestamp', '—(尚未執行)')}",
        f"- base:`{loaded.get('base', {}).get('model', '— pending —')}`",
        f"- trained:`{loaded.get('trained', {}).get('model', '— pending —')}`",
    ] + ([warn] if warn else []) + [
        "",
        "| 指標 | Base | GRPO 訓練後 | Δ |",
        "|---|---|---|---|",
    ]
    for name, key, is_pct in rows:
        lines.append(
            f"| {name} | {cell('base', key, is_pct)} | {cell('trained', key, is_pct)} | {delta(key, is_pct)} |"
        )
    lines += [
        "",
        "逐題生成記錄:`results/eval_generations_base.jsonl`、`results/eval_generations_trained.jsonl`。",
        "",
        "重新產生本報告:",
        "```bash",
        "python eval/run_eval.py --trained-model steven0226/qwen2.5-3b-grpo-gsm8k",
        "```",
        "",
    ]
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text("\n".join(lines), encoding="utf-8")
    print(f"[saved] {out_path}")
    if "base" in loaded and "trained" in loaded:
        print("\n" + "\n".join(lines[8:14]))


def main():
    args = parse_args()
    questions = None

    if args.models in ("both", "base"):
        questions = load_questions(args.num_questions)
        evaluate_model("base", args.base_model, None, questions, args)

    if args.models in ("both", "trained"):
        if questions is None:
            questions = load_questions(args.num_questions)
        if args.adapter:
            evaluate_model("trained", args.base_model, args.adapter, questions, args)
        else:
            evaluate_model("trained", resolve_trained_repo(args), None, questions, args)

    build_report(args.out, args.num_questions)


if __name__ == "__main__":
    main()
