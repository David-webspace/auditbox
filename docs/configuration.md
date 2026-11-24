# 設定與工作區

## 工作區資料夾

工作區通常是部門共用、透過 OneDrive 同步到每台電腦的 SharePoint 資料夾。

```
工作區/
├── 00_設定/            設定.yaml、稽核規則.yaml、驗收單欄位對照.yaml、廠商主檔、寄信對照表、驗收單範本
├── 01_待處理/<承辦>/   廠商寄來的「XXX IV.pdf」（發票）＋「XXX.pdf」（附件）
├── 02_驗收單/<承辦>/   自動填好的資產驗收單 xlsx
├── 03_已處理/<承辦>/   可送簽的案件：合併 PDF、草稿、稽核結果、原始檔
├── 04_人工處理/<承辦>/ 需補件或內部處理的案件，以及系統失敗的案件
├── 05_系統匯出/        SAP PO（ME2N）、SAP GR（MB51）、應付帳款已付清單、HR 員工名單（檔名可帶日期，取最新）
└── Logs/
```

## 設定.yaml 重點

| 區塊 | 說明 |
|---|---|
| `company` | 公司中文名、英文名（英文信使用） |
| `pics` | `01_待處理` 底下的資料夾名稱對應承辦工號 |
| `files` | 各設定檔與系統匯出的檔名（可用萬用字元） |
| `patterns` | PO 號、模具編號、工號的格式（正規表示式） |
| `retry` | 擷取失敗的重試次數 |
| `llm` | 預設的 LLM 與 Ollama 位址、Claude 模型與 effort |
| `mail` | `mode`（`eml` 只存草稿、`mailpit` 同時送模擬信箱）、`llm_intro`、寄件人 |

`驗收單欄位對照.yaml` 定義驗收單每個欄位填在哪個儲存格、資料從哪裡來（承辦、廠商主檔、SAP、PDF 擷取、固定值、今天日期）。

## 模型設定

在介面的「模型設定」頁選擇：

- **Claude API**：輸入 API key 後按「驗證並儲存」，系統會先向 Anthropic 確認 key 可用（不產生費用）。可選 Opus、Sonnet、Haiku 5.5。PDF 內容會送到 Anthropic API。
- **本機 Ollama**：資料不出電腦，需自行安裝 Ollama 並下載模型。

設定與 API key 存在本機的 `~/.auditbox/llm.json`（Docker 則在 volume `/data`），檔案權限 600，不會寫進共用工作區。
優先順序：畫面設定 > 環境變數 > `設定.yaml`。

## 環境變數（Docker）

| 變數 | 用途 |
|---|---|
| `AUDITBOX_WORKSPACE` | 主機上的工作區路徑，預設 `./workspace` |
| `AUDITBOX_LLM_PROVIDER` | 預設 provider（`claude`／`ollama`） |
| `OLLAMA_BASE_URL` | Ollama 位址，Docker 預設連主機的 `host.docker.internal:11434` |
| `AUDITBOX_MAIL_MODE`、`MAILPIT_HOST`、`MAILPIT_PORT` | 信件輸出方式與模擬信箱位址 |
| `AUDITBOX_DATA` | 本機資料庫與 LLM 設定的位置 |

把工作區指向共用資料夾：

```bash
AUDITBOX_WORKSPACE="/path/to/共用資料夾" ./start.sh
```

```bat
set AUDITBOX_WORKSPACE=C:\Users\me\OneDrive - 公司\模具請款
start.bat
```

停止服務用 `docker compose down`；連同本機資料庫與 API key 一起刪除用 `docker compose down -v`。
