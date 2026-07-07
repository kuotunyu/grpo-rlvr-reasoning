# GSM8K 評測報告 — base vs GRPO 訓練後

- 資料:`openai/gsm8k`(main)test split 前 200 題(訓練管線零接觸,只在本評測使用)
- 解碼:greedy(`do_sample=False`),max_new_tokens=?
- 環境:? / dtype=? / 產生於 —(尚未執行)
- base:`— pending —`
- trained:`— pending —`

| 指標 | Base | GRPO 訓練後 | Δ |
|---|---|---|---|
| Strict accuracy(`<answer>` 內數字正確) | — pending — | — pending — | — |
| Flexible accuracy(全文最後一個數字) | — pending — | — pending — | — |
| 格式遵循率(soft:tag 依序出現) | — pending — | — pending — | — |
| 格式遵循率(strict:完整結構) | — pending — | — pending — | — |
| 平均輸出 tokens(至第一個 EOS) | — pending — | — pending — | — |

逐題生成記錄:`results/eval_generations_base.jsonl`、`results/eval_generations_trained.jsonl`。

重新產生本報告:
```bash
python eval/run_eval.py --trained-model <HF_USERNAME>/qwen2.5-3b-grpo-gsm8k
```
