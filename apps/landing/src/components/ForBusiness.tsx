"use client";

import {
  motion,
  useScroll,
  useTransform,
  MotionValue,
} from "framer-motion";
import { useRef } from "react";
import { TrendingUp, Users, MapPin, DollarSign } from "lucide-react";

const metrics = [
  {
    icon: TrendingUp,
    label: "Demand Visibility",
    value: "Real-time",
    description: "See what your city craves before events happen",
    bars: [35, 55, 70, 85, 60, 90, 65, 75, 80, 50],
  },
  {
    icon: Users,
    label: "Audience Insights",
    value: "360\u00b0",
    description: "Deep understanding of who attends what and why",
    bars: [60, 45, 80, 55, 90, 40, 75, 85, 50, 70],
  },
  {
    icon: MapPin,
    label: "Geo Intelligence",
    value: "Block-level",
    description: "Granular location-based event analytics",
    bars: [50, 70, 40, 85, 55, 65, 90, 45, 80, 60],
  },
  {
    icon: DollarSign,
    label: "Pricing Signals",
    value: "Dynamic",
    description: "Market-aware pricing recommendations",
    bars: [75, 50, 85, 60, 45, 80, 55, 90, 70, 65],
  },
];

const audiences = [
  "Event Organizers",
  "Venues & Promoters",
  "City Councils",
  "Tour Providers",
  "Ticketing Platforms",
  "Travel Agencies",
];

function FallingBlock({
  metric,
  index,
  scrollYProgress,
}: {
  metric: (typeof metrics)[number];
  index: number;
  scrollYProgress: MotionValue<number>;
}) {
  // Each block gets a staggered scroll window
  const segStart = 0.12 + index * 0.14;
  const fallPoint = segStart + 0.08;
  const bouncePoint = segStart + 0.11;
  const settlePoint = segStart + 0.14;

  // Fall → land → bounce → settle
  const y = useTransform(
    scrollYProgress,
    [segStart, fallPoint, bouncePoint, settlePoint],
    [-100, 0, -6, 0]
  );
  const opacity = useTransform(
    scrollYProgress,
    [segStart, segStart + 0.04],
    [0, 1]
  );
  const rotateX = useTransform(
    scrollYProgress,
    [segStart, fallPoint],
    [14, 0]
  );
  const scaleVal = useTransform(
    scrollYProgress,
    [segStart, fallPoint, bouncePoint, settlePoint],
    [0.96, 1.015, 0.995, 1]
  );

  // Impact glow when block lands
  const glowOpacity = useTransform(
    scrollYProgress,
    [fallPoint - 0.005, fallPoint, bouncePoint, settlePoint],
    [0, 0.7, 0.2, 0]
  );

  // Bar chart animates after block settles
  const barProgress = useTransform(
    scrollYProgress,
    [settlePoint, settlePoint + 0.06],
    [0, 1]
  );

  const Icon = metric.icon;

  return (
    <motion.div
      style={{
        y,
        opacity,
        rotateX,
        scale: scaleVal,
        transformOrigin: "center bottom",
      }}
      className="relative"
    >
      {/* Impact shockwave */}
      <motion.div
        style={{ opacity: glowOpacity }}
        className="absolute -bottom-1 inset-x-0 h-[2px]"
      >
        <div className="h-full bg-gradient-to-r from-transparent via-indigo-500/50 to-transparent blur-[2px]" />
        <div className="h-[6px] bg-gradient-to-r from-transparent via-indigo-500/20 to-transparent blur-md -mt-1" />
      </motion.div>

      {/* The block */}
      <div
        className="relative rounded-2xl border border-white/[0.08] bg-white/[0.025] backdrop-blur-sm overflow-hidden"
        style={{ transformStyle: "preserve-3d" }}
      >
        {/* Glass top edge highlight */}
        <div className="absolute top-0 inset-x-0 h-[1px] bg-gradient-to-r from-transparent via-white/[0.1] to-transparent" />

        <div className="p-6 md:p-8">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <div className="flex items-center gap-2.5 mb-1">
                <Icon className="w-4 h-4 text-[#555]" />
                <span className="text-xs text-[#666] font-medium uppercase tracking-wider">
                  {metric.label}
                </span>
              </div>
              <p className="text-sm text-[#555] mt-2">{metric.description}</p>
            </div>
            <span className="text-2xl md:text-3xl font-bold gradient-text flex-shrink-0">
              {metric.value}
            </span>
          </div>

          {/* Bar chart that fills after block settles */}
          <div className="mt-5 flex items-end gap-1 h-10">
            {metric.bars.map((height, j) => (
              <BarSegment
                key={j}
                height={height}
                index={j}
                progress={barProgress}
              />
            ))}
          </div>
        </div>
      </div>
    </motion.div>
  );
}

function BarSegment({
  height,
  index,
  progress,
}: {
  height: number;
  index: number;
  progress: MotionValue<number>;
}) {
  // Stagger each bar slightly
  const barStart = index * 0.06;
  const barEnd = barStart + 0.4;
  const h = useTransform(progress, [barStart, barEnd], [0, height]);
  const display = useTransform(h, (v) => `${v}%`);

  return (
    <motion.div
      style={{ height: display }}
      className="flex-1 rounded-sm bg-gradient-to-t from-indigo-500/25 to-indigo-500/5"
    />
  );
}

export default function ForBusiness() {
  const ref = useRef(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start 0.85", "end 0.15"],
  });

  return (
    <section
      ref={ref}
      className="py-32 px-6 bg-[#0a0a0a]"
      style={{ perspective: "1200px" }}
    >
      <div className="max-w-7xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <span className="text-xs font-medium text-[#888] uppercase tracking-wider">
            For Business
          </span>
          <h2 className="text-4xl md:text-5xl font-bold mt-4 tracking-tight">
            Intelligence,
            <br />
            <span className="gradient-text">not guesswork</span>
          </h2>
          <p className="text-[#666] text-lg mt-6 max-w-2xl mx-auto">
            Event organizers, venues, tour providers, and travel agencies get
            unprecedented visibility into cultural demand and audience behavior.
          </p>
        </motion.div>

        {/* Stacking blocks */}
        <div className="max-w-2xl mx-auto space-y-4">
          {metrics.map((metric, i) => (
            <FallingBlock
              key={i}
              metric={metric}
              index={i}
              scrollYProgress={scrollYProgress}
            />
          ))}
        </div>

        {/* Target audience pills */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="flex flex-wrap justify-center gap-3 mt-16"
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
