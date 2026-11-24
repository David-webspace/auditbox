const STYLES: Record<string, string> = {
  可送簽: "bg-emerald-100 text-emerald-800 ring-emerald-200",
  待廠商補件: "bg-amber-100 text-amber-800 ring-amber-200",
  內部處理: "bg-orange-100 text-orange-800 ring-orange-200",
  主檔維護: "bg-violet-100 text-violet-800 ring-violet-200",
  系統失敗: "bg-red-100 text-red-800 ring-red-200",
  已寄補件: "bg-sky-100 text-sky-800 ring-sky-200",
  送簽中: "bg-blue-100 text-blue-800 ring-blue-200",
  已結案: "bg-slate-100 text-slate-600 ring-slate-200",
  處理中: "bg-blue-100 text-blue-800 ring-blue-200",
  完成: "bg-emerald-100 text-emerald-800 ring-emerald-200",
};

export const OUTCOME_LABEL: Record<string, string> = {
  ready_to_sign: "可送簽",
  need_vendor_docs: "待廠商補件",
  internal_action: "內部處理",
  master_data: "主檔維護",
  system_error: "系統失敗",
};

export default function StatusBadge({ status }: { status: string }) {
  const style = STYLES[status] ?? "bg-slate-100 text-slate-600 ring-slate-200";
  return (
    <span className={`inline-flex shrink-0 items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${style}`}>
      {status}
    </span>
  );
}
