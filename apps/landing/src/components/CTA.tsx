"use client";

import { motion } from "framer-motion";

export default function CTA() {
  return (
    <section className="py-24 px-6 bg-gradient-to-r from-indigo-600/20 to-purple-600/20 border-t border-indigo-500/20">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        viewport={{ once: true }}
        className="max-w-2xl mx-auto text-center"
      >
        <h2 className="text-4xl font-bold mb-4">
          Ready to Understand Your City's Pulse?
        </h2>
        <p className="text-slate-300 text-lg mb-8">
          Start analyzing real-time event data today
        </p>
        <button className="px-8 py-4 bg-indigo-600 rounded-lg font-semibold hover:bg-indigo-500 transition glow-box">
          Get Started Free
        </button>
      </motion.div>
    </section>
  );
}
