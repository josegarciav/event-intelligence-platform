"use client";

import { motion } from "framer-motion";

const personas = [
  {
    title: "Urban Professionals",
    description:
      "Time-poor, money-rich. Find the best experiences without the research.",
  },
  {
    title: "Culture Seekers",
    description:
      "Discover our 'Surprise Me' feature for serendipitous finds tailored to your vibe.",
  },
  {
    title: "Expats & Newcomers",
    description:
      "Navigate a new city\u2019s cultural landscape with confidence.",
  },
  {
    title: "Social Planners",
    description:
      "Plan perfect itineraries that work for everyone.",
  },
];

const highlights = [
  "Context-aware recs",
  "Mood matching",
  "Itinerary builder",
  "Transparent AI",
];

export default function ForPeople() {
  return (
    <section className="py-32 px-6">
      <div className="max-w-7xl mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-start">
          {/* Text side */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="lg:sticky lg:top-32"
          >
            <span className="text-xs font-medium text-[#888] uppercase tracking-wider">
              For People
            </span>
            <h2 className="text-4xl md:text-5xl font-bold mt-4 mb-6 tracking-tight">
              Discovery,
              <br />
              not listings
            </h2>
            <p className="text-[#666] text-lg leading-relaxed max-w-md">
              Stop scrolling through endless event lists. Pulsecity understands
              your taste, mood, and context to surface experiences that actually
              matter to you.
            </p>
          </motion.div>

          {/* Cards side */}
          <div className="space-y-4">
            {personas.map((persona, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: 30 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.1 }}
                className="bento-card p-8 group"
              >
                <h3 className="font-semibold mb-2 group-hover:text-indigo-400 transition-colors duration-300">
                  {persona.title}
                </h3>
                <p className="text-sm text-[#555] leading-relaxed">
                  {persona.description}
                </p>
              </motion.div>
            ))}

            {/* Feature highlights */}
            <div className="grid grid-cols-2 gap-4 pt-4">
              {highlights.map((feature, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.4, delay: 0.4 + i * 0.05 }}
                  className="py-3 px-4 text-center text-xs text-[#555] border border-white/[0.06] rounded-xl"
                >
                  {feature}
                </motion.div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
