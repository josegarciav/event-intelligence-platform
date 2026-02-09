"use client";

import { motion } from "framer-motion";
import {
  Zap,
  Database,
  Brain,
  Globe,
  Compass,
  MapPin,
  Users,
  Shield,
} from "lucide-react";
import PulseLine from "@/components/PulseLine";

const capabilities = [
  {
    category: "Ingestion",
    icon: Globe,
    items: [
      "50+ source connectors",
      "API feed processing",
      "Resilient data collection",
    ],
  },
  {
    category: "Processing",
    icon: Database,
    items: [
      "Canonical event schema",
      "Intelligent deduplication",
      "Temporal normalization",
    ],
  },
  {
    category: "Intelligence",
    icon: Brain,
    items: [
      "ML-powered enrichment",
      "Taxonomy classification",
      "Price signal extraction",
    ],
  },
  {
    category: "Serving",
    icon: Zap,
    items: [
      "REST & GraphQL APIs",
      "Recommendation engine",
      "Search & filtering",
    ],
  },
];

const techStack = [
  { layer: "Ingestion", tools: "Python, Playwright, Airflow" },
  { layer: "Processing", tools: "FastAPI, Pydantic, spaCy, LLM assist" },
  { layer: "Storage", tools: "Postgres, S3, pgvector, Weaviate" },
  { layer: "Intelligence", tools: "Python ML, embeddings, implicit feedback" },
  { layer: "Serving", tools: "FastAPI, GraphQL, Redis, CDN" },
  { layer: "Clients", tools: "Next.js, Flutter, React Native" },
  { layer: "DevOps", tools: "Docker, Terraform, GitHub Actions" },
];

const peopleFeatures = [
  {
    title: "Taste Modeling",
    description:
      "We learn what you love \u2014 genres, vibes, formats \u2014 and surface experiences that match your unique preferences.",
    icon: Compass,
  },
  {
    title: "Context Awareness",
    description:
      "Time, mood, location, weather, who you\u2019re with. Every recommendation considers your real-world context.",
    icon: MapPin,
  },
  {
    title: "Social Planning",
    description:
      "Find experiences that work for your group. Overlapping tastes, shared availability, one perfect plan.",
    icon: Users,
  },
  {
    title: "Transparent Recs",
    description:
      "Every suggestion comes with a clear reason. No black-box algorithms. You always know why.",
    icon: Shield,
  },
];

const businessFeatures = [
  {
    title: "Demand Forecasting",
    description:
      "See what your city craves before events happen. Plan supply to meet real demand.",
  },
  {
    title: "Audience Analytics",
    description:
      "Deep segmentation of who attends what, when, and why. Build personas, not guesses.",
  },
  {
    title: "Pricing Intelligence",
    description:
      "Market-aware dynamic pricing signals. Optimize revenue without alienating audiences.",
  },
  {
    title: "Competitive Landscape",
    description:
      "Understand what else is happening when you plan to host. Avoid clashes, find gaps.",
  },
  {
    title: "Cultural Mapping",
    description:
      "Geo-intelligence on cultural density, underserved areas, and emerging scenes.",
  },
  {
    title: "ROI Measurement",
    description:
      "Track recommendation-to-ticket conversion. Measure the actual impact of intelligence.",
  },
];

export default function ProductPage() {
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
              Product
            </span>
            <h1 className="text-5xl md:text-7xl font-bold mt-6 tracking-tight leading-[1.05]">
              The intelligence
              <br />
              layer for <span className="gradient-text">events.</span>
            </h1>
          </motion.div>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="text-xl text-[#666] mt-8 max-w-3xl leading-relaxed"
          >
            Pulsecity transforms raw, fragmented event data into structured
            intelligence &mdash; powering discovery for users and analytics for
            businesses.
          </motion.p>
        </div>
      </section>

      {/* For People */}
      <section id="people" className="py-32 px-6 bg-[#0a0a0a]">
        <div className="max-w-5xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="mb-16"
          >
            <span className="text-xs font-medium text-indigo-400 uppercase tracking-wider">
              For People
            </span>
            <h2 className="text-3xl md:text-5xl font-bold mt-4 tracking-tight">
              Your city, understood.
            </h2>
            <p className="text-[#666] text-lg mt-6 max-w-2xl leading-relaxed">
              Whether you&apos;re a time-poor professional, a culture seeker, an
              expat discovering a new city, or planning a night out with friends
              &mdash; Pulsecity gives you the right experience at the right
              time.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {peopleFeatures.map((feature, i) => {
              const Icon = feature.icon;
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 30 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.6, delay: i * 0.1 }}
                  className="bento-card p-8 group"
                >
                  <Icon className="w-5 h-5 text-[#555] group-hover:text-white transition-colors duration-500 mb-4" />
                  <h3 className="text-lg font-semibold mb-2">
                    {feature.title}
                  </h3>
                  <p className="text-sm text-[#555] leading-relaxed">
                    {feature.description}
                  </p>
                </motion.div>
              );
            })}
          </div>
        </div>
      </section>

      <PulseLine />

      {/* For Business */}
      <section id="business" className="py-32 px-6">
        <div className="max-w-5xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="mb-16"
          >
            <span className="text-xs font-medium text-indigo-400 uppercase tracking-wider">
              For Business
            </span>
            <h2 className="text-3xl md:text-5xl font-bold mt-4 tracking-tight">
              Cultural intelligence at scale.
            </h2>
            <p className="text-[#666] text-lg mt-6 max-w-2xl leading-relaxed">
              Event organizers, venues, city councils, tourism boards, ticketing
              platforms, and brands get unprecedented visibility into cultural
              demand and audience behavior.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {businessFeatures.map((feature, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: i * 0.1 }}
                className="bento-card p-8 group"
              >
                <div className="w-8 h-8 rounded-full border border-white/[0.08] flex items-center justify-center mb-4 group-hover:border-white/[0.16] transition-colors duration-500">
                  <span className="text-xs text-[#555] font-medium">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                </div>
                <h3 className="text-lg font-semibold mb-2">{feature.title}</h3>
                <p className="text-sm text-[#555] leading-relaxed">
                  {feature.description}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <PulseLine />

      {/* Capabilities */}
      <section className="py-32 px-6 bg-[#0a0a0a]">
        <div className="max-w-5xl mx-auto">
          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="text-3xl md:text-4xl font-bold tracking-tight mb-16"
          >
            Under the hood.
          </motion.h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {capabilities.map((cap, i) => {
              const Icon = cap.icon;
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 30 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.6, delay: i * 0.1 }}
                  className="bento-card p-8"
                >
                  <div className="flex items-center gap-3 mb-6">
                    <Icon className="w-5 h-5 text-[#666]" />
                    <h3 className="font-semibold">{cap.category}</h3>
                  </div>
                  <ul className="space-y-3">
                    {cap.items.map((item, j) => (
                      <li
                        key={j}
                        className="flex items-center gap-3 text-sm text-[#555]"
                      >
                        <div className="w-1 h-1 rounded-full bg-indigo-500/50" />
                        {item}
                      </li>
                    ))}
                  </ul>
                </motion.div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Tech Stack */}
      <section className="py-32 px-6">
        <div className="max-w-5xl mx-auto">
          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="text-3xl md:text-4xl font-bold tracking-tight mb-16"
          >
            Technology.
          </motion.h2>

          <div className="border-t border-white/[0.06]">
            {techStack.map((item, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0 }}
                whileInView={{ opacity: 1 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.05 }}
                className="py-5 border-b border-white/[0.06] grid grid-cols-3 gap-4"
              >
                <span className="text-sm font-medium">{item.layer}</span>
                <span className="col-span-2 text-sm text-[#555]">
                  {item.tools}
                </span>
              </motion.div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
