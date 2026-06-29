import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Infera",
  description: "LLM chat with near real-time inference observability",
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
