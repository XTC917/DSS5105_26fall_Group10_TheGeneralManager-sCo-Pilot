/** Tiny className joiner — avoids pulling in an extra dependency. */
export function cx(...parts) {
  return parts.filter(Boolean).join(" ");
}
