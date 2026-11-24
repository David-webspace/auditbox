"use client";

import type { ExtractedDoc, Finding } from "@/lib/api";

export type Target = { file: string; page: number; q: string | null; label: string };

const MARK = { fail: "❌", pass: "✅", skipped: "－" } as const;
const ORDER = { fail: 0, pass: 1, skipped: 2 } as const;

const DOC_LABEL: Record<string, string> = {
  invoice: "發票", po: "採購單 PO", commitment: "模具訂單承諾書", approval: "模具承認書", spec: "模具規格書",
  custody: "模具保管單", cost_breakdown: "模具費用明細表", photos: "模具照片", dimension_report: "尺寸檢測報告",
};

const show = (v: unknown) =>
  v === null || v === undefined ? "—" : Array.isArray(v) ? v.join(", ") : typeof v === "boolean" ? (v ? "是" : "否") : String(v);

export function FindingsView({ findings, onPick, picked }: { findings: Finding[]; onPick: (t: Target) => void; picked?: Target | null }) {
  const sorted = [...findings].sort((a, b) => ORDER[a.status] - ORDER[b.status] || a.rule.localeCompare(b.rule));
  return (
    <ul className="divide-y divide-slate-100">
      {sorted.map((f) => (
        <li key={f.rule} className={`py-2.5 ${f.status === "fail" ? "" : "text-slate-600"}`}>
          <div className="flex gap-2">
            <span aria-hidden>{MARK[f.status]}</span>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium">
                <span className="mr-1.5 font-mono text-xs text-slate-400">{f.rule}</span>
                {f.name}
              </div>
              <div className={`break-words text-sm ${f.status === "fail" ? "text-red-800" : "text-slate-500"}`}>{f.message}</div>
              {f.evidence.some((e) => e.page) && (
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {f.evidence.filter((e) => e.page && e.file).map((e, i) => {
                    const t = { file: e.file!, page: e.page!, q: e.raw ?? show(e.value), label: `${e.doc} 第 ${e.page} 頁` };
                    const on = picked && picked.file === t.file && picked.page === t.page && picked.q === t.q;
                    return (
                      <button
                        key={i}
                        onClick={() => onPick(t)}
                        className={`rounded px-2 py-0.5 text-xs ring-1 ${on ? "bg-navy text-white ring-navy" : "bg-slate-50 text-slate-700 ring-slate-200 hover:bg-slate-100"}`}
                      >
                        {e.doc} p{e.page}：{show(e.value)}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}

export function FieldsView({ docs, onPick }: { docs: Record<string, ExtractedDoc>; onPick: (t: Target) => void }) {
  return (
    <div className="space-y-4">
      {Object.entries(docs).map(([key, d]) => (
        <div key={key}>
          <h3 className="mb-1 flex flex-wrap items-baseline gap-2 text-sm font-semibold">
            {DOC_LABEL[key] ?? key}
            <button
              className="text-xs font-normal text-navy underline-offset-2 hover:underline"
              onClick={() => onPick({ file: d.file, page: d.pages[0], q: null, label: `${DOC_LABEL[key] ?? key} 第 ${d.pages[0]} 頁` })}
            >
              {d.file === "invoice" ? "發票檔" : "附件"} 第 {d.pages.join("、")} 頁
            </button>
          </h3>
          {Object.keys(d.fields).length > 0 && (
            <table className="w-full text-sm">
              <tbody className="divide-y divide-slate-100">
                {Object.entries(d.fields).map(([name, f]) => (
                  <tr key={name}>
                    <td className="w-40 py-1 pr-2 font-mono text-xs text-slate-500">{name}</td>
                    <td className="min-w-0 break-words py-1">
                      {f.page ? (
                        <button
                          className="text-left hover:underline"
                          onClick={() => onPick({ file: d.file, page: f.page!, q: f.raw, label: `${DOC_LABEL[key]} 第 ${f.page} 頁` })}
                        >
                          {show(f.value)}
                        </button>
                      ) : (
                        show(f.value)
                      )}
                    </td>
                    <td className="w-24 py-1 text-right text-xs">
                      {f.verified === false ? (
                        <span className="text-amber-700" title="擷取值不在引用頁的原文中，請人工確認">⚠ 原文未對上</span>
                      ) : f.verified ? (
                        <span className="text-emerald-700">原文已對上</span>
                      ) : (
                        <span className="text-slate-400">看圖判斷</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ))}
    </div>
  );
}
