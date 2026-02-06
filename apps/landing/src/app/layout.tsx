import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Pulsecity - Event Intelligence Platform",
  description: "Discover real-time event intelligence for your city",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
