"use client";

import { motion, useScroll, useTransform, MotionValue } from "framer-motion";
import { useRef } from "react";

const problems = [
  { text: "Event data is fragmented, messy, duplicated.", highlight: false },
  {
    text: "Discovery tools are listing-based, not intelligence-based.",
    highlight: false,
  },
  { text: "Users don't lack options \u2014", highlight: true },
  { text: "they lack context fit.", highlight: true },
];

function ProblemLine({
  text,
  index,
  scrollYProgress,
  isHighlight,
}: {
  text: string;
  index: number;
  scrollYProgress: MotionValue<number>;
  isHighlight: boolean;
}) {
  const start = 0.15 + index * 0.12;
  const end = start + 0.2;
  const opacity = useTransform(scrollYProgress, [start, end], [0.1, 1]);
  const y = useTransform(scrollYProgress, [start, end], [30, 0]);

  return (
    <motion.p
      style={{ opacity, y }}
      className={`text-3xl md:text-5xl lg:text-6xl font-bold leading-tight mb-4 ${
        isHighlight ? "gradient-text" : "text-white"
      }`}
    >
      {text}
    </motion.p>
  );
}

export default function ProblemStatement() {
  const ref = useRef(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"],
  });

  return (
    <section ref={ref} className="py-32 md:py-48 px-6">
      <div className="max-w-5xl mx-auto">
        {problems.map((line, i) => (
          <ProblemLine
            key={i}
            text={line.text}
            index={i}
            scrollYProgress={scrollYProgress}
            isHighlight={line.highlight}
          />
        ))}
      </div>
    </section>
  );
}
