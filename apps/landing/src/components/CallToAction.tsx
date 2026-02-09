"use client";

import { motion } from "framer-motion";

export default function CallToAction() {
  return (
    <section className="py-32 px-6 relative overflow-hidden">
      {/* Background gradient */}
      <div className="absolute inset-0">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-indigo-600/[0.03] to-transparent" />
        <motion.div
          animate={{
            scale: [1, 1.1, 1],
            opacity: [0.08, 0.12, 0.08],
          }}
          transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-indigo-600/10 blur-[150px]"
        />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.8 }}
        className="max-w-3xl mx-auto text-center relative z-10"
      >
        <h2 className="text-4xl md:text-6xl font-bold tracking-tight mb-6">
          Ready to feel
          <br />
          the <span className="gradient-text">pulse?</span>
        </h2>
        <p className="text-lg text-[#666] mb-10 max-w-xl mx-auto">
          Join the waitlist for early access. Be among the first to experience
          intelligent event discovery.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <button className="px-10 py-4 bg-white text-black font-medium rounded-full hover:bg-white/90 transition-all duration-300 text-sm">
            Join Waitlist
          </button>
          <button className="px-10 py-4 border border-white/[0.12] rounded-full font-medium hover:bg-white/[0.04] transition-all duration-300 text-sm">
            Talk to Us
          </button>
        </div>
      </motion.div>
    </section>
  );
}
