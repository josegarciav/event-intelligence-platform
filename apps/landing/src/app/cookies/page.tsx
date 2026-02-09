"use client";

import { motion } from "framer-motion";

export default function CookiesPage() {
  return (
    <main className="pt-24">
      <section className="py-32 px-6">
        <div className="max-w-3xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
          >
            <span className="text-xs font-medium text-[#888] uppercase tracking-wider">
              Legal
            </span>
            <h1 className="text-5xl md:text-7xl font-bold mt-6 tracking-tight leading-[1.05]">
              Cookie Policy.
            </h1>
            <p className="text-sm text-[#444] mt-4">
              Last updated: February 2026
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="mt-12 space-y-8 text-[#666] leading-relaxed"
          >
            <div>
              <h2 className="text-lg font-semibold text-white mb-3">
                1. What Are Cookies
              </h2>
              <p>
                Cookies are small text files stored on your device when you
                visit our website. They help us provide you with a better
                experience by remembering your preferences and understanding
                how you use our services.
              </p>
            </div>

            <div>
              <h2 className="text-lg font-semibold text-white mb-3">
                2. Cookies We Use
              </h2>
              <p>
                We use essential cookies required for our platform to function,
                analytics cookies to understand usage patterns, and preference
                cookies to remember your settings. We do not use advertising or
                tracking cookies.
              </p>
            </div>

            <div>
              <h2 className="text-lg font-semibold text-white mb-3">
                3. Managing Cookies
              </h2>
              <p>
                You can control and manage cookies through your browser
                settings. Please note that disabling certain cookies may affect
                the functionality of our services.
              </p>
            </div>

            <div>
              <h2 className="text-lg font-semibold text-white mb-3">
                4. Contact
              </h2>
              <p>
                For questions about our cookie practices, please reach out
                through our platform.
              </p>
            </div>
          </motion.div>
        </div>
      </section>
    </main>
  );
}
