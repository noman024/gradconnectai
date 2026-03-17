import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import Nav from "@/components/Nav";

export const metadata: Metadata = {
  title: "GradConnectAI",
  description: "AI-driven supervisor discovery and matching for graduate students",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="gc-shell">
        <header className="gc-header">
          <Link href="/" className="gc-logo">
            GradConnect<span>AI</span>
          </Link>
          <Nav />
        </header>
        <main className="gc-main">
          <div className="gc-container">{children}</div>
        </main>
      </body>
    </html>
  );
}
