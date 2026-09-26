import type { Metadata } from "next";
import { DM_Sans } from "next/font/google";
import "maplibre-gl/dist/maplibre-gl.css";
import { ModeProvider } from "@/lib/mode";
import "./globals.css";

// One friendly geometric sans for everything (Happy Hues style)
const body = DM_Sans({ subsets: ["latin"], variable: "--font-body", weight: ["400", "500", "700"], style: ["normal", "italic"] });

export const metadata: Metadata = {
  title: "Sherlock Homes — AI Housing Detective for Pittsburgh",
  description: "Sherlock Homes investigates Pittsburgh housing data and shows where to look, with evidence, timing and limits.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={body.variable}>
      <body className="min-h-screen font-sans antialiased">
        <ModeProvider>{children}</ModeProvider>
      </body>
    </html>
  );
}
