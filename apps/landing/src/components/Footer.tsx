"use client";

import Image from "next/image";
import Link from "next/link";
import logo from "@/app/apple-icon.png";

const footerLinks = {
  Product: [
    { label: "Features", href: "/product" },
    { label: "For People", href: "/product#people" },
    { label: "For Business", href: "/product#business" },
    { label: "API", href: "/product#business" },
  ],
  Company: [
    { label: "About", href: "/about" },
    { label: "Careers", href: "/careers" },
    // { label: "Blog", href: "#" },
    // { label: "Press", href: "#" },
  ],
  Resources: [
    { label: "Documentation", href: "/docs" },
  ],
  Legal: [
    { label: "Privacy", href: "/privacy" },
    { label: "Terms", href: "/terms" },
    { label: "Cookies", href: "/cookies" },
  ],
};

export default function Footer() {
  return (
    <footer className="border-t border-white/[0.06] bg-[#050505]">
      <div className="max-w-7xl mx-auto px-6 md:px-12">
        <div className="py-16 grid grid-cols-2 md:grid-cols-5 gap-10">
          {/* Brand */}
          <div className="col-span-2 md:col-span-1">
            <Link href="/" className="flex items-center gap-2 mb-4">
              <Image
                src={logo}
                alt="Pulsecity"
                width={28}
                height={28}
                className="w-7 h-7 rounded-md object-cover"
              />
              <span className="font-semibold tracking-tight">Pulsecity</span>
            </Link>
            <p className="text-sm text-[#555] leading-relaxed">
              Help humans spend their free time better.
            </p>
          </div>

          {/* Link columns */}
          {Object.entries(footerLinks).map(([category, links]) => (
            <div key={category}>
              <h4 className="text-xs font-medium text-[#888] uppercase tracking-wider mb-4">
                {category}
              </h4>
              <ul className="space-y-3">
                {links.map((link) => (
                  <li key={link.label}>
                    <Link
                      href={link.href}
                      className="text-sm text-[#555] hover:text-white transition-colors duration-300"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom bar */}
        <div className="py-6 border-t border-white/[0.06] flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-xs text-[#444]">
            &copy; {new Date().getFullYear()} Pulsecity. All rights reserved.
          </p>
          <div className="flex items-center gap-6">
            {["Twitter", "LinkedIn", "GitHub"].map((social) => (
              <a
                key={social}
                href="#"
                className="text-xs text-[#444] hover:text-white transition-colors duration-300"
              >
                {social}
              </a>
            ))}
          </div>
        </div>
      </div>
    </footer>
  );
}
