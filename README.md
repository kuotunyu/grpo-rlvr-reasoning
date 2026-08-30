# grpo-rlvr-reasoning

用 **GRPO**(Group Relative Policy Optimization)+ **可驗證獎勵**(RLVR)訓練
`Qwen/Qwen2.5-3B-Instruct` 在 GSM8K 上的數學推理,驗證 DeepSeek-R1 帶起的 RLVR 敘事:
單靠規則式獎勵(答對 + 格式,不用 reward model),reward 乾淨爬升、格式遵循率從
19.5% 衝到 90%。這裡也誠實記錄了一個反直覺的發現:**completion 長度並沒有隨訓練
無腦成長**,模型學到的其實是「難題多想、易題少想」的效率提升,詳見下方分析。

- 訓練:Google Colab Pro+(L4 GPU,延長訓練那段換 A100)× [Unsloth](https://unsloth.ai) GRPO × vLLM rollout
- 模型:🤗 [qwen2.5-3b-grpo-gsm8k](https://huggingface.co/steven0226/qwen2.5-3b-grpo-gsm8k)(merged 16bit)/
  [qwen2.5-3b-grpo-gsm8k-lora](https://huggingface.co/steven0226/qwen2.5-3b-grpo-gsm8k-lora)(LoRA adapter)

> **授權邊界:**GitHub 原始碼並不替模型權重授權。Qwen2.5-3B base、merged 模型與
> LoRA adapter 均受 [Qwen Research License](LICENSES/QWEN-RESEARCH-LICENSE.txt)約束,
> 僅供非商業研究與評估;GSM8K 題目則依 OpenAI MIT License 散布。詳見
> [第三方聲明](THIRD_PARTY_NOTICES.md)。

> **English TL;DR** — GRPO/RLVR fine-tuning of Qwen2.5-3B on GSM8K using only
> programmatically verifiable rewards. On the same 200 test problems, strict accuracy improved
> from **70.5% to 79.0%** (paired exact McNemar `p=0.0046`) and strict format adherence from
> **19.5% to 90.0%**. Flexible accuracy improved by 3.5 points but was not significant
> (`p=0.2478`); all per-example outputs and paired analyses are included.

## 結果一覽

同一批 GSM8K test 前 200 題、greedy decoding 的逐題配對結果：

| 指標 | Base | GRPO | Δ | paired evidence |
|---|---:|---:|---:|---:|
| Strict accuracy（`<answer>` 內最後一個數字） | 70.5% | **79.0%** | +8.5% | exact McNemar p=0.0046 |
| Flexible accuracy（全文最後一個數字） | 76.0% | 79.5% | +3.5% | p=0.2478，未達顯著 |
| Strict format | 19.5% | **90.0%** | +70.5% | p≈5.9×10⁻³⁹ |
| 平均輸出 tokens | 283 | **261** | −22 | paired 95% CI [−32.4, −10.8] |

完整數字、25 個由錯轉對／8 個由對轉錯的配對關係與固定案例，見
[paired analysis](results/paired_analysis.md)。這裡刻意分開 strict 與 flexible
口徑：前者的改善顯著，後者目前沒有足夠證據宣稱確定提升。

## 為什麼是 RLVR

2026 年 RL 訓練 LLM 的主流敘事已經從「訓 reward model 再做 RLHF」轉向
**RLVR(Reinforcement Learning with Verifiable Rewards)**:在數學、程式這類
答案可程式驗證的領域,獎勵直接由規則判分 ——

- **降低 reward-model gaming**:答案由確定性規則判分,不用討好另一個神經網路;
- **便宜**:省掉收集偏好資料與訓練 reward model 的整條管線;
- **GRPO 再省一層**:同一題抽 8 個回答、組內比較算相對優勢(advantage),
  連 PPO 的 value model 也不用。

規則式 verifier 仍可能有可鑽漏洞，因此本專案另外保留逐題輸出並檢查格式、答案抽取與
長度分布；較準確的說法是「在目前的規則與抽樣結果中未觀察到明顯 reward hacking」，
而不是宣稱 RLVR 天生不可能被 hack。

本專案的獎勵組(定義在 [rewards.py](rewards.py),有完整 [pytest](tests/)):

| 獎勵函數 | 條件 | 分數 |
|---|---|---|
| `correctness_reward` | `<answer>` 內數字 == 標準答案 | **2.0** |
| `strict_format_reward` | 完整 `<reasoning>…</reasoning><answer>…</answer>` 結構 | 0.5 |
| `soft_format_reward` | 兩組 tag 依序出現(部分符合) | 0.5 |
| `number_only_reward` | `<answer>` 區塊是純數字 | 0.5 |

## 訓練結果:reward 爬升確實,但「長度隨訓練成長」沒有出現

reward 曲線很乾淨:從 ~1.4 一路爬到 200 步左右穩定在 3.1~3.3(滿分 3.5),之後
800 步都維持在這個高原,沒有崩潰；逐題輸出與長度分布中也未觀察到明顯的
reward hacking 模式。

| reward 曲線(1000 步) | completion 長度曲線(1000 步) |
|---|---|
| ![reward curve](results/figs/reward_curve.png) | ![completion length curve](results/figs/completion_length_curve.png) |

但 **completion 長度並沒有隨訓練淨成長**:開頭幾步因為模型還不熟悉
`<reasoning>/<answer>` 格式而暴衝到 400+ token,前 100 步內就收斂到 220~300 token
的區間,之後一路到第 1000 步都在這個範圍內震盪,沒有向上的趨勢。

這點特別驗證過,不是隨口說說:先訓 500 步觀察到這個現象後,**從同一個 checkpoint
續訓到 1000 步**,結果幾乎完全重現(strict format 遵循率兩次都是 90.0%,長度分布
也幾乎一致)—— 降低了「500 步還看不到」的疑慮,但不外推到更長訓練或其他設定。
比較合理的解釋是:本專案的獎勵函數
從未直接獎勵「長度」本身,只獎勵答對與格式對;GSM8K 對 Qwen2.5-3B-Instruct 這個
規模的模型來說,也還沒難到需要更長的推理鏈才能算對。

不過長度的分配方式其實**很聰明**:把 200 題測試依題目字數切五等分,trained 模型
在**每個難度區間都比 base 模型短 15~30 token**,但同時**難題本身仍分配到更多
token**(以 base 模型答錯的題目當難度 proxy,trained 模型在這些難題上平均多寫
約 60 token)。也就是說,模型學到的不是「一律講更長」,而是**難題多想、易題少想**
的效率提升 —— 這其實比單純的長度暴力成長更貼近「有效推理」的本意。

## 評測(GSM8K test 前 200 題,greedy)

完整對照表:[results/eval_report.md](results/eval_report.md)(訓練後由
[eval/run_eval.py](eval/run_eval.py) 產生;base 與訓練後模型的數字都是真實跑出來的)。
逐題配對檢定由 [eval/analyze_paired.py](eval/analyze_paired.py) 對已提交的兩份 JSONL
重算，不需重新執行模型：

```bash
python eval/analyze_paired.py
```

訓練**只用 train split(7,473 題)**;notebook 只呼叫 `split="train"`,test split
僅由獨立的評測程式載入。已提交評測使用 test 前 200 題,逐題資料來源、MIT notice、
固定 revision、SHA-256 與可重現性限制見 [results provenance](results/README.md)。

## 如何執行

### 0. 本機(免 GPU):驗證獎勵函數

```bash
pip install pytest
python -m pytest tests/ -v
python eval/verify_results.py     # 雜湊、schema、配對與 metrics 一致性
python eval/analyze_paired.py     # 不跑模型,重建配對統計
```

### 1. Colab 訓練

1. 把 [train_grpo_colab.ipynb](train_grpo_colab.ipynb) 上傳 Colab,
   Runtime → Change runtime type → **L4 GPU**。
2. 左側 🔑 Secrets 加 `HF_TOKEN`(Hugging Face **write** token),
   並開啟此 notebook 的存取權(⚠️ 背景執行時無法回應授權彈窗,務必先掛好)。
3. **SMOKE_TEST 跑通**:保持 `SMOKE_TEST = True` → Run all(約 15–20 分鐘),
   確認安裝、模型載入、Drive checkpoint、samples/metrics 記錄、畫圖全鏈路無誤。
4. **正式訓練(背景執行)**:改 `SMOKE_TEST = False` → Run all → 直接關閉分頁。
   Colab Pro+ 會在背景繼續跑(500 步約 4–7 小時);結束時會先檢查既有 HF repo,
   再建立兩個 **release PR candidate**。candidate revision 通過 artifact gate 後自動
   `runtime.unassign()` 釋放機器;不會自動 merge 或直寫 default branch。
5. **斷線續跑**:若背景 session 被提早收走,重新連 L4 → 設 `RESUME = True` → Run all,
   會從 Drive 最新有效 checkpoint(每 100 步存一份)接著訓練。
6. **延長訓練**:想在既有 checkpoint 上訓更多步(例如觀察長度是否會在更後期成長):
   把 `MAX_STEPS` 調大(如 500→1000)、`RESUME = True`,其餘不變,一樣 Run all。
   注意 cosine LR 排程會依這次的 `MAX_STEPS` 重新計算,resume 那一步 LR 會有一次性
   跳動,是正常現象。本專案實際做過這個實驗:1000 步的結果與 500 步幾乎一致
   (見上一節),證實了長度不成長不是訓練不夠久。

> 📉 **前 ~100 步 reward ≈ 0 是正常現象**(Unsloth 官方文件:等 150–300 步才開始爬),
> 不要提早砍掉健康的 run。

OOM 時的調參階梯(依序嘗試):`GPU_MEMORY_UTILIZATION` 0.85→0.7 →
`NUM_GENERATIONS` 8→6 → `MAX_COMPLETION_LENGTH` 768→512。

### 2. 訓練後評測

```bash
# Colab 或本機 GPU(如 4090)皆可;約 20–40 分鐘
python eval/run_eval.py --trained-model steven0226/qwen2.5-3b-grpo-gsm8k
# 也可以直接評 Drive 上還沒 merge 的 LoRA checkpoint:
python eval/run_eval.py --models trained --adapter /path/to/checkpoint-1000
```

產出 `results/eval_report.md` 與逐題生成記錄,commit 回本 repo 即完成。
預設命令固定 GSM8K、base model 與已發布 trained weights 的 revision;`do_sample=False`
關閉抽樣隨機性,但不同 CUDA、PyTorch、Transformers 或 tokenizer 環境仍不保證 bitwise
相同輸出。原始 2026-07 評測未完整記錄套件版本,因此本 repo 對既有證據宣稱的是
**可稽核與可重算統計**,不是跨環境逐 byte 重生成保證。

## 選配:A100 + 7B 旗艦版

L4 + 3B 是成本甜蜜點;想上 7B 只要改 notebook 的 PARAMS cell:

| 參數 | 3B(L4) | 7B(A100 40GB) |
|---|---|---|
| `MODEL_NAME` | Qwen/Qwen2.5-3B-Instruct | `Qwen/Qwen2.5-7B-Instruct` |
| `LORA_R` | 32 | 64(官方建議區間上緣) |
| `MAX_COMPLETION_LENGTH` | 768 | 1024(A100 放得下,推理空間更大) |
| `LOAD_IN_4BIT` | True | True;VRAM 有餘裕可改 False(16bit LoRA,品質略升) |
| `MAX_STEPS` | 500 | 500–1000(7B 學得動更多步) |
| `GPU_MEMORY_UTILIZATION` | 0.85 | 0.85 |

粗估:7B QLoRA + vLLM rollout 在 A100 40GB 上綽綽有餘(Unsloth 的經驗法則:
16GB 就能跑到 ~14B 的 GRPO QLoRA);500 步約 5–8 小時,曲線通常比 3B 更陡。

## 專案結構

```
rewards.py               # SYSTEM_PROMPT + 抽取 helpers + 4 個獎勵函數(唯一事實來源)
tests/                   # 獎勵函數、paired analysis、release 與 provenance 測試
train_grpo_colab.ipynb   # Colab 訓練 notebook(SMOKE_TEST / RESUME / HF PR gate / 自動釋放)
eval/run_eval.py         # base vs trained 對照評測(Colab / 本機皆可)
eval/analyze_paired.py   # 不重跑模型，對逐題結果做 exact paired analysis
eval/verify_results.py   # 離線驗證 committed evidence 的雜湊、schema 與 metrics
hf_release.py            # HF card 授權 metadata 與 merged/LoRA 檔案面 gate
results/                 # 曲線圖、provenance、paired 統計、逐題生成記錄
docs/huggingface/        # 唯讀 artifact audit 與待審的 HF 遠端修復方案
LICENSES/                # GSM8K MIT、Unsloth LGPL、Qwen Research License
```

## License 與第三方內容

- 原創程式、文件、測試與 assets: [Apache-2.0](LICENSE)。
- `rewards.py` 與 `train_grpo_colab.ipynb`:修改自 UnslothAI GRPO notebook,
  依 [LGPL-3.0](LICENSES/UNSLOTH-NOTEBOOKS-LGPL-3.0.txt)散布。
- `results/eval_generations_*.jsonl` 內的 GSM8K 題目:Copyright (c) 2021 OpenAI,
  [MIT License](LICENSES/GSM8K-MIT.txt);引用 Cobbe et al. (2021),
  *Training Verifiers to Solve Math Word Problems*, arXiv:2110.14168。
- Hugging Face 的 base/merged/LoRA 模型 artifact:
  [Qwen Research License](LICENSES/QWEN-RESEARCH-LICENSE.txt),非 Apache-2.0。

完整適用範圍、修改聲明與 redistribution notice 見
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
