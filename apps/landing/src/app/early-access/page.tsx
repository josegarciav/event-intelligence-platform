"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Check } from "lucide-react";
import Link from "next/link";
import PulseBee from "@/components/PulseBee";

const FORMSPREE_URL = "https://formspree.io/f/mbdalven";

export default function EarlyAccess() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [note, setNote] = useState("");
  const [status, setStatus] = useState<"idle" | "submitting" | "success" | "error">("idle");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus("submitting");

    try {
      const res = await fetch(FORMSPREE_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          email,
          _subject: "LEAD GENERATION MANAGEMENT",
          message: `Hello, client ${name} has registered for early access to the Pulsecity platform. Here is their associated email ID: ${email}.${note ? ` They said ${note}.` : ""} Happy coding!`,
        }),
      });

      if (res.ok) {
        setStatus("success");
      } else {
        setStatus("error");
      }
    } catch {
      setStatus("error");
    }
  };

  return (
    <main className="relative min-h-screen flex items-center justify-center overflow-hidden pt-24 px-6">
      {/* Animated gradient orbs */}
      <div className="absolute inset-0 overflow-hidden">
        <motion.div
          animate={{
            scale: [1, 1.2, 1],
            x: [0, 30, 0],
            y: [0, -20, 0],
          }}
          transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
          className="absolute top-1/4 left-1/4 w-[500px] h-[500px] rounded-full bg-indigo-600/[0.08] blur-[120px]"
        />
        <motion.div
          animate={{
            scale: [1.2, 1, 1.2],
            x: [0, -40, 0],
            y: [0, 30, 0],
          }}
          transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
          className="absolute bottom-1/4 right-1/4 w-[600px] h-[600px] rounded-full bg-purple-600/[0.07] blur-[120px]"
        />

        {/* Bee flythrough */}
        <motion.div
          initial={{ x: "-10vw", y: "40vh", opacity: 0 }}
          animate={{
            x: ["-10vw", "20vw", "40vw", "60vw", "80vw", "110vw"],
            y: ["40vh", "32vh", "45vh", "30vh", "38vh", "34vh"],
            opacity: [0, 0.25, 0.25, 0.25, 0.25, 0],
            rotate: [0, -4, 6, -5, 3, 0],
          }}
          transition={{
            duration: 20,
            delay: 1,
            ease: "easeInOut",
            times: [0, 0.1, 0.35, 0.6, 0.85, 1],
          }}
          className="absolute z-[1] pointer-events-none"
        >
          <motion.div
            animate={{ y: [0, -5, 0, 4, 0] }}
            transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
          >
            <div className="drop-shadow-[0_0_16px_rgba(139,92,246,0.35)]">
              <PulseBee size={44} />
            </div>
          </motion.div>
        </motion.div>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8 }}
        className="relative z-10 w-full max-w-md"
      >
        {status === "success" ? (
          <div className="bento-card p-10 text-center">
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: "spring", stiffness: 200, damping: 15 }}
              className="w-16 h-16 rounded-full gradient-bg flex items-center justify-center mx-auto mb-6"
            >
              <Check className="w-8 h-8 text-white" />
            </motion.div>
            <h1 className="text-3xl font-bold mb-3">
              You&apos;re on the <span className="gradient-text">list!</span>
            </h1>
            <p className="text-[#666] mb-8">
              We&apos;ll be in touch soon with early access details.
            </p>
            <Link
              href="/"
              className="inline-block px-8 py-3 bg-white text-black font-medium rounded-full hover:bg-white/90 transition-all duration-300 text-sm"
            >
              Back to Home
            </Link>
          </div>
        ) : (
          <div className="bento-card p-10">
            <div className="text-center mb-8">
              <h1 className="text-3xl sm:text-4xl font-bold tracking-tight mb-3">
                Get <span className="gradient-text">Early Access</span>
              </h1>
              <p className="text-[#666] text-sm">
                Join the waitlist and be among the first to experience intelligent event discovery.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label htmlFor="name" className="block text-sm text-[#888] mb-2">
                  Name
                </label>
                <input
                  id="name"
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Your name"
                  className="w-full px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white placeholder:text-[#555] focus:outline-none focus:border-white/[0.2] transition-colors duration-300 text-sm"
                />
              </div>

              <div>
                <label htmlFor="email" className="block text-sm text-[#888] mb-2">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="w-full px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white placeholder:text-[#555] focus:outline-none focus:border-white/[0.2] transition-colors duration-300 text-sm"
                />
              </div>

              <div>
                <label htmlFor="note" className="block text-sm text-[#888] mb-2">
                  Anything you&apos;d like us to know?{" "}
                  <span className="text-[#555]">(optional)</span>
                </label>
                <textarea
                  id="note"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="e.g. a role you're interested in, a question, or just say hi"
                  rows={3}
                  className="w-full px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white placeholder:text-[#555] focus:outline-none focus:border-white/[0.2] transition-colors duration-300 text-sm resize-none"
                />
              </div>

              {status === "error" && (
                <p className="text-red-400 text-sm">
                  Something went wrong. Please try again.
                </p>
              )}

              <button
                type="submit"
                disabled={status === "submitting"}
                className="w-full py-3.5 bg-white text-black font-medium rounded-full hover:bg-white/90 transition-all duration-300 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {status === "submitting" ? "Submitting..." : "Join Waitlist"}
              </button>
            </form>
          </div>
        )}
      </motion.div>
    </main>
  );
}
