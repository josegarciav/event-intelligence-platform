"use client";

import { motion } from "framer-motion";
import Link from "next/link";

export default function DocsPage() {
  return (
    <main className="pt-24">
      <section className="py-32 px-6">
        <div className="max-w-3xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
          >
            <span className="text-xs font-medium text-[#888] uppercase tracking-wider">
              Resources
            </span>
            <h1 className="text-5xl md:text-7xl font-bold mt-6 tracking-tight leading-[1.05]">
              Documentation.
            </h1>
          </motion.div>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="text-xl text-[#666] mt-8 leading-relaxed"
          >
            Our documentation is currently being prepared. API references,
            integration guides, and platform documentation will be available
            here soon.
          </motion.p>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.4 }}
            className="mt-12"
          >
            <Link href="/early-access" className="inline-block px-8 py-4 bg-white text-black font-medium rounded-full hover:bg-white/90 transition-all duration-300 text-sm">
              Get Notified When Ready
            </Link>
          </motion.div>
        </div>
      </section>
    </main>
  );
}
