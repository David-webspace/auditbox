"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type HealthCheck, type InboxItem, type JobState } from "@/lib/api";
import StatusBadge, { OUTCOME_LABEL } from "./StatusBadge";

const FOLDERS = [
  ["inbox", "01 待處理"],
  ["forms", "02 驗收單"],
  ["done", "03 已處理"],
  ["manual", "04 人工處理"],
] as const;

export default function RunPanel() {
  const [pics, setPics] = useState<string[]>([]);
  const [pic, setPic] = useState("");
  const [llm, setLlm] = useState("");
  const [llmReady, setLlmReady] = useState(true);
  const [workspace, setWorkspace] = useState<{ path: string; canOpen: boolean } | null>(null);
  const [items, setItems] = useState<InboxItem[]>([]);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [job, setJob] = useState<JobState | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const [health, setHealth] = useState<HealthCheck[] | null>(null);
  const [error, setError] = useState("");
  const cursor = useRef(0);
  const logBox = useRef<HTMLPreElement>(null);

  const loadInbox = useCallback(async (p: string) => {
    if (!p) return;
    try {
      const list = await api.inbox(p);
      setItems(list);
      setChecked(new Set(list.filter((i) => !i.problem).map((i) => i.base)));
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    Promise.all([api.meta(), api.job(0)])
      .then(([m, j]) => {
        setPics(m.pics);
        setLlm(m.llm);
        setLlmReady(m.llm_ready);
        setWorkspace({ path: m.workspace, canOpen: m.can_open });
        const first = j.running && j.pic ? j.pic : m.pics[0];
        if (j.running) {
          setJob(j);
          setLog(j.log);
          cursor.current = j.next;
        }
        setPic(first);
        loadInbox(first);
      })
      .catch((e) => setError(`後端連不上：${e.message}`));
    api.health().then(setHealth).catch(() => setHealth([]));
  }, [loadInbox]);

  function choosePic(p: string) {
    setPic(p);
    loadInbox(p);
  }

  const running = !!job?.running;
  useEffect(() => {
    if (!running) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const j = await api.job(cursor.current);
        if (!alive) return;
        cursor.current = j.next;
        setJob(j);
        if (j.log.length) setLog((l) => [...l, ...j.log]);
        if (!j.running) {
          loadInbox(j.pic ?? pic);
          return;
        }
      } catch {
        // 伺服器忙或暫時斷線，下一輪再試
      }
      if (alive) timer = setTimeout(poll, 1000);
    };
    timer = setTimeout(poll, 1000);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [running, pic, loadInbox]);

  useEffect(() => {
    logBox.current?.scrollTo({ top: logBox.current.scrollHeight });
  }, [log]);

  async function start() {
    setError("");
    const bases = items.filter((i) => checked.has(i.base)).map((i) => i.base);
    try {
      await api.startJob(pic, bases);
      cursor.current = 0;
      setLog([]);
      setJob({ running: true, pic, items: bases.map((b) => ({ base: b, status: "等待中", case_id: null, outcome: null })), log: [], next: 0 });
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const toggle = (base: string) =>
    setChecked((s) => {
      const n = new Set(s);
      if (n.has(base)) n.delete(base);
      else n.add(base);
      return n;
    });

  const jobItem = (base: string) => job?.items.find((i) => i.base === base);
  const failed = health?.filter((h) => !h.ok) ?? [];
  const finished = job?.items.filter((i) => i.case_id) ?? [];

  return (
    <div className="space-y-4">
      <section className="rounded-lg bg-white p-4 shadow-sm ring-1 ring-slate-200">
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm font-medium">
            承辦
            <select
              value={pic}
              disabled={running}
              onChange={(e) => choosePic(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-1.5"
            >
              {pics.map((p) => (
                <option key={p}>{p}</option>
              ))}
            </select>
          </label>
          <button onClick={() => loadInbox(pic)} disabled={running} className="btn">
            重新整理
          </button>
          <p className="min-w-0 flex-1 basis-full text-sm text-slate-500 md:basis-0">
            勾選檔案後按「開始」。系統會讀取 PDF、稽核、填驗收單、產生信件草稿並歸檔；失敗會重試，仍失敗移到 04 人工處理，不會卡住整批。
          </p>
        </div>
        {!llmReady && (
          <p className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-800">
            還沒設定 Claude API key，無法開始處理。
            <Link href="/settings/" className="ml-1 font-semibold underline">前往模型設定</Link>
          </p>
        )}
        {health && (
          <div className={`mt-3 rounded-md px-3 py-2 text-sm ${failed.length ? "bg-amber-50 text-amber-900" : "bg-emerald-50 text-emerald-900"}`}>
            {failed.length ? (
              <>
                環境檢查有 {failed.length} 項需要注意：{failed.map((f) => f.name).join("、")}
                <Link href="/check/" className="underline">查看</Link>
              </>
            ) : (
              <>環境檢查通過　模型：{llm}</>
            )}
          </div>
        )}
        {error && <p className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>}
      </section>

      <section className="overflow-hidden rounded-lg bg-white shadow-sm ring-1 ring-slate-200">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="bg-slate-50 text-left text-slate-600">
              <tr>
                <th className="w-10 px-3 py-2" />
                <th className="px-3 py-2">案件（廠商＋模具）</th>
                <th className="px-3 py-2">頁數</th>
                <th className="px-3 py-2">更新時間</th>
                <th className="px-3 py-2">狀態</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-3 py-8 text-center text-slate-400">
                    {pic ? `01_待處理/${pic} 沒有檔案` : "讀取中…"}
                  </td>
                </tr>
              )}
              {items.map((i) => {
                const ji = jobItem(i.base);
                return (
                  <tr key={i.base} className={i.problem ? "bg-red-50/50" : ""}>
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        aria-label={`選取 ${i.base}`}
                        disabled={!!i.problem || running}
                        checked={checked.has(i.base)}
                        onChange={() => toggle(i.base)}
                        className="size-4 accent-navy"
                      />
                    </td>
                    <td className="min-w-0 px-3 py-2">
                      <div className="font-medium">{i.base}</div>
                      <div className="truncate text-xs text-slate-500">
                        {[i.invoice, i.attachment].filter(Boolean).join("　")}
                      </div>
                    </td>
                    <td className="px-3 py-2 tabular-nums">{i.pages}</td>
                    <td className="px-3 py-2 tabular-nums text-slate-600">{i.modified}</td>
                    <td className="px-3 py-2">
                      {i.problem ? (
                        <span className="text-xs text-red-700">{i.problem}</span>
                      ) : (
                        <StatusBadge status={ji?.status ?? "待處理"} />
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="flex flex-wrap gap-2 border-t border-slate-100 p-3">
          <button className="btn" disabled={running} onClick={() => setChecked(new Set(items.filter((i) => !i.problem).map((i) => i.base)))}>
            全選
          </button>
          <button className="btn" disabled={running} onClick={() => setChecked(new Set())}>
            全不選
          </button>
          <button
            className="rounded-md bg-navy px-5 py-1.5 text-sm font-semibold text-white hover:bg-navy-dark disabled:opacity-40"
            disabled={running || checked.size === 0}
            onClick={start}
          >
            ▶ 開始處理勾選的 {checked.size} 份
          </button>
          <button
            className="btn"
            disabled={!running}
            onClick={() => api.skipJob().then(() => setLog((l) => [...l, "  …略過中，等目前這次讀取完成（約 10–20 秒）"]))}
          >
            略過這份
          </button>
          <button
            className="btn"
            disabled={!running}
            onClick={() => api.stopJob().then(() => setLog((l) => [...l, "  …停止中，等目前這次讀取完成，剩下的檔案不會處理"]))}
          >
            停止
          </button>
        </div>
      </section>

      {finished.length > 0 && (
        <section className="rounded-lg bg-white p-4 shadow-sm ring-1 ring-slate-200">
          <h2 className="mb-2 text-sm font-semibold text-slate-700">本批結果</h2>
          <ul className="flex flex-wrap gap-2">
            {finished.map((i) => (
              <li key={i.base}>
                <Link
                  href={`/case/?id=${encodeURIComponent(i.case_id!)}`}
                  className="flex items-center gap-2 rounded-md px-3 py-1.5 text-sm ring-1 ring-slate-200 hover:bg-slate-50"
                >
                  {i.base}
                  <StatusBadge status={OUTCOME_LABEL[i.outcome!] ?? i.outcome!} />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="rounded-lg bg-white shadow-sm ring-1 ring-slate-200">
        <pre
          ref={logBox}
          className="h-64 overflow-auto whitespace-pre-wrap break-words p-3 font-mono text-xs leading-relaxed text-slate-700"
        >
          {log.length ? log.join("\n") : "處理紀錄會顯示在這裡。"}
        </pre>
        {workspace?.canOpen === false ? (
          <p className="break-all border-t border-slate-100 p-3 text-sm text-slate-600">
            處理結果在電腦上的這個資料夾：<code className="rounded bg-slate-100 px-1.5 py-0.5">{workspace.path}</code>
          </p>
        ) : (
          <div className="flex flex-wrap gap-2 border-t border-slate-100 p-3">
            {FOLDERS.map(([key, label]) => (
              <button key={key} className="btn" onClick={() => api.open(key)}>
                開啟 {label}
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
