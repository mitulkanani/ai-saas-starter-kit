import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI SaaS Starter Kit",
  description: "A multi-tenant AI SaaS workspace with transparent usage metering.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
