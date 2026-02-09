"use client";

import { motion } from "framer-motion";

export default function PrivacyPage() {
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
              Privacy Policy.
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
                1. Information We Collect
              </h2>
              <p>
                Pulsecity collects information you provide directly, such as
                when you create an account, subscribe to our waitlist, or
                contact us. This may include your name and preferences.
              </p>
            </div>

            <div>
              <h2 className="text-lg font-semibold text-white mb-3">
                2. How We Use Your Information
              </h2>
              <p>
                We use your information to provide and improve our services,
                personalize your experience, communicate with you, and ensure
                the security of our platform. We never sell your personal data
                to third parties.
              </p>
            </div>

            <div>
              <h2 className="text-lg font-semibold text-white mb-3">
                3. Data Storage & Security
              </h2>
              <p>
                Your data is stored securely using industry-standard encryption.
                We implement appropriate technical and organizational measures
                to protect your personal information against unauthorized
                access, alteration, or destruction.
              </p>
            </div>

            <div>
              <h2 className="text-lg font-semibold text-white mb-3">
                4. Your Rights
              </h2>
              <p>
                You have the right to access, correct, or delete your personal
                data at any time. You may also request a copy of your data or
                opt out of certain data processing activities by contacting us.
              </p>
            </div>

            <div>
              <h2 className="text-lg font-semibold text-white mb-3">
                5. Contact
              </h2>
              <p>
                For privacy-related inquiries, please reach out to us through
                our platform.
              </p>
            </div>
          </motion.div>
        </div>
      </section>
    </main>
  );
}
