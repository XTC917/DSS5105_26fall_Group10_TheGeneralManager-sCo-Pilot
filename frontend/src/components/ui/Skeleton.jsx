import { cx } from "./cx.js";

/**
 * Skeleton placeholder. Uses the shimmer utility from tokens.css and is
 * automatically neutralised under prefers-reduced-motion.
 */
export default function Skeleton({ width, height = 12, rounded = "sm", className, style }) {
  const radius = {
    none: "rounded-none",
    sm: "rounded-xs",
    md: "rounded-control",
    lg: "rounded-card",
    full: "rounded-full",
  }[rounded] || "rounded-xs";

  return (
    <span
      aria-hidden="true"
      className={cx("skeleton block", radius, className)}
      style={{ width, height, ...style }}
    />
  );
}

/** Convenience stack of skeleton lines. */
export function SkeletonLines({ lines = 3, className }) {
  return (
    <div className={cx("space-y-2", className)} aria-hidden="true">
      {Array.from({ length: lines }).map((_, index) => (
        <Skeleton
          key={index}
          height={10}
          style={{ width: index === lines - 1 ? "62%" : "100%" }}
        />
      ))}
    </div>
  );
}
