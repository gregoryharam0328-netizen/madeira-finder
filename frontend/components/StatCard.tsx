"use client";

import { motion, useReducedMotion } from "framer-motion";

import { springSnappy } from "@/lib/motion";

const accents = {
  neutral: { value: "text-brand-900", label: "text-brand-500" },
  emerald: { value: "text-emerald-700", label: "text-brand-500" },
  amber: { value: "text-amber-700", label: "text-brand-500" },
  blue: { value: "text-sky-700", label: "text-brand-500" },
  violet: { value: "text-violet-700", label: "text-brand-500" },
} as const;

export default function StatCard({
  label,
  value,
  accent = "neutral",
}: {
  label: string;
  value: number;
  accent?: keyof typeof accents;
}) {
  const reduce = useReducedMotion();
  const c = accents[accent] ?? accents.neutral;

  return (
    <motion.div
      layout
      whileHover={reduce ? undefined : { y: -2, transition: springSnappy }}
      className="h-full rounded-lg border border-brand-200 bg-white px-4 py-4 shadow-card transition-shadow hover:shadow-md"
    >
      <p className={`text-xs font-medium ${c.label}`}>{label}</p>
      <motion.p
        key={value}
        initial={reduce ? false : { opacity: 0.4, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={reduce ? { duration: 0 } : { duration: 0.2 }}
        className={`mt-1 text-2xl font-semibold tabular-nums ${c.value}`}
      >
        {value}
      </motion.p>
    </motion.div>
  );
}
