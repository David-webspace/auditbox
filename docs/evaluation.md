# 評測

## 測試資料

`tools/mockgen` 產生虛構公司「隼光科技」的 12 件模具請款案（160 頁、416 個欄位），每件都有標準答案（`eval/ground_truth/`）。

| 案例 | 情境 | 預期結果 |
|---|---|---|
| C01、C02 | 正常 | 可送簽 |
| C03 | 缺保管單 | 待廠商補件 |
| C04 | 發票金額與 PO 不符 | 待廠商補件 |
| C05 | 承諾書 PO 號打錯 | 待廠商補件 |
| C06 | 承認書未簽品保 | 待廠商補件 |
| C07 | 發票幣別與 PO 不符 | 待廠商補件 |
| C08 | SAP 查無 GR | 內部處理 |
| C09 | 重複請款 | 內部處理 |
| C10 | 掃描檔歪斜＋廠商用別名 | 可送簽 |
| C11 | 廠商不在主檔 | 主檔維護 |
| C12 | 保管人已離職 | 內部處理 |

文件涵蓋簡體、繁體、英文廠商，以及掃描影像、千分位寫法不同、廠商名稱別名等干擾。

## 結果

| 模型 | 分頁 | 欄位 | 每件時間 | 12 件費用 |
|---|---|---|---|---|
| Claude Opus 5.5 | 160/160 | 416/416 | 約 27 秒 | USD 1.29 |
| Claude Haiku 5.5 | 160/160 | 416/416（原始 413/416） | 約 20 秒 | USD 0.037 |
| qwen3.5:9b（本機） | 160/160 | 416/416 | 約 130 秒 | 0 |

- Haiku 把掃描檔上的「46,200.00」讀成「46.200.00」。改進金額解析後（依分隔符號位置判斷小數點）三者皆全對。
- 信件開頭段落三者事實皆正確；Opus 語氣最自然，qwen 偏生硬。
- 完整比較與逐件數據：[`eval/runs/comparison.md`](../eval/runs/comparison.md)。

模擬文件版面乾淨，真實廠商文件（手寫、印章壓字、表格跨頁）可能拉開差距，正式導入前應以真實樣本再測。

## 執行評測

```bash
# 本機 Ollama
uv run python -m auditbox.evaluate demo --out eval/runs/qwen3.5-9b --provider ollama

# Claude（API key 用環境變數 ANTHROPIC_API_KEY，或先在本機版介面的「模型設定」存好）
uv run python -m auditbox.evaluate demo --out eval/runs/claude-opus-5-5 --provider claude
uv run python -m auditbox.evaluate demo --out eval/runs/claude-haiku-5-5 --provider claude --model claude-haiku-5-5

# 只重新計分、不呼叫 LLM
uv run python -m auditbox.evaluate demo --out eval/runs/<name> --score-only

# 比較信件開頭段落
uv run python -m auditbox.evaluate demo --out eval/runs/<name> --provider claude --intros
```

輸出 `report.md`（逐件分數、時間、tokens、費用、錯誤明細）、`intros.md` 與各案 JSON。
