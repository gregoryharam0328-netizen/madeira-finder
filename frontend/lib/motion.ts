import type { Transition, Variants } from "framer-motion";

/** Shared motion presets; keep durations short for snappy UI. */
export const springSnappy: Transition = { type: "spring", stiffness: 380, damping: 28 };

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0 },
};

export const staggerContainer: Variants = {
  hidden: {},
  show: {
    transition: { staggerChildren: 0.06, delayChildren: 0.04 },
  },
};

export const staggerItem: Variants = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: springSnappy },
};
