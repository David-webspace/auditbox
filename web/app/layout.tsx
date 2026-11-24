import type { Metadata } from "next";
import Nav from "@/components/Nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "模具請款稽核",
  description: "模具請款文件自動稽核、驗收單與通知信草稿",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="zh-Hant-TW" className="h-full antialiased">
      <body className="flex min-h-full flex-col">
        <Nav />
        <main className="mx-auto w-full max-w-7xl min-w-0 flex-1 px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
