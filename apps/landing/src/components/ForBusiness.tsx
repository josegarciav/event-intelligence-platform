"use client";

import { motion } from "framer-motion";
import { TrendingUp, Users, MapPin, DollarSign } from "lucide-react";

const metrics = [
  {
    icon: TrendingUp,
    label: "Demand Visibility",
    value: "Real-time",
    description: "See what your city craves before events happen",
  },
  {
    icon: Users,
    label: "Audience Insights",
    value: "360\u00b0",
    description: "Deep understanding of who attends what and why",
  },
  {
    icon: MapPin,
    label: "Geo Intelligence",
    value: "Block-level",
    description: "Granular location-based event analytics",
  },
  {
    icon: DollarSign,
    label: "Pricing Signals",
    value: "Dynamic",
    description: "Market-aware pricing recommendations",
  },
];

const audiences = [
  "Event Organizers",
  "Venues & Promoters",
  "City Councils",
  "Tourism Boards",
  "Ticketing Platforms",
  "Experiential Brands",
];

export default function ForBusiness() {
  return (
    <section className="py-32 px-6 bg-[#0a0a0a]">
      <div className="max-w-7xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-20"
        >
          <span className="text-xs font-medium text-[#888] uppercase tracking-wider">
            For Business
          </span>
          <h2 className="text-4xl md:text-5xl font-bold mt-4 tracking-tight">
            Intelligence,
            <br />
            <span className="gradient-text">not guesswork.</span>
          </h2>
          <p className="text-[#666] text-lg mt-6 max-w-2xl mx-auto">
            Event organizers, venues, city councils, and brands get
            unprecedented visibility into cultural demand and audience behavior.
          </p>
        </motion.div>

        {/* Metrics dashboard visualization */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {metrics.map((metric, i) => {
            const Icon = metric.icon;
            return (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: i * 0.1 }}
                className="bento-card p-8 group"
              >
                <div className="flex items-start justify-between mb-8">
                  <div>
                    <Icon className="w-5 h-5 text-[#555] mb-3" />
                    <h3 className="text-sm text-[#888] font-medium">
                      {metric.label}
                    </h3>
                  </div>
                  <span className="text-3xl font-bold gradient-text">
                    {metric.value}
                  </span>
                </div>
                <p className="text-[#555] text-sm">{metric.description}</p>

                {/* Animated bar chart visualization */}
                <div className="mt-6 flex items-end gap-1.5 h-16">
                  {Array.from({ length: 12 }).map((_, j) => {
                    const heights = [35, 55, 40, 70, 85, 60, 45, 90, 65, 50, 75, 80];
                    return (
                      <motion.div
                        key={j}
                        initial={{ height: 0 }}
                        whileInView={{
                          height: `${heights[j % heights.length]}%`,
                        }}
                        viewport={{ once: true }}
                        transition={{
                          duration: 0.8,
                          delay: i * 0.1 + j * 0.05,
                        }}
                        className="flex-1 rounded-sm bg-gradient-to-t from-indigo-600/20 to-indigo-600/5 group-hover:from-indigo-600/40 group-hover:to-indigo-600/10 transition-colors duration-500"
                      />
                    );
                  })}
                </div>
              </motion.div>
            );
          })}
        </div>

        {/* Target audience pills */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="flex flex-wrap justify-center gap-3 mt-12"
        >
          {audiences.map((audience, i) => (
            <span
              key={i}
              className="px-4 py-2 text-xs text-[#666] border border-white/[0.06] rounded-full hover:border-white/[0.12] hover:text-[#888] transition-all duration-300 cursor-default"
            >
              {audience}
            </span>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
