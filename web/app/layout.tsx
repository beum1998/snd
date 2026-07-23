import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "크립토 패턴 봇 — 테스트베드",
  description: "차트에서 스스로 발견한 패턴을 검증하는 대시보드",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
