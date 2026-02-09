"use client";

import { motion } from "framer-motion";

const roles = [
  {
    title: "Staff AI Engineer",
    type: "Engineering",
    location: "Remote",
    description:
      "Design the APIs, services, and infrastructure that serve millions of recommendations.",
  },
  {
    title: "Chief Tech Officer (CTO)",
    type: "Engineering",
    location: "Remote",
    description:
      "Lead the technical vision and execution of our city-scale intelligence platform.",
  },
];

const perks = [
  "Remote-first",
  "Meaningful work",
  "Small team, big impact",
  "City-by-city rollout",
  "User-first culture",
  "Open source contributions",
];

export default function CareersPage() {
  return (
    <main className="pt-24">
      {/* Hero */}
      <section className="py-32 px-6">
        <div className="max-w-5xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
          >
            <span className="text-xs font-medium text-[#888] uppercase tracking-wider">
              Careers
            </span>
            <h1 className="text-5xl md:text-7xl font-bold mt-6 tracking-tight leading-[1.05]">
              Build what
              <br />
              <span className="gradient-text">matters.</span>
            </h1>
          </motion.div>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="text-xl text-[#666] mt-8 max-w-3xl leading-relaxed"
          >
            We&apos;re a small team building city-scale intelligence
            infrastructure. Every person here shapes the product, the culture,
            and the company.
          </motion.p>
        </div>
      </section>

      {/* Culture */}
      <section className="py-32 px-6 bg-[#0a0a0a]">
        <div className="max-w-5xl mx-auto">
          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="text-3xl md:text-4xl font-bold tracking-tight mb-8"
          >
            How we work.
          </motion.h2>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="text-[#666] text-lg leading-relaxed max-w-2xl mb-12"
          >
            We believe in small teams doing focused work. No meetings for the
            sake of meetings. No bureaucracy. Just smart people solving hard
            problems and shipping fast.
          </motion.p>

          <div className="flex flex-wrap gap-3">
            {perks.map((perk, i) => (
              <motion.span
                key={i}
                initial={{ opacity: 0, scale: 0.9 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.05 }}
                className="px-5 py-2.5 text-sm text-[#888] border border-white/[0.06] rounded-full"
              >
                {perk}
              </motion.span>
            ))}
          </div>
        </div>
      </section>

      {/* Open Roles */}
      <section className="py-32 px-6">
        <div className="max-w-5xl mx-auto">
          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="text-3xl md:text-4xl font-bold tracking-tight mb-16"
          >
            Open roles.
          </motion.h2>

          <div className="border-t border-white/[0.06]">
            {roles.map((role, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.08 }}
                className="py-8 border-b border-white/[0.06] group cursor-pointer hover:pl-4 transition-all duration-300"
              >
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div>
                    <h3 className="text-lg font-semibold group-hover:text-indigo-400 transition-colors duration-300">
                      {role.title}
                    </h3>
                    <p className="text-sm text-[#555] mt-1">
                      {role.description}
                    </p>
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <span className="px-3 py-1 text-xs text-[#666] border border-white/[0.06] rounded-full">
                      {role.type}
                    </span>
                    <span className="px-3 py-1 text-xs text-[#666] border border-white/[0.06] rounded-full">
                      {role.location}
                    </span>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: 0.3 }}
            className="mt-16 text-center"
          >
            <p className="text-[#555] mb-6">
              Don&apos;t see your role? We&apos;re always looking for
              exceptional people.
            </p>
            <button className="px-8 py-4 bg-white text-black font-medium rounded-full hover:bg-white/90 transition-all duration-300 text-sm">
              Send Open Application
            </button>
          </motion.div>
        </div>
      </section>
    </main>
  );
}
