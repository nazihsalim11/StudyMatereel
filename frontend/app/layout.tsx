import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "StudyReels — Turn slides into vertical videos",
  description: "Upload a PDF or PPTX and get a narrated vertical study reel in minutes.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
