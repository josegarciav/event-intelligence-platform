"use client";

import { motion } from "framer-motion";
import PulseLine from "@/components/PulseLine";

const valuesList = [
  {
    title: "Human time is sacred",
    text: "We optimize for meaningful experiences, not addiction loops. Every feature is measured against this standard.",
  },
  {
    title: "Discovery over exploitation",
    text: "Help people explore beyond algorithmic sameness. Novelty and serendipity are features, not bugs.",
  },
  {
    title: "Cities are cultural organisms",
    text: "We strengthen local scenes and cultural ecosystems, not just monetize them.",
  },
  {
    title: "Radical transparency",
    text: "Every recommendation comes with a reason. No black boxes.",
  },
  {
    title: "Humane monetization",
    text: "Revenue should never degrade user wellbeing. If it hurts the user, we don\u2019t do it.",
  },
  {
    title: "Open infrastructure",
    text: "We\u2019re building a cultural data layer that cities and organizers directly benefit from.",
  },
];

const milestones = [
  {
    phase: "v0",
    title: "Ingestion + Schema",
    timeline: "4\u20136 weeks",
    description: "Core data pipeline and canonical event schema",
  },
  {
    phase: "MVP",
    title: "Discovery App",
    timeline: "8\u201312 weeks",
    description: "First city-scale event intelligence application",
  },
  {
    phase: "v1",
    title: "Personalization",
    timeline: "3\u20136 months",
    description: "Taste modeling and context-aware recommendations",
  },
];

const team = [
  { role: "Data Engineer", focus: "Ingestion & Infrastructure" },
  { role: "Data Scientist", focus: "Modeling & Experimentation" },
  { role: "Backend / Platform Engineer", focus: "Platform & APIs" },
];

export default function AboutPage() {
  return (
    <main className="pt-24">
      {/* Mission Hero */}
      <section className="py-32 px-6">
        <div className="max-w-5xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
          >
            <span className="text-xs font-medium text-[#888] uppercase tracking-wider">
              About Pulsecity
            </span>
            <h1 className="text-5xl md:text-7xl font-bold mt-6 tracking-tight leading-[1.05]">
              Building the operating
              <br />
              system for{" "}
              <span className="gradient-text">free time.</span>
            </h1>
          </motion.div>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="text-xl text-[#666] mt-8 max-w-3xl leading-relaxed"
          >
            We&apos;re building the intelligence infrastructure that connects
            people, cities, and experiences &mdash; transforming fragmented
            event data into meaningful real-world engagement.
          </motion.p>
        </div>
      </section>

      {/* Story */}
      <section className="py-32 px-6 bg-[#0a0a0a]">
        <div className="max-w-5xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6 }}
            >
              <h2 className="text-3xl md:text-4xl font-bold tracking-tight mb-6">
                The problem is clear.
              </h2>
              <div className="space-y-4 text-[#666] leading-relaxed">
                <p>
                  Every city pulses with cultural energy &mdash; concerts,
                  exhibitions, pop-ups, festivals, meetups. But discovering
                  what&apos;s right for you is broken.
                </p>
                <p>
                  Event data is scattered across dozens of platforms. Duplicated.
                  Inconsistent. No shared schema. No intelligence layer.
                </p>
                <p>
                  Users don&apos;t lack options. They lack context fit.
                </p>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: 0.1 }}
            >
              <h2 className="text-3xl md:text-4xl font-bold tracking-tight mb-6">
                Our approach is different.
              </h2>
              <div className="space-y-4 text-[#666] leading-relaxed">
                <p>
                  We treat events as data assets, not listings. We ingest,
                  normalize, enrich, and model them into an experience graph.
                </p>
                <p>
                  Then we build intelligence on top &mdash; taste modeling,
                  context awareness, cultural analytics &mdash; so every
                  recommendation has purpose.
                </p>
                <p>City by city. Scene by scene.</p>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      <PulseLine />

      {/* Values */}
      <section className="py-32 px-6">
        <div className="max-w-5xl mx-auto">
          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="text-3xl md:text-4xl font-bold tracking-tight mb-16"
          >
            What we believe.
          </motion.h2>

          <div className="space-y-0 border-t border-white/[0.06]">
            {valuesList.map((value, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0 }}
                whileInView={{ opacity: 1 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.05 }}
                className="py-8 border-b border-white/[0.06] grid grid-cols-1 md:grid-cols-3 gap-4"
              >
                <h3 className="font-semibold text-lg">{value.title}</h3>
                <p className="md:col-span-2 text-[#555] leading-relaxed">
                  {value.text}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Roadmap */}
      <section className="py-32 px-6 bg-[#0a0a0a]">
        <div className="max-w-5xl mx-auto">
          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="text-3xl md:text-4xl font-bold tracking-tight mb-16"
          >
            Where we&apos;re headed.
          </motion.h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {milestones.map((milestone, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: i * 0.1 }}
                className="bento-card p-8"
              >
                <span className="text-xs text-indigo-400 font-medium uppercase tracking-wider">
                  {milestone.phase}
                </span>
                <h3 className="text-xl font-semibold mt-3 mb-2">
                  {milestone.title}
                </h3>
                <p className="text-sm text-[#555] leading-relaxed mb-4">
                  {milestone.description}
                </p>
                <span className="text-xs text-[#444]">
                  {milestone.timeline}
                </span>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <PulseLine />

      {/* Team */}
      <section className="py-32 px-6">
        <div className="max-w-5xl mx-auto">
          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="text-3xl md:text-4xl font-bold tracking-tight mb-16"
          >
            The team we&apos;re building.
          </motion.h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {team.map((member, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.08 }}
                className="bento-card p-8"
              >
                <div className="w-12 h-12 rounded-full bg-gradient-to-br from-indigo-600/20 to-purple-600/20 mb-6" />
                <h3 className="font-semibold">{member.role}</h3>
                <p className="text-sm text-[#555] mt-1">{member.focus}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
