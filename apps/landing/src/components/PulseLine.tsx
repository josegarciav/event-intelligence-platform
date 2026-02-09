"use client";

import { motion, useScroll, useTransform } from "framer-motion";
import { useRef } from "react";

const heartbeatPath = [
  "M 0,50 H 350",
  // First pulse: P wave, QRS complex, T wave
  "L 370,50 L 382,43 L 394,50",
  "L 404,50 L 410,46 L 422,8 L 434,88 L 446,50",
  "L 464,50 L 476,38 L 492,50",
  // Flat between pulses
  "H 908",
  // Second pulse
  "L 928,50 L 940,43 L 952,50",
  "L 962,50 L 968,46 L 980,8 L 992,88 L 1004,50",
  "L 1022,50 L 1034,38 L 1050,50",
  // Flat to end
  "H 1400",
].join(" ");

export default function PulseLine() {
  const ref = useRef(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start 0.85", "end 0.25"],
  });

  const pathLength = useTransform(scrollYProgress, [0, 1], [0, 1]);
  const glowOpacity = useTransform(
    scrollYProgress,
    [0, 0.05, 0.9, 1],
    [0, 0.6, 0.6, 0]
  );

  return (
    <section ref={ref} className="py-8 overflow-hidden">
      <div className="max-w-7xl mx-auto px-6 md:px-12">
        <svg
          viewBox="0 0 1400 100"
          className="w-full"
          style={{ height: "60px" }}
          preserveAspectRatio="xMidYMid meet"
          fill="none"
        >
          <defs>
            <linearGradient
              id="pulseGrad"
              x1="0%"
              y1="0%"
              x2="100%"
              y2="0%"
            >
              <stop offset="0%" stopColor="#6366f1" stopOpacity="0" />
              <stop offset="15%" stopColor="#6366f1" />
              <stop offset="50%" stopColor="#a855f7" />
              <stop offset="85%" stopColor="#ec4899" />
              <stop offset="100%" stopColor="#ec4899" stopOpacity="0" />
            </linearGradient>
            <filter id="pulseGlow" x="-20%" y="-50%" width="140%" height="200%">
              <feGaussianBlur stdDeviation="6" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Background trace — faint static line so user sees the shape */}
          <path
            d={heartbeatPath}
            stroke="white"
            strokeWidth="1"
            strokeOpacity="0.03"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Glow layer */}
          <motion.path
            d={heartbeatPath}
            stroke="url(#pulseGrad)"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
            filter="url(#pulseGlow)"
            style={{
              pathLength,
              opacity: glowOpacity,
            }}
          />

          {/* Main crisp line */}
          <motion.path
            d={heartbeatPath}
            stroke="url(#pulseGrad)"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            style={{
              pathLength,
              opacity: glowOpacity,
            }}
          />
        </svg>
      </div>
    </section>
  );
}
