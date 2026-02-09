"use client";

import { motion } from "framer-motion";

export default function TermsPage() {
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
              Terms of Service.
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
                1. Acceptance of Terms
              </h2>
              <p>
                By accessing or using Pulsecity&apos;s services, you agree to be
                bound by these Terms of Service. If you do not agree to these
                terms, please do not use our services.
              </p>
            </div>

            <div>
              <h2 className="text-lg font-semibold text-white mb-3">
                2. Use of Services
              </h2>
              <p>
                Pulsecity provides event intelligence and discovery services.
                You agree to use our services only for lawful purposes and in
                accordance with these terms. You are responsible for maintaining
                the confidentiality of your account credentials.
              </p>
            </div>

            <div>
              <h2 className="text-lg font-semibold text-white mb-3">
                3. Intellectual Property
              </h2>
              <p>
                All content, features, and functionality of Pulsecity&apos;s
                services are owned by Pulsecity and are protected by
                international copyright, trademark, and other intellectual
                property laws.
              </p>
            </div>

            <div>
              <h2 className="text-lg font-semibold text-white mb-3">
                4. Limitation of Liability
              </h2>
              <p>
                Pulsecity shall not be liable for any indirect, incidental,
                special, or consequential damages arising from your use of our
                services. Our total liability shall not exceed the amount you
                have paid us in the preceding twelve months.
              </p>
            </div>

            <div>
              <h2 className="text-lg font-semibold text-white mb-3">
                5. Changes to Terms
              </h2>
              <p>
                We reserve the right to modify these terms at any time. We will
                notify users of material changes through our platform. Continued use after changes constitutes acceptance.
              </p>
            </div>

            <div>
              <h2 className="text-lg font-semibold text-white mb-3">
                6. Contact
              </h2>
              <p>
                For questions about these terms, please reach out through our
                platform.
              </p>
            </div>
          </motion.div>
        </div>
      </section>
    </main>
  );
}
