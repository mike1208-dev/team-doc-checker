import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "ZeeNote", description: "Turn rough notes into your team's daily report." };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
