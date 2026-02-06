"use client";

export default function Footer() {
  return (
    <footer className="py-12 px-6 bg-slate-900 border-t border-indigo-500/20">
      <div className="max-w-6xl mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-8">
          <div>
            <h3 className="font-semibold mb-4">Pulsecity</h3>
            <p className="text-slate-400 text-sm">
              Event intelligence for your city.
            </p>
          </div>
          <div>
            <h4 className="font-semibold mb-4">Product</h4>
            <ul className="space-y-2 text-slate-400 text-sm">
              <li>
                <a href="#" className="hover:text-indigo-400 transition">
                  Features
                </a>
              </li>
              <li>
                <a href="#" className="hover:text-indigo-400 transition">
                  Pricing
                </a>
              </li>
              <li>
                <a href="#" className="hover:text-indigo-400 transition">
                  Docs
                </a>
              </li>
            </ul>
          </div>
          <div>
            <h4 className="font-semibold mb-4">Company</h4>
            <ul className="space-y-2 text-slate-400 text-sm">
              <li>
                <a href="#" className="hover:text-indigo-400 transition">
                  About
                </a>
              </li>
              <li>
                <a href="#" className="hover:text-indigo-400 transition">
                  Blog
                </a>
              </li>
              <li>
                <a href="#" className="hover:text-indigo-400 transition">
                  Contact
                </a>
              </li>
            </ul>
          </div>
          <div>
            <h4 className="font-semibold mb-4">Legal</h4>
            <ul className="space-y-2 text-slate-400 text-sm">
              <li>
                <a href="#" className="hover:text-indigo-400 transition">
                  Privacy
                </a>
              </li>
              <li>
                <a href="#" className="hover:text-indigo-400 transition">
                  Terms
                </a>
              </li>
            </ul>
          </div>
        </div>
        <div className="border-t border-indigo-500/20 pt-8 text-center text-slate-400 text-sm">
          <p>&copy; 2026 Pulsecity. All rights reserved.</p>
        </div>
      </div>
    </footer>
  );
}
