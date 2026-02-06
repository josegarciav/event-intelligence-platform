"use client";

import { motion } from "framer-motion";
import { ChevronRight } from "lucide-react";

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.2,
      delayChildren: 0.3,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.8 },
  },
};

export default function Hero() {
  return (
    <section className="min-h-screen flex items-center justify-center pt-20 px-6 relative overflow-hidden">
      {/* Gradient orbs */}
      <motion.div
        animate={{
          y: [0, 50, 0],
          x: [0, 30, 0],
        }}
        transition={{ duration: 8, repeat: Infinity }}
        className="absolute top-20 left-10 w-72 h-72 bg-purple-600/20 rounded-full blur-3xl"
      />
      <motion.div
        animate={{
          y: [0, -50, 0],
          x: [0, -30, 0],
        }}
        transition={{ duration: 10, repeat: Infinity }}
        className="absolute bottom-20 right-10 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl"
      />

      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="text-center max-w-4xl relative z-10"
      >
        <motion.div variants={itemVariants} className="mb-6">
          <span className="px-4 py-2 bg-indigo-500/10 border border-indigo-500/30 rounded-full text-indigo-300 text-sm">
            ✨ Real-time Event Intelligence
          </span>
        </motion.div>

        <motion.h1
          variants={itemVariants}
          className="text-6xl md:text-7xl font-bold gradient-text mb-6"
        >
          Discover What's Happening
        </motion.h1>

        <motion.p
          variants={itemVariants}
          className="text-xl text-slate-300 mb-8 leading-relaxed"
        >
          Pulsecity ingests, normalizes, and analyzes real-time event data from
          multiple sources. Make intelligent decisions about your city's
          cultural pulse.
        </motion.p>

        <motion.div
          variants={itemVariants}
          className="flex gap-4 justify-center flex-wrap"
        >
          <button className="px-8 py-4 bg-indigo-600 rounded-lg font-semibold hover:bg-indigo-500 transition flex items-center gap-2 glow-box">
            Launch Demo <ChevronRight className="w-4 h-4" />
          </button>
          <button className="px-8 py-4 border border-indigo-500/50 rounded-lg font-semibold hover:bg-indigo-500/10 transition">
            View Docs
          </button>
        </motion.div>

        <motion.div
          variants={itemVariants}
          className="mt-16 grid grid-cols-3 gap-8 text-left"
        >
          {[
            { number: "50+", label: "Event Sources" },
            { number: "Real-time", label: "Data Ingestion" },
            { number: "10x", label: "Faster Analysis" },
          ].map((stat) => (
            <div key={stat.label} className="p-4 borders border-indigo-500/20 rounded-lg bg-indigo-500/5">
              <div className="text-2xl font-bold text-indigo-400">
                {stat.number}
              </div>
              <div className="text-sm text-slate-400">{stat.label}</div>
            </div>
          ))}
        </motion.div>
      </motion.div>
    </section>
  );
}
