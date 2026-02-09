"use client";

import { motion } from "framer-motion";
import { Zap, Database, Brain, BarChart3, Compass, Globe } from "lucide-react";

const features = [
  {
    icon: Globe,
    title: "City-Scale Ingestion",
    description:
      "Automatically collect events from 50+ sources \u2014 APIs, feeds, and integrations \u2014 across entire cities.",
    size: "large",
  },
  {
    icon: Database,
    title: "Canonical Schema",
    description: "Every event normalized, deduplicated, and structured.",
    size: "small",
  },
  {
    icon: Brain,
    title: "ML Enrichment",
    description:
      "Taxonomy, vibe, audience, and price signals extracted automatically.",
    size: "small",
  },
  {
    icon: Compass,
    title: "Smart Discovery",
    description:
      "Recommendations powered by taste modeling, context, mood, and location \u2014 not just popularity.",
    size: "large",
  },
  {
    icon: BarChart3,
    title: "Cultural Analytics",
    description:
      "Deep insights into your city\u2019s event landscape for organizers, venues, and city councils.",
    size: "medium",
  },
  {
    icon: Zap,
    title: "Real-time Processing",
    description:
      "Events become live data assets within minutes, not days.",
    size: "medium",
  },
];

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.1 },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 30 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, ease: "easeOut" },
  },
};

export default function BentoGrid() {
  return (
    <section className="py-32 px-6">
      <div className="max-w-7xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-20"
        >
          <span className="text-xs font-medium text-[#888] uppercase tracking-wider">
            Capabilities
          </span>
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-bold mt-4 tracking-tight">
            Events become
            <br />
            <span className="gradient-text">data assets.</span>
          </h2>
        </motion.div>

        <motion.div
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: "-100px" }}
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
        >
          {features.map((feature, index) => {
            const Icon = feature.icon;
            const isLarge = feature.size === "large";

            return (
              <motion.div
                key={index}
                variants={itemVariants}
                className={`bento-card p-8 md:p-10 ${
                  isLarge ? "lg:col-span-2" : ""
                } group cursor-default`}
              >
                <div className="mb-6">
                  <div className="w-12 h-12 rounded-xl bg-white/[0.04] border border-white/[0.06] flex items-center justify-center group-hover:border-white/[0.12] transition-colors duration-500">
                    <Icon className="w-5 h-5 text-[#888] group-hover:text-white transition-colors duration-500" />
                  </div>
                </div>
                <h3 className="text-xl font-semibold mb-3 tracking-tight">
                  {feature.title}
                </h3>
                <p className="text-[#666] leading-relaxed text-sm">
                  {feature.description}
                </p>
              </motion.div>
            );
          })}
        </motion.div>
      </div>
    </section>
  );
}
