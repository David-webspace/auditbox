"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const LINKS = [
  { href: "/", label: "執行" },
  { href: "/cases/", label: "案件追蹤" },
  { href: "/check/", label: "設定檢查" },
  { href: "/settings/", label: "模型設定" },
];

export default function Nav() {
  const path = usePathname();
  const [mailpit, setMailpit] = useState<string | null>(null);
  useEffect(() => {
    api.meta().then((m) => setMailpit(m.mailpit_url)).catch(() => {});
  }, []);
  const active = (href: string) => (href === "/" ? path === "/" : path.startsWith(href) || (href === "/cases/" && path.startsWith("/case")));
  return (
    <header className="bg-navy text-white">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
        <Link href="/" className="text-lg font-bold tracking-wide">
          模具請款稽核
        </Link>
        <nav className="flex flex-wrap gap-1">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`rounded-md px-3 py-1.5 text-sm ${active(l.href) ? "bg-white/20 font-semibold" : "text-white/80 hover:bg-white/10"}`}
            >
              {l.label}
            </Link>
          ))}
          {mailpit && (
            <a href={mailpit} target="_blank" rel="noopener" className="rounded-md px-3 py-1.5 text-sm text-white/80 hover:bg-white/10">
              模擬信箱 ↗
            </a>
          )}
        </nav>
      </div>
    </header>
  );
}
