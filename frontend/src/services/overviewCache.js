import { fetchBriefing, fetchDiscovery, fetchWatches } from "./api.js";

/**
 * Module-level Overview cache so revisiting the page can paint immediately
 * and refresh in the background without a new dependency.
 */
let cache = {
  briefing: null,
  discovery: null,
  watches: { fired: [], active: [], cancelled: [] },
  fetchedAt: 0,
  error: "",
};

let inflight = null;

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
}

async function fetchAll() {
  const [briefing, discovery, board] = await Promise.all([
    fetchBriefing(),
    fetchDiscovery(8),
    fetchWatches(),
  ]);
  cache = {
    briefing,
    discovery,
    watches: {
      fired: board.fired || [],
      active: board.active || [],
      cancelled: board.cancelled || [],
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
  if (inflight) {
    const next = await inflight;
    return { ...next, fromCache: false };
  }
  inflight = fetchAll()
    .catch((err) => {
      cache = {
        ...cache,
        error: err.message || "Failed to load overview data.",
      };
      throw err;
    })
    .finally(() => {
      inflight = null;
    });
  const next = await inflight;
  return { ...next, fromCache: false };
}

/** Lightweight factory-date fetch that reuses overview cache when present. */
export async function loadFactoryDate() {
  if (cache.briefing?.factory_today) {
    return cache.briefing.factory_today;
  }
  try {
    const data = await loadOverviewData();
    return data.briefing?.factory_today || "";
  } catch {
    return cache.briefing?.factory_today || "";
  }
}
