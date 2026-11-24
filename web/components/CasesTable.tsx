"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ageDays, api, type CaseRow } from "@/lib/api";
import StatusBadge from "./StatusBadge";

const OPEN = ["可送簽", "待廠商補件", "內部處理", "主檔維護", "系統失敗", "已寄補件", "送簽中"];

export default function CasesTable() {
  const [rows, setRows] = useState<CaseRow[] | null>(null);
  const [error, setError] = useState("");
  const [pic, setPic] = useState("");
  const [status, setStatus] = useState("未結案");

  useEffect(() => {
    api.cases().then(setRows).catch((e) => setError(e.message));
  }, []);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    rows?.forEach((r) => (c[r.status] = (c[r.status] ?? 0) + 1));
    return c;
  }, [rows]);

  const pics = useMemo(() => [...new Set(rows?.map((r) => r.pic))].sort(), [rows]);
  const shown = (rows ?? []).filter(
    (r) =>
      (!pic || r.pic === pic) &&
      (status === "全部" || (status === "未結案" ? OPEN.includes(r.status) : r.status === status)),
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {["未結案", "全部", ...Object.keys(counts)].map((s) => (
          <button
            key={s}
            onClick={() => setStatus(s)}
            className={`rounded-full px-3 py-1 text-sm ring-1 ${status === s ? "bg-navy text-white ring-navy" : "bg-white text-slate-700 ring-slate-300 hover:bg-slate-50"}`}
          >
            {s}
            {counts[s] !== undefined && <span className="ml-1.5 tabular-nums opacity-70">{counts[s]}</span>}
          </button>
        ))}
        <select
          aria-label="承辦"
          value={pic}
          onChange={(e) => setPic(e.target.value)}
          className="ml-auto rounded-md border border-slate-300 bg-white px-3 py-1 text-sm"
        >
          <option value="">全部承辦</option>
          {pics.map((p) => (
            <option key={p}>{p}</option>
          ))}
        </select>
      </div>
      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>}
      <div className="overflow-hidden rounded-lg bg-white shadow-sm ring-1 ring-slate-200">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="bg-slate-50 text-left text-slate-600">
              <tr>
                <th className="px-3 py-2">狀態</th>
                <th className="px-3 py-2">廠商</th>
                <th className="px-3 py-2">PO 號</th>
                <th className="px-3 py-2">案件</th>
                <th className="px-3 py-2">承辦</th>
                <th className="px-3 py-2">最後更新</th>
                <th className="px-3 py-2 text-right">停留天數</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows === null && (
                <tr>
                  <td colSpan={7} className="px-3 py-8 text-center text-slate-400">讀取中…</td>
                </tr>
              )}
              {rows && shown.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-3 py-8 text-center text-slate-400">沒有符合的案件</td>
                </tr>
              )}
              {shown.map((r) => {
                const age = ageDays(r.updated);
                return (
                  <tr key={r.id} className="hover:bg-slate-50">
                    <td className="px-3 py-2">
                      <StatusBadge status={r.status} />
                    </td>
                    <td className="px-3 py-2">{r.vendor}</td>
                    <td className="px-3 py-2 font-mono tabular-nums">
                      <Link href={`/case/?id=${encodeURIComponent(r.id)}`} className="text-navy underline-offset-2 hover:underline">
                        {r.po_no ?? "—"}
                      </Link>
                    </td>
                    <td className="max-w-48 truncate px-3 py-2 text-slate-600">{r.base}</td>
                    <td className="px-3 py-2">{r.pic}</td>
                    <td className="px-3 py-2 tabular-nums text-slate-600">{r.updated.replace("T", " ").slice(0, 16)}</td>
                    <td className={`px-3 py-2 text-right tabular-nums ${age >= 7 && OPEN.includes(r.status) ? "font-semibold text-red-700" : ""}`}>
                      {age}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
