"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, fileUrl, pageUrl, type CaseDetail as Detail } from "@/lib/api";
import { FieldsView, FindingsView, type Target } from "./EvidenceViews";
import StatusBadge from "./StatusBadge";

const TABS = ["稽核結果", "擷取欄位", "信件草稿", "檔案", "歷程"] as const;
type Tab = (typeof TABS)[number];

export default function CaseDetail() {
  const id = useSearchParams().get("id") ?? "";
  const [c, setC] = useState<Detail | null>(null);
  const [files, setFiles] = useState<string[]>([]);
  const [statuses, setStatuses] = useState<string[]>([]);
  const [canOpen, setCanOpen] = useState(false);
  const [tab, setTab] = useState<Tab>("稽核結果");
  const [target, setTarget] = useState<Target | null>(null);
  const [next, setNext] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    Promise.all([api.case(id), api.listing(id), api.meta()])
      .then(([cd, fl, m]) => {
        setC(cd);
        setFiles(fl);
        setStatuses(m.statuses);
        setCanOpen(m.can_open);
        setNext(cd.status);
        const ev = cd.detail?.findings.find((f) => f.status === "fail")?.evidence.find((e) => e.page && e.file);
        const po = cd.detail?.extraction.documents.po;
        if (ev) setTarget({ file: ev.file!, page: ev.page!, q: ev.raw, label: `${ev.doc} 第 ${ev.page} 頁` });
        else if (po) setTarget({ file: po.file, page: po.pages[0], q: null, label: `採購單 PO 第 ${po.pages[0]} 頁` });
      })
      .catch((e) => setError(e.message));
  }, [id]);

  async function save() {
    try {
      const updated = await api.setStatus(id, next, note);
      setC(updated);
      setNote("");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  if (!id) return <p className="text-slate-500">缺少案件編號。</p>;
  if (error) return <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>;
  if (!c) return <p className="text-slate-400">讀取中…</p>;
  const d = c.detail;

  return (
    <div className="space-y-4">
      <Link href="/cases/" className="text-sm text-navy hover:underline">← 案件追蹤</Link>
      <section className="flex flex-wrap items-start gap-4 rounded-lg bg-white p-4 shadow-sm ring-1 ring-slate-200">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-bold">{c.vendor || c.base}　PO {c.po_no ?? "—"}</h1>
            <StatusBadge status={c.status} />
          </div>
          <p className="mt-1 break-words text-sm text-slate-500">
            {c.base}・承辦 {c.pic}・{c.created.replace("T", " ").slice(0, 16)}
            {d && `・${d.extraction.llm}，${d.extraction.seconds} 秒`}
          </p>
          {c.note && <p className="mt-1 text-sm text-slate-700">備註：{c.note}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select aria-label="狀態" value={next} onChange={(e) => setNext(e.target.value)} className="rounded-md border border-slate-300 px-2 py-1.5 text-sm">
            {statuses.map((s) => <option key={s}>{s}</option>)}
          </select>
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="備註（選填）"
            className="w-44 rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          />
          <button onClick={save} disabled={next === c.status && !note} className="rounded-md bg-navy px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-40">
            更新狀態
          </button>
          {canOpen && <button className="btn" onClick={() => api.open(`case:${c.id}`)}>開啟資料夾</button>}
        </div>
      </section>

      {!d ? (
        <section className="rounded-lg bg-white p-4 text-sm shadow-sm ring-1 ring-slate-200">
          系統處理失敗，詳見資料夾內的「失敗原因.md」。
        </section>
      ) : (
        <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
          <section className="min-w-0 rounded-lg bg-white shadow-sm ring-1 ring-slate-200">
            <div className="flex overflow-x-auto border-b border-slate-200" role="tablist">
              {TABS.map((t) => (
                <button
                  key={t}
                  role="tab"
                  aria-selected={tab === t}
                  onClick={() => setTab(t)}
                  className={`shrink-0 px-4 py-2.5 text-sm ${tab === t ? "border-b-2 border-navy font-semibold text-navy" : "text-slate-500 hover:text-slate-800"}`}
                >
                  {t}
                </button>
              ))}
            </div>
            <div className="max-h-[75vh] overflow-y-auto p-4">
              {tab === "稽核結果" && <FindingsView findings={d.findings} onPick={setTarget} picked={target} />}
              {tab === "擷取欄位" && <FieldsView docs={d.extraction.documents} onPick={setTarget} />}
              {tab === "信件草稿" && (
                <div className="space-y-3 text-sm">
                  <dl className="grid grid-cols-[4rem_minmax(0,1fr)] gap-y-1">
                    <dt className="text-slate-500">主旨</dt><dd className="break-words font-medium">{d.draft.subject}</dd>
                    <dt className="text-slate-500">收件人</dt><dd className="break-words">{d.draft.to.join(", ")}</dd>
                    <dt className="text-slate-500">副本</dt><dd className="break-words">{d.draft.cc.join(", ") || "—"}</dd>
                    <dt className="text-slate-500">開頭</dt><dd>{d.draft.intro_source}</dd>
                  </dl>
                  {d.route.warnings.length > 0 && (
                    <ul className="rounded-md bg-amber-50 px-3 py-2 text-amber-900">
                      {d.route.warnings.map((w) => <li key={w}>⚠ {w}</li>)}
                    </ul>
                  )}
                  <iframe title="信件預覽" sandbox="allow-same-origin" srcDoc={d.draft.html} className="h-[28rem] w-full rounded-md ring-1 ring-slate-200" />
                  <a href={fileUrl(c.id, "草稿.eml")} className="inline-block rounded-md bg-navy px-3 py-1.5 font-semibold text-white">
                    下載草稿（.eml，用 Outlook 開啟）
                  </a>
                </div>
              )}
              {tab === "檔案" && (
                <div className="space-y-4 text-sm">
                  <ul className="space-y-1">
                    {files.map((f) => (
                      <li key={f}><a className="break-all text-navy hover:underline" href={fileUrl(c.id, f)}>{f}</a></li>
                    ))}
                  </ul>
                  {d.form && (
                    <div>
                      <h3 className="mb-1 font-semibold">驗收單內容</h3>
                      <table className="w-full">
                        <tbody className="divide-y divide-slate-100">
                          {Object.entries(d.form).map(([k, v]) => (
                            <tr key={k}><td className="w-28 py-1 text-slate-500">{k}</td><td className="break-words py-1">{v}</td></tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
              {tab === "歷程" && (
                <ol className="space-y-2 text-sm">
                  {c.history.map((h, i) => (
                    <li key={i} className="flex flex-wrap gap-2">
                      <span className="tabular-nums text-slate-500">{h.at.replace("T", " ")}</span>
                      <StatusBadge status={h.status} />
                      <span className="break-words">{h.note}</span>
                    </li>
                  ))}
                </ol>
              )}
            </div>
          </section>
          <section className="min-w-0 rounded-lg bg-white shadow-sm ring-1 ring-slate-200">
            <div className="border-b border-slate-200 px-4 py-2.5 text-sm font-medium">
              {target ? `${target.file === "invoice" ? "發票檔" : "附件"}・${target.label}` : "點左側的證據查看原始頁面"}
            </div>
            {target && (
              // eslint-disable-next-line @next/next/no-img-element -- 頁面圖片由本機 API 即時產生
              <img
                key={`${target.file}-${target.page}-${target.q}`}
                src={pageUrl(c.id, target.file, target.page, target.q)}
                alt={target.label}
                width={909}
                height={1286}
                className="h-auto w-full max-w-full"
              />
            )}
          </section>
        </div>
      )}
    </div>
  );
}
