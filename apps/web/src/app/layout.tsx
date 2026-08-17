import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { ActorProvider } from "@/lib/actor";
import { TopBar } from "@/components/TopBar";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "IPAC Governance Systems",
  description: "OPBOH assurance engine — Milestone 1.1",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-slate-50 text-slate-900">
        <ActorProvider>
          <TopBar />
          <main className="flex-1 w-full max-w-6xl mx-auto px-6 py-8">{children}</main>
        </ActorProvider>
      </body>
    </html>
  );
}
