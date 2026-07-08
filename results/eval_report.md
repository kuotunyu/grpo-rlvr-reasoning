# GSM8K 評測報告 — base vs GRPO 訓練後

- 資料:`openai/gsm8k`(main)test split 前 200 題(訓練管線零接觸,只在本評測使用)
- 解碼:greedy(`do_sample=False`),max_new_tokens=768
- 環境:Tesla T4 / dtype=torch.bfloat16 / 產生於 2026-07-08T18:32:12
- base:`Qwen/Qwen2.5-3B-Instruct`
- trained:`steven0226/qwen2.5-3b-grpo-gsm8k`

| 指標 | Base | GRPO 訓練後 | Δ |
|---|---|---|---|
| Strict accuracy(`<answer>` 內數字正確) | 70.5% | 79.0% | +8.5% |
| Flexible accuracy(全文最後一個數字) | 76.0% | 79.5% | +3.5% |
| 格式遵循率(soft:tag 依序出現) | 83.5% | 91.0% | +7.5% |
| 格式遵循率(strict:完整結構) | 19.5% | 90.0% | +70.5% |
| 平均輸出 tokens(至第一個 EOS) | 283 | 261 | -22 |

逐題生成記錄:`results/eval_generations_base.jsonl`、`results/eval_generations_trained.jsonl`。

重新產生本報告:
```bash
python eval/run_eval.py --trained-model <HF_USERNAME>/qwen2.5-3b-grpo-gsm8k
```
