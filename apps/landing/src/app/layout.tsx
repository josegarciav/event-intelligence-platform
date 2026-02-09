import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Navigation from "@/components/Navigation";
import Footer from "@/components/Footer";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "Pulsecity — Help humans spend their free time better",
  description:
    "A city-scale intelligence platform that transforms fragmented event data into personalized, free-time recommendations and analytics.",
  keywords: [
    "events",
    "intelligence",
    "city",
    "discovery",
    "analytics",
    "recommendations",
  ],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className={`${inter.className} antialiased`}>
        <div className="noise" />
        <Navigation />
        {children}
        <Footer />
      </body>
    </html>
  );
}
