"use client";

import { motion, useReducedMotion } from "framer-motion";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { springSnappy } from "@/lib/motion";

/** Counts from GET /dashboard/summary (null before first load). */
export type SidebarNavCounts = {
  new_today: number;
  total: number;
  saved: number;
  price_changes: number;
};

const NAV_ITEMS: { href: string; label: string; countKey: keyof SidebarNavCounts }[] = [
  { href: "/dashboard", label: "New today", countKey: "new_today" },
  { href: "/dashboard/all", label: "All listings", countKey: "total" },
  { href: "/dashboard/saved", label: "Favourites", countKey: "saved" },
  { href: "/dashboard/price-changes", label: "Price changes", countKey: "price_changes" },
];

function labelWithCount(label: string, count: number | undefined) {
  if (count === undefined) return label;
  return `${label} (${count})`;
}

export default function Sidebar({ counts }: { counts?: SidebarNavCounts | null }) {
  const pathname = usePathname();
  const reduce = useReducedMotion();

  return (
    <motion.aside
      initial={reduce ? false : { opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={springSnappy}
      className="w-full shrink-0 rounded-lg border border-brand-200 bg-white shadow-card lg:w-[min(100%,17rem)] lg:sticky lg:top-6 lg:self-start"
    >
      <div className="border-b border-brand-200 px-4 py-5">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-brand-500">Workspace</p>
        <p className="mt-1 text-lg font-semibold text-brand-900">Exploring Madeira</p>
        <p className="mt-0.5 text-xs text-brand-600">Property discovery dashboard</p>
      </div>
      <nav className="flex flex-col gap-0.5 p-2">
        {NAV_ITEMS.map((item, i) => {
          const active =
            pathname === item.href || (item.href !== "/dashboard" && pathname?.startsWith(item.href));
          const n = counts ? counts[item.countKey] : undefined;
          return (
            <motion.div
              key={item.href}
              initial={reduce ? false : { opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ ...springSnappy, delay: reduce ? 0 : i * 0.04 }}
            >
              <motion.div whileHover={{ x: active ? 0 : 4 }} whileTap={{ scale: 0.98 }} transition={springSnappy}>
                <Link
                  href={item.href}
                  className={`block rounded-md px-3 py-2.5 text-sm font-medium transition-colors tabular-nums ${
                    active ? "bg-ocean-700 text-white shadow-sm" : "text-brand-700 hover:bg-brand-100"
                  }`}
                >
                  {labelWithCount(item.label, n)}
                </Link>
              </motion.div>
            </motion.div>
          );
        })}
      </nav>
    </motion.aside>
  );
}
