"use client";

import { useEffect, useState } from "react";
import { api, type LLMSettings } from "@/lib/api";

export default function LLMSettingsPanel() {
  const [cur, setCur] = useState<LLMSettings | null>(null);
  const [provider, setProvider] = useState<"claude" | "ollama">("claude");
  const [model, setModel] = useState("");
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    api
      .llm()
      .then((s) => {
        setCur(s);
        setProvider(s.provider);
        setModel(s.model);
      })
      .catch((e) => setMsg({ ok: false, text: e.message }));
  }, []);

  async function save(body: { provider: string; model?: string; api_key?: string | null }, done: string) {
    setBusy(true);
    setMsg(null);
    try {
      const s = await api.saveLlm(body);
      setCur(s);
      setKey("");
      setMsg({ ok: true, text: done });
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    } finally {
      setBusy(false);
    }
  }

  if (!cur) return <p className="text-sm text-slate-400">{msg?.text ?? "讀取中…"}</p>;

  return (
    <div className="max-w-2xl space-y-4">
      <section className="rounded-lg bg-white p-4 shadow-sm ring-1 ring-slate-200">
        <h2 className="mb-1 font-semibold">讀取 PDF 用的 AI 模型</h2>
        <p className="mb-4 text-sm text-slate-500">
          AI 只負責從 PDF 抄出欄位；能不能送簽由系統規則判斷。設定只存在這台電腦，不會同步到共用資料夾。
        </p>

        <fieldset className="space-y-2">
          <label className="flex items-start gap-2 text-sm">
            <input type="radio" name="provider" checked={provider === "claude"} onChange={() => setProvider("claude")} className="mt-1" />
            <span>
              <b>Claude API</b>（使用你們訂閱的 API key）
              <span className="block text-slate-500">PDF 內容會送到 Anthropic API 處理。</span>
            </span>
          </label>
          <label className="flex items-start gap-2 text-sm">
            <input type="radio" name="provider" checked={provider === "ollama"} onChange={() => setProvider("ollama")} className="mt-1" />
            <span className="min-w-0 break-words">
              <b>本機 Ollama</b>（{cur.ollama.model}，資料不出電腦）
              <span className="block text-slate-500">需要自行安裝 Ollama：{cur.ollama.base_url}</span>
            </span>
          </label>
        </fieldset>

        {provider === "claude" && (
          <div className="mt-4 space-y-3 border-t border-slate-100 pt-4">
            <label className="block text-sm font-medium">
              模型
              <select value={model} onChange={(e) => setModel(e.target.value)} className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-1.5 font-normal">
                {Object.entries(cur.models).map(([id, label]) => (
                  <option key={id} value={id}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm font-medium">
              API key
              <input
                type="password"
                autoComplete="off"
                value={key}
                onChange={(e) => setKey(e.target.value)}
                placeholder={cur.key_hint ? `已設定 ${cur.key_hint}，留空表示不變更` : "sk-ant-…"}
                className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-1.5 font-mono font-normal"
              />
            </label>
            {cur.key_source === "環境變數" && (
              <p className="text-xs text-slate-500">目前使用環境變數 ANTHROPIC_API_KEY；在這裡輸入會優先使用。</p>
            )}
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button
            disabled={busy}
            onClick={() =>
              save({ provider, model, ...(key ? { api_key: key } : {}) }, provider === "claude" ? "已儲存，API key 驗證通過" : "已改用本機 Ollama")
            }
            className="rounded-md bg-navy px-4 py-1.5 text-sm font-semibold text-white disabled:opacity-40"
          >
            {busy ? "驗證中…" : provider === "claude" ? "驗證並儲存" : "儲存"}
          </button>
          {cur.key_source === "畫面設定" && (
            <button disabled={busy} className="btn" onClick={() => save({ provider: "ollama", api_key: "" }, "已清除 API key，改用本機 Ollama")}>
              清除 API key
            </button>
          )}
        </div>
        {msg && <p className={`mt-3 rounded-md px-3 py-2 text-sm ${msg.ok ? "bg-emerald-50 text-emerald-900" : "bg-red-50 text-red-800"}`}>{msg.text}</p>}
      </section>

      <p className="text-sm text-slate-500">
        目前使用：{cur.provider === "claude" ? cur.models[cur.model] ?? cur.model : `Ollama ${cur.ollama.model}`}
      </p>
    </div>
  );
}
