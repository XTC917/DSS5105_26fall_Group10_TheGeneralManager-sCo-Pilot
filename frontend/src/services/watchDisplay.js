function triggerDay(item) {
  return String(item?.fired_as_of || item?.as_of || item?.check_date || "").slice(0, 10);
}

/** Same-day fires stay alerts. Later days are done history. Earlier days stay watching. */
export function partitionWatches(watches = {}) {
  const today = String(watches.asOf || "").slice(0, 10);
  const triggered = [];
  const done = [];
  const watching = [...(watches.active || [])];
  for (const item of watches.fired || []) {
    const day = triggerDay(item);
    if (today && day && day < today) done.push(item);
    else if (today && day && day > today) watching.push(item);
    else triggered.push(item);
  }
  return {
    triggered,
    watching,
    done,
    cancelled: watches.cancelled || [],
  };
}
