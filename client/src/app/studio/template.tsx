"use client";

import { motion } from "motion/react";
import type { ReactNode } from "react";

/** Fades each Studio section in on navigation between routes. */
export default function StudioTemplate({ children }: { children: ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </motion.div>
  );
}
