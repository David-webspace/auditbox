# 開發

## 不用 Docker 執行

需要 Python 3.12＋[uv](https://docs.astral.sh/uv/) 與 Node.js＋pnpm。

```bash
cd web && pnpm install && pnpm build && cd ..
uv run auditbox serve demo          # 或 ./start-local.sh demo
```

其他指令：

```bash
uv run auditbox run demo --pic Amber   # 不開介面，直接處理某位承辦的全部檔案
uv run auditbox lint demo              # 檢查寄信對照表
```

## 專案結構

```
src/auditbox/      後端（擷取、稽核、驗收單、路由、信件、API）
web/               前端（Next.js 16，靜態輸出到 web/out）
demo/              展示工作區（由 mockgen 產生）
tools/mockgen/     產生虛構的 PDF、主檔、SAP 匯出與標準答案
eval/              標準答案與評測結果
tests/             pytest
docker/、Dockerfile、compose.yaml、start.*   部署
```

## 測試

```bash
uv run pytest -q
```

測試不呼叫 LLM：用已存的擷取結果重播整條流程，涵蓋稽核規則、路由、信件、驗收單、歸檔、重複請款、重試、並行請求與 API。

## 重新產生展示資料

```bash
uv run python -m tools.mockgen
```

會覆寫 `demo/` 與 `eval/ground_truth/`；亂數種子固定，結果可重現。

## 前端

```bash
cd web
pnpm dev        # 開發（API 需另外啟動 uv run auditbox serve demo）
pnpm build      # 輸出到 web/out，由 FastAPI 提供
```
