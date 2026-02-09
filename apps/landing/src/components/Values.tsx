"use client";

import { motion } from "framer-motion";

const values = [
  {
    title: "Human time is sacred",
    description:
      "We optimize for meaningful experiences, not addiction loops.",
  },
  {
    title: "Discovery > exploitation",
    description:
      "Help people explore beyond algorithmic sameness.",
  },
  {
    title: "Cities are cultural organisms",
    description:
      "We strengthen local scenes, not just monetize them.",
  },
  {
    title: "Transparency in recommendations",
    description: "Explain why something is suggested. Always.",
  },
  {
    title: "Humane monetization",
    description: "Revenue should never degrade user wellbeing.",
  },
  {
    title: "Open cultural infrastructure",
    description:
      "A data layer cities and organizers benefit from.",
  },
];

export default function Values() {
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
            Our values
          </span>
          <h2 className="text-4xl md:text-5xl font-bold mt-4 tracking-tight">
            Built on
            <br />
            <span className="gradient-text">principles.</span>
          </h2>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-px bg-white/[0.06] rounded-2xl overflow-hidden">
          {values.map((value, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
              className="bg-[#050505] p-10 group hover:bg-white/[0.02] transition-colors duration-500"
            >
              <div className="w-8 h-8 rounded-full border border-white/[0.08] flex items-center justify-center mb-6 group-hover:border-white/[0.16] transition-colors duration-500">
                <span className="text-xs text-[#555] font-medium">
                  {String(i + 1).padStart(2, "0")}
                </span>
              </div>
              <h3 className="text-lg font-semibold mb-3">{value.title}</h3>
              <p className="text-sm text-[#555] leading-relaxed">
                {value.description}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
