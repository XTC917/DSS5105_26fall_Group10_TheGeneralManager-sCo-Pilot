import { fetchBriefing, fetchDiscovery, fetchWatches } from "./api.js";

/**
 * Module-level Overview cache so revisiting the page can paint immediately
 * and refresh in the background without a new dependency.
 */
let cache = {
  briefing: null,
  discovery: null,
  watches: { fired: [], active: [], cancelled: [], finished: [] },
  fetchedAt: 0,
  error: "",
};

let inflight = null;
let generation = 0;

export function peekOverviewCache() {
  return cache.briefing || cache.discovery ? { ...cache } : null;
}

export function invalidateOverviewCache() {
  cache = {
    briefing: null,
    discovery: null,
    watches: { fired: [], active: [], cancelled: [] },
    fetchedAt: 0,
    error: "",
  };
  inflight = null;
  generation += 1;
}

async function fetchAll(gen) {
  const [briefing, discovery, board] = await Promise.all([
    fetchBriefing(),
    fetchDiscovery(5, { all: true }),
    fetchWatches(),
  ]);
  if (gen !== generation) return null;
  cache = {
    briefing,
    discovery,
    watches: {
      asOf: board.as_of || "",
      fired: board.fired || [],
      active: board.active || [],
      cancelled: board.cancelled || [],
      finished: board.finished || [],
    },
    fetchedAt: Date.now(),
    error: "",
  };
  return { ...cache };
}

/**
 * @param {{ force?: boolean }} [options]
 * @returns {Promise<{ briefing: object|null, discovery: object|null, watches: object, fetchedAt: number, error: string, fromCache: boolean }>}
 */
export async function loadOverviewData({ force = false } = {}) {
  if (!force && cache.briefing && cache.discovery) {
    return { ...cache, fromCache: true };
  }
  if (force) {
    generation += 1;
    inflight = null;
  } else if (inflight) {
    const next = await inflight;
    return { ...(next || cache), fromCache: false };
  }
  const gen = generation;
  const run = fetchAll(gen)
    .catch((err) => {
      if (gen === generation) {
        cache = {
          ...cache,
          error: err.message || "Failed to load overview data.",
        };
      }
      throw err;
    })
    .finally(() => {
      if (inflight === run) inflight = null;
    });
  inflight = run;
  const next = await run;
  return { ...(next || cache), fromCache: false };
}

/** Lightweight factory-date fetch that reuses overview cache when present. */
export async function loadFactoryDate() {
  const cachedClock = cache.briefing?.clock_date || cache.briefing?.factory_today;
  if (cachedClock) return cachedClock;
  try {
    const data = await loadOverviewData();
    return data.briefing?.clock_date || data.briefing?.factory_today || "";
  } catch {
    return cache.briefing?.clock_date || cache.briefing?.factory_today || "";
  }
}
