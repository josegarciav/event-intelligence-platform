"use client";

import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";

export default function Navigation() {
  return (
    <motion.nav
      initial={{ y: -100 }}
      animate={{ y: 0 }}
      transition={{ duration: 0.5 }}
      className="fixed top-0 w-full bg-slate-900/80 backdrop-blur-md z-50 border-b border-indigo-500/20"
    >
      <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="w-6 h-6 text-indigo-400" />
          <span className="font-bold text-xl gradient-text">Pulsecity</span>
        </div>
        <div className="flex gap-8">
          <a href="#features" className="hover:text-indigo-400 transition">
            Features
          </a>
          <a href="#how-it-works" className="hover:text-indigo-400 transition">
            How it Works
          </a>
          <a href="#" className="hover:text-indigo-400 transition">
            Docs
          </a>
        </div>
        <button className="px-6 py-2 bg-indigo-600 rounded-lg hover:bg-indigo-500 transition">
          Get Started
        </button>
      </div>
    </motion.nav>
  );
}
