"use client";

import { motion } from "framer-motion";

const steps = [
  {
    number: "01",
    title: "Ingest",
    description:
      "APIs, feeds, and integrations \u2014 50+ sources collected and aggregated in real-time.",
  },
  {
    number: "02",
    title: "Normalize",
    description:
      "Canonical schema. Deduplication. Clean, structured data.",
  },
  {
    number: "03",
    title: "Enrich",
    description:
      "Taxonomy, vibe, audience signals, and price intelligence extracted via ML.",
  },
  {
    number: "04",
    title: "Serve",
    description:
      "Discovery apps, APIs, dashboards, and recommendation engines \u2014 all powered.",
  },
];

export default function Pipeline() {
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
            How it works
          </span>
          <h2 className="text-4xl md:text-5xl font-bold mt-4 tracking-tight">
            From chaos to
            <br />
            <span className="gradient-text">clarity.</span>
          </h2>
        </motion.div>

        <div className="relative">
          {/* Connecting line */}
          <div className="hidden lg:block absolute left-0 right-0 top-1/2 h-[1px] bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {steps.map((step, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 40 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: i * 0.15 }}
                className="relative"
              >
                {/* Step node on the line */}
                <div className="hidden lg:flex absolute -top-3 left-1/2 -translate-x-1/2 -translate-y-full items-center justify-center">
                  <motion.div
                    initial={{ scale: 0 }}
                    whileInView={{ scale: 1 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.4, delay: i * 0.15 + 0.3 }}
                    className="w-6 h-6 rounded-full border border-white/[0.12] bg-[#050505] flex items-center justify-center"
                  >
                    <div className="w-2 h-2 rounded-full gradient-bg" />
                  </motion.div>
                </div>

                <div className="bento-card p-8 text-center lg:text-left">
                  <span className="text-4xl font-bold text-white/[0.06]">
                    {step.number}
                  </span>
                  <h3 className="text-xl font-semibold mt-4 mb-3">
                    {step.title}
                  </h3>
                  <p className="text-sm text-[#666] leading-relaxed">
                    {step.description}
                  </p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
