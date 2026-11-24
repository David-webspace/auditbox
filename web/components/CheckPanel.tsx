"use client";

import { useEffect, useState } from "react";
import { api, type HealthCheck, type LintIssue, type RoutingRule } from "@/lib/api";

const LEVEL = {
  error: ["錯誤", "bg-red-100 text-red-800"],
  warning: ["提醒", "bg-amber-100 text-amber-800"],
  info: ["建議", "bg-slate-100 text-slate-700"],
} as const;

export default function CheckPanel() {
  const [health, setHealth] = useState<HealthCheck[] | null>(null);
  const [lint, setLint] = useState<{ rules: RoutingRule[]; issues: LintIssue[] } | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.health().then(setHealth).catch((e) => setError(e.message));
    api.lint().then(setLint).catch((e) => setError(e.message));
  }, []);

  const issuesByRow = new Map<number, LintIssue[]>();
  lint?.issues.forEach((i) => issuesByRow.set(i.row, [...(issuesByRow.get(i.row) ?? []), i]));

  return (
    <div className="space-y-6">
      {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>}
      <section className="rounded-lg bg-white p-4 shadow-sm ring-1 ring-slate-200">
        <h2 className="mb-3 font-semibold">環境檢查</h2>
        {!health ? (
          <p className="text-sm text-slate-400">檢查中…</p>
        ) : (
          <ul className="divide-y divide-slate-100 text-sm">
            {health.map((h) => (
              <li key={h.name} className="flex flex-wrap gap-x-3 py-2">
                <span aria-hidden>{h.ok ? "✅" : "❌"}</span>
                <span className="w-56 font-medium">{h.name}</span>
                <span className="min-w-0 flex-1 break-words text-slate-600">{h.detail}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-lg bg-white p-4 shadow-sm ring-1 ring-slate-200">
        <h2 className="font-semibold">寄信對照表健檢</h2>
        <p className="mb-3 text-sm text-slate-500">
          對照表由大家共同維護，這裡列出格式錯誤、離職人員、重複與互相衝突的規則。請直接修改 00_設定/寄信對照表.xlsx。
        </p>
        {!lint ? (
          <p className="text-sm text-slate-400">檢查中…</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-sm">
              <thead className="bg-slate-50 text-left text-slate-600">
                <tr>
                  <th className="px-2 py-2">列</th>
                  <th className="px-2 py-2">規則</th>
                  <th className="px-2 py-2">結果</th>
                  <th className="px-2 py-2">條件</th>
                  <th className="px-2 py-2">收件人</th>
                  <th className="px-2 py-2">副本</th>
                  <th className="px-2 py-2">問題</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 align-top">
                {lint.rules.map((r) => {
                  const issues = issuesByRow.get(r.row) ?? [];
                  const worst = issues.find((i) => i.level === "error") ? "bg-red-50/60" : issues.length ? "bg-amber-50/50" : "";
                  return (
                    <tr key={r.row} className={`${worst} ${r.enabled ? "" : "text-slate-400"}`}>
                      <td className="px-2 py-2 tabular-nums">{r.row}</td>
                      <td className="px-2 py-2 font-mono">{r.rule_id}{!r.enabled && "（停用）"}</td>
                      <td className="whitespace-nowrap px-2 py-2">{r.outcome}</td>
                      <td className="px-2 py-2 text-xs">
                        {Object.entries(r.cond).filter(([, v]) => v !== "*").map(([k, v]) => `${k}=${v}`).join("、") || "不限"}
                      </td>
                      <td className="break-all px-2 py-2 text-xs">{r.to.join("; ")}</td>
                      <td className="break-all px-2 py-2 text-xs">{r.cc.join("; ")}</td>
                      <td className="px-2 py-2">
                        {issues.map((i, k) => (
                          <div key={k} className="mb-1 flex gap-1.5">
                            <span className={`shrink-0 rounded px-1.5 text-xs ${LEVEL[i.level][1]}`}>{LEVEL[i.level][0]}</span>
                            <span className="break-words text-xs">{i.message}</span>
                          </div>
                        ))}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
