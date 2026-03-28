import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "FloodStream",
  description: "NFIP claim automation dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-zinc-950 text-zinc-100">
        <header className="border-b border-zinc-800 px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-semibold tracking-tight">FloodStream</h1>
            <span className="text-xs text-zinc-500 font-mono">Anchor Adjusters</span>
          </div>
          <nav className="flex gap-4 text-sm">
            <a href="/" className="text-zinc-400 hover:text-zinc-100 transition-colors">Claims</a>
            <a href="/import" className="text-zinc-400 hover:text-zinc-100 transition-colors">Import</a>
            <a href="/prelim" className="text-zinc-400 hover:text-zinc-100 transition-colors">New Prelim</a>
            <a href="/upload" className="text-zinc-400 hover:text-zinc-100 transition-colors">Upload Final</a>
          </nav>
        </header>
        <main className="flex-1 p-6">{children}</main>
      </body>
    </html>
  );
}
