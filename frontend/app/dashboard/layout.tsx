"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { label: "AI Chat", href: "/dashboard/chat", icon: "✦" },
  { label: "Data Sources", href: "/dashboard/sources", icon: "⊞" },
  { label: "Settings", href: "/dashboard/settings", icon: "⊙" },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex h-screen bg-white">
      {/* Sidebar */}
      <aside className="w-52 flex-shrink-0 border-r border-gray-100 flex flex-col bg-white">
        {/* Logo */}
        <div className="px-4 py-4 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-indigo-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-xs">A</span>
            </div>
            <span className="font-semibold text-gray-900 text-sm tracking-tight">AskData</span>
          </div>
        </div>

        {/* Search */}
        <div className="px-3 py-3 border-b border-gray-100">
          <div className="flex items-center gap-2 bg-gray-50 rounded-lg px-3 py-2">
            <span className="text-gray-400 text-xs">⌕</span>
            <span className="text-xs text-gray-400">Search…</span>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 py-2 space-y-0.5">
          {navItems.map((item) => {
            const active = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                  active
                    ? "bg-indigo-50 text-indigo-700 font-medium"
                    : "text-gray-500 hover:bg-gray-50 hover:text-gray-800"
                }`}
              >
                <span className="text-base leading-none w-4 text-center">{item.icon}</span>
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* Bottom */}
        <div className="px-2 py-3 border-t border-gray-100 space-y-0.5">
          <div className="flex items-center gap-2.5 px-3 py-2 rounded-lg">
            <span className="text-xs text-gray-400">◐</span>
            <span className="text-xs text-gray-400">Light</span>
          </div>
        </div>
      </aside>

      <main className="flex-1 overflow-hidden">{children}</main>
    </div>
  );
}
