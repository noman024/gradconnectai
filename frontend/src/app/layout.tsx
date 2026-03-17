import type { Metadata } from "next";
import "./globals.css";

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
      <body>{children}</body>
    </html>
  );
}
