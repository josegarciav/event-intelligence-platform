"use client";

import { motion } from "framer-motion";

/**
 * Custom SVG character faithfully traced from the Pulsecity logo.
 * A ribbon-like "P" with a sharp top fin, eye, and three long
 * swept-back wing arcs that flap.
 */
export default function PulseBee({ size = 48 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size * 1.3}
      viewBox="0 0 80 110"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        {/* Main body gradient — bright purple top to deep purple bottom */}
        <linearGradient id="beeBody" x1="30" y1="5" x2="55" y2="108" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#c084fc" />
          <stop offset="30%" stopColor="#a855f7" />
          <stop offset="60%" stopColor="#7c3aed" />
          <stop offset="100%" stopColor="#5b21b6" />
        </linearGradient>
        {/* Inner ribbon highlight — lighter to show dimension */}
        <linearGradient id="beeHighlight" x1="35" y1="20" x2="60" y2="80" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#d8b4fe" />
          <stop offset="50%" stopColor="#a855f7" />
          <stop offset="100%" stopColor="#7c3aed" />
        </linearGradient>
        {/* Fin gradient */}
        <linearGradient id="beeFin" x1="42" y1="0" x2="56" y2="20" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#a855f7" />
          <stop offset="100%" stopColor="#6d28d9" />
        </linearGradient>
        {/* Wing gradient — pink to purple */}
        <linearGradient id="beeWing" x1="0" y1="10" x2="38" y2="35" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#f0abfc" />
          <stop offset="60%" stopColor="#d946ef" />
          <stop offset="100%" stopColor="#a855f7" />
        </linearGradient>
      </defs>

      {/*
        === BODY: Filled ribbon P-shape ===
        Outer silhouette traced as a single filled path.
        The ribbon flows: stem top → bowl right → bowl curves back →
        stem continues down → tail curls → back up the left edge.
      */}
      <path
        d={`
          M 36 22
          C 34 28, 32 42, 32 55
          C 32 70, 30 82, 31 92
          C 32 100, 34 106, 38 108
          C 42 110, 46 106, 47 100
          C 48 94, 47 86, 46 78
          C 45 70, 44 64, 46 58
          C 48 54, 56 52, 65 46
          C 72 42, 77 38, 78 34
          C 79 30, 76 22, 56 14
          C 50 12, 44 14, 40 18
          Z
        `}
        fill="url(#beeBody)"
      />

      {/* Inner ribbon fold — lighter band to show the ribbon twisting through the bowl */}
      <path
        d={`
          M 40 24
          C 44 20, 52 18, 58 20
          C 64 22, 70 28, 70 32
          C 70 36, 66 42, 58 44
          C 50 46, 46 44, 44 40
          C 42 36, 42 30, 40 28
          Z
        `}
        fill="url(#beeHighlight)"
        opacity="0.35"
      />

      {/* Second ribbon fold — the crossing/overlap where bowl meets stem */}
      <path
        d={`
          M 44 52
          C 46 48, 50 46, 54 48
          C 58 50, 56 56, 50 58
          C 46 60, 42 58, 44 52
          Z
        `}
        fill="url(#beeHighlight)"
        opacity="0.25"
      />

      {/* Tail curl highlight */}
      <path
        d={`
          M 38 90
          C 36 96, 38 102, 42 104
          C 44 105, 46 102, 46 98
          C 46 94, 44 88, 40 86
          Z
        `}
        fill="url(#beeHighlight)"
        opacity="0.3"
      />

      {/* === TOP FIN / EAR — sharp and angular === */}
      <path
        d={`
          M 44 18
          C 46 12, 50 4, 56 2
          C 58 1, 60 3, 58 6
          C 56 10, 50 16, 46 20
          Z
        `}
        fill="url(#beeFin)"
      />

      {/* === EYE === */}
      <ellipse cx="58" cy="32" rx="2.8" ry="3" fill="#1a0533" />
      <circle cx="59" cy="31" r="1" fill="white" opacity="0.9" />

      {/* === WINGS — 3 long, elegant swept-back arcs that flap === */}
      <motion.g
        style={{ transformOrigin: "38px 24px" }}
        animate={{ rotate: [0, -22, 0, -22, 0] }}
        transition={{ duration: 0.2, repeat: Infinity, ease: "easeInOut" }}
      >
        {/* Wing 1 — topmost, longest, most visible */}
        <path
          d="M 36 20 C 26 12, 14 4, 2 2"
          stroke="url(#beeWing)"
          strokeWidth="2.5"
          strokeLinecap="round"
          fill="none"
          opacity="0.9"
        />
        {/* Wing 2 — middle */}
        <path
          d="M 35 25 C 24 18, 12 12, 2 12"
          stroke="url(#beeWing)"
          strokeWidth="2.2"
          strokeLinecap="round"
          fill="none"
          opacity="0.7"
        />
        {/* Wing 3 — innermost, shortest */}
        <path
          d="M 34 30 C 24 24, 14 20, 5 21"
          stroke="url(#beeWing)"
          strokeWidth="1.8"
          strokeLinecap="round"
          fill="none"
          opacity="0.5"
        />
      </motion.g>
    </svg>
  );
}
