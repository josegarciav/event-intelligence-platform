"use client";

import { motion } from "framer-motion";
import { Zap, Database, Brain, BarChart3 } from "lucide-react";

const features = [
  {
    icon: Zap,
    title: "Real-time Ingestion",
    description:
      "Automatically collect and normalize events from 50+ sources in real-time",
  },
  {
    icon: Database,
    title: "Unified Schema",
    description: "All events normalized to a canonical schema with taxonomy",
  },
  {
    icon: Brain,
    title: "ML-Powered Enrichment",
    description: "Automatic extraction and enrichment of event features",
  },
  {
    icon: BarChart3,
    title: "Rich Analytics",
    description: "Deep analytics for understanding your city's event landscape",
  },
];

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.2,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5 },
  },
};

export default function Features() {
  return (
    <section
      id="features"
      className="py-24 px-6 bg-gradient-to-b from-slate-900 via-slate-800 to-slate-900"
    >
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <h2 className="text-4xl md:text-5xl font-bold gradient-text mb-4">
            Powerful Features
          </h2>
          <p className="text-slate-300 text-lg">
            Everything you need for event intelligence
          </p>
        </motion.div>

        <motion.div
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          className="grid grid-cols-1 md:grid-cols-2 gap-8"
        >
          {features.map((feature, index) => {
            const Icon = feature.icon;
            return (
              <motion.div
                key={index}
                variants={itemVariants}
                whileHover={{ y: -10 }}
                className="p-8 rounded-xl bg-gradient-to-br from-slate-800 to-slate-900 border border-indigo-500/20 hover:border-indigo-500/50 transition"
              >
                <Icon className="w-10 h-10 text-indigo-400 mb-4" />
                <h3 className="text-xl font-semibold mb-2">{feature.title}</h3>
                <p className="text-slate-400">{feature.description}</p>
              </motion.div>
            );
          })}
        </motion.div>
      </div>
    </section>
  );
}
