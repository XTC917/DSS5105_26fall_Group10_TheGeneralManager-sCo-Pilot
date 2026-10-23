export function filterOrders(orders, filter = "ALL", stage = null) {
  return orders.filter((row) => {
    if (stage && row.current_stage !== stage) return false;
    if (filter === "ALL") return true;
    if (filter === "STALLED") return (row.flags || []).includes("STALLED");
    if (filter === "SOON") return ["TODAY", "TWO_DAYS"].includes(row.bucket);
    return row.bucket === filter;
  });
}

export function deadlineText(days) {
  if (days == null) return "Due date unavailable";
  if (days < 0) return `Overdue by ${Math.abs(days)} ${days === -1 ? "day" : "days"}`;
  if (days <= 1) return "Due today";
  return `Due in ${days} days`;
}
