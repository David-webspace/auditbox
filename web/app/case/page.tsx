import { Suspense } from "react";
import CaseDetail from "@/components/CaseDetail";

export default function CasePage() {
  return (
    <Suspense fallback={<p className="text-slate-400">讀取中…</p>}>
      <CaseDetail />
    </Suspense>
  );
}
