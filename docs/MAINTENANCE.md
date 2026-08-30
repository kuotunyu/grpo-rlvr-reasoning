# 維護與發布防呆指南

這是本 repo 唯一的操作入口。若不確定下一步，先停止操作，把想做的變更和目前畫面交給 Codex；不需要自行猜 Git、GitHub 或 Hugging Face 指令。

## 1. 預設做法

- 描述想修改的內容、成功條件，以及是否涉及 GitHub release 或 HF 模型。
- 讓 Codex 建立 branch、執行測試、開 PR 並核對遠端狀態。
- 不要 force-push、不要重寫公開歷史、不要刪除 main。
- 不要移動或重建既有 release tag；已發布版本有問題時，建立新版本。
- 不要直接寫入、刪除或重寫 HF default branch。

## 2. 一般 GitHub 修改

必要流程只有：

1. 從最新 main 建立新 branch。
2. 修改並執行本機測試。
3. push branch 並建立 PR。
4. 等待 pytest (3.10)、pytest (3.11)、pytest (3.12) 全綠。
5. 解決所有 review 對話後再 merge。

不需要找其他人批准；CI 全綠且對話已解決即可自行 merge。不要繞過失敗的檢查，也不要直接 push 到 main。

## 3. 發布 GitHub 版本

發布前執行：

~~~bash
python -m pytest -q
python eval/verify_results.py
python release_audit.py
~~~

接著讓變更經 PR 合併，確認 main 的 CI 全綠，再建立新的版本號與 release notes。既有 tag 永遠保持指向原 commit；修正內容使用下一個版本號。

## 4. 修改 Hugging Face

HF 變更只走 candidate PR：

1. 建立 candidate revision，不直接寫 default branch。
2. 稽核 candidate 的檔案種類、授權文字、大小與 SHA-256。
3. 提交 HF PR 並等待人工核准。
4. merge 後執行 python release_audit.py。

不要直接寫入、刪除或重寫 HF default branch。不要把 GitHub 的 Apache-2.0 誤當成模型權重授權。

## 5. 檢查失敗時

- 停止 merge，不要 bypass。
- 保留完整錯誤輸出、失敗 run URL 和 commit SHA。
- 把證據交給 Codex 診斷。
- 修正必須透過同一個 PR 或新的修復 PR，再讓全部檢查重跑。

## 6. 復原方式

公開歷史只用新的 revert PR 復原。不要 force-push，也不要刪除或重建 release tag。若 HF 發布有問題，先停止下載宣傳與後續 merge，再以新的 candidate PR 修正；不要重寫遠端歷史。

## 哪些事情不必做

- 一般文件或程式修改不需要碰 HF。
- 沒有新模型 artifact 時，不需要改 remote artifact audit。
- 沒有新的使用者可見版本時，不需要建立 release。
- 既有 2026-07 評測不需要為每次文件更新重新跑 GPU。
