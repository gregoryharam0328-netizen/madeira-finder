import "./globals.css";
import type { ReactNode } from "react";
import { Inter } from "next/font/google";

const sans = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata = {
  title: "Exploring Madeira — Property Finder",
  description: "Daily Madeira property discovery for the Exploring Madeira team.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={sans.variable}>
      <body className="font-sans">{children}</body>
    </html>
  );
}
