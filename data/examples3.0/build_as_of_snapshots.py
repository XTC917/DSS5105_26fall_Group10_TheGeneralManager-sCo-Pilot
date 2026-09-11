"""Build as-of order snapshots for 2026-03-23 through 2026-04-01.

Snapshot rule: last_activity_date L on the 4/1 file is the day the order
*entered* its 4/1 stage. Days before L are previous stages or ORDERED.
v1 (old) is kept only for the comparison table.

    .venv/Scripts/python.exe data/examples/build_as_of_snapshots.py
"""

from __future__ import annotations

import csv
import hashlib
import random
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
EXAMPLES = DATA / "examples"
CLOSED_WEEKDAY = 6

STAGES = ("KNITTING", "ASSEMBLY", "WASHING", "PACKING")
ORDERED = "ORDERED"
ANCHOR_DATE = date(2026, 4, 1)
AS_OF_DATES = tuple(
    date(2026, 3, 23) + timedelta(days=i)
    for i in range((ANCHOR_DATE - date(2026, 3, 23)).days + 1)
)
QUEUE_DATES = AS_OF_DATES
ORDER_COLUMNS = [
    "order_id",
    "customer",
    "product",
    "category",
    "pieces",
    "order_date",
    "due_date",
    "status",
    "current_stage",
    "last_activity_date",
    "completed_date",
    "days_late",
]


def is_working_day(day: date) -> bool:
    return day.weekday() != CLOSED_WEEKDAY


def count_working_days(start: date, end: date) -> int:
    if end < start:
        return 0
    total = 0
    cursor = start
    while cursor <= end:
        if is_working_day(cursor):
            total += 1
        cursor += timedelta(days=1)
    return total


def working_day_list(start: date, end: date) -> list[date]:
    days: list[date] = []
    cursor = start
    while cursor <= end:
        if is_working_day(cursor):
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def last_working_on_or_before(d: date, start: date) -> date | None:
    cursor = d
    while cursor >= start:
        if is_working_day(cursor):
            return cursor
        cursor -= timedelta(days=1)
    return None


def previous_filled(d: date, start: date, painted: dict[date, str]) -> str | None:
    cursor = d
    while cursor >= start:
        if cursor in painted:
            return painted[cursor]
        cursor -= timedelta(days=1)
    return None


def last_day_in_stage(as_of: date, start: date, stage: str, painted: dict[date, str]) -> date | None:
    cursor = as_of
    while cursor >= start:
        if cursor in painted and painted[cursor] == stage:
            return cursor
        cursor -= timedelta(days=1)
    return None


def first_day_in_stage(start: date, as_of: date, stage: str, painted: dict[date, str]) -> date | None:
    """First painted day of this stage on or before as_of — the phase start."""
    cursor = start
    while cursor <= as_of:
        if painted.get(cursor) == stage:
            return cursor
        cursor += timedelta(days=1)
    return None


def service_dwell(pieces: int, median_th: float) -> int:
    return max(1, int(round(pieces / median_th)))


def paint_backward(
    order_date: date,
    anchor: date,
    path: tuple[str, ...],
    pieces: int,
    medians: dict[str, float],
) -> dict[date, str]:
    """Fill working days order_date…anchor from the end: current stage first."""
    work = working_day_list(order_date, anchor)
    if not work:
        return {}
    latest_first = list(reversed(work))
    painted: dict[date, str] = {}
    idx = 0
    for stage in reversed(path):
        n = service_dwell(pieces, medians[stage])
        for _ in range(n):
            if idx >= len(latest_first):
                break
            painted[latest_first[idx]] = stage
            idx += 1
    # Earlier leftover working days stay unpainted → ORDERED.
    return painted


# --- v1 (old): split full order_date→anchor window by 1/TH shares ---


def allocate_dwells_v1(total: int, stages: tuple[str, ...], weights: dict[str, float]) -> dict[str, int]:
    n = len(stages)
    if total <= 0:
        return {s: 0 for s in stages}
    if total < n:
        dwells = {s: 0 for s in stages}
        for i in range(total):
            dwells[stages[n - 1 - i]] += 1
        return dwells
    ws = [weights[s] for s in stages]
    z = sum(ws)
    ideal = [total * w / z for w in ws]
    floors = [int(x) for x in ideal]
    rem = total - sum(floors)
    order = sorted(range(n), key=lambda i: (ideal[i] - floors[i], i), reverse=True)
    for i in range(rem):
        floors[order[i]] += 1
    while min(floors) < 1:
        donor = max(range(n), key=lambda i: floors[i])
        recv = min(range(n), key=lambda i: floors[i])
        if floors[donor] <= 1:
            break
        floors[donor] -= 1
        floors[recv] += 1
    return dict(zip(stages, floors, strict=True))


def paint_forward_v1(work_days: list[date], stages: tuple[str, ...], dwells: dict[str, int]) -> dict[date, str]:
    painted: dict[date, str] = {}
    idx = 0
    for stage in stages:
        for _ in range(dwells[stage]):
            if idx >= len(work_days):
                break
            painted[work_days[idx]] = stage
            idx += 1
    while idx < len(work_days):
        painted[work_days[idx]] = stages[-1]
        idx += 1
    return painted


def fit_params(orders: pd.DataFrame, log: pd.DataFrame) -> tuple[dict[str, float], dict[str, float]]:
    work_log = log[log["date"].dt.weekday != 6]
    medians = {s: float(work_log.loc[work_log["stage"] == s, "pieces_completed"].median()) for s in STAGES}
    weights = {s: 1.0 / medians[s] for s in STAGES}
    return weights, medians


def emit_row(
    row: pd.Series,
    as_of: date,
    status: str,
    stage: str,
    last_activity: date | None,
    completed_out: date | None,
    source: str,
) -> dict[str, str]:
    due: date = row["due_date"].date()
    pieces = int(row["pieces"])
    order_date: date = row["order_date"].date()
    if last_activity is not None and last_activity > as_of:
        last_activity = last_working_on_or_before(as_of, order_date)
    if completed_out is not None and completed_out > as_of:
        completed_out = None
        status = "IN_PROGRESS"
    days_late = ""
    completed_s = ""
    if completed_out is not None:
        completed_s = completed_out.isoformat()
        days_late = str((completed_out - due).days)
    last_s = last_activity.isoformat() if last_activity is not None else ""
    return {
        "order_id": row["order_id"],
        "customer": row["customer"],
        "product": row["product"],
        "category": row["category"],
        "pieces": str(pieces),
        "order_date": order_date.isoformat(),
        "due_date": due.isoformat(),
        "status": status,
        "current_stage": stage,
        "last_activity_date": last_s,
        "completed_date": completed_s,
        "days_late": days_late,
        "snapshot_date": as_of.isoformat(),
        "stage_source": source,
        "stage_known": "Y",
        "last_activity_as_of": last_s,
    }


def emit_ordered(row: pd.Series, as_of: date) -> dict[str, str]:
    order_date: date = row["order_date"].date()
    return emit_row(row, as_of, "IN_PROGRESS", ORDERED, order_date, None, "ordered")


def emit_from_paint(
    row: pd.Series,
    as_of: date,
    order_date: date,
    painted: dict[date, str],
) -> dict[str, str]:
    stage = previous_filled(as_of, order_date, painted)
    if stage is None:
        return emit_ordered(row, as_of)
    last_act = first_day_in_stage(order_date, as_of, stage, painted)
    return emit_row(row, as_of, "IN_PROGRESS", stage, last_act, None, "imputed")


def _anchors(row: pd.Series, as_of: date) -> dict[str, str] | None | str:
    """Return emit dict, None if not yet ordered, or 'impute'."""
    order_date: date = row["order_date"].date()
    if order_date > as_of:
        return None
    stage_4_1 = row["current_stage"]
    last_l: date = row["last_activity_date"].date()
    completed = row["completed_date"]
    completed_d: date | None = completed.date() if pd.notna(completed) else None

    if completed_d is not None and completed_d <= as_of:
        return emit_row(row, as_of, "COMPLETE", "COMPLETE", completed_d, completed_d, "frozen")
    # L = day they entered the 4/1 stage. From that evening on, they stay there.
    if completed_d is None and as_of >= last_l:
        return emit_row(row, as_of, "IN_PROGRESS", stage_4_1, last_l, None, "anchored")
    return "impute"


def snapshot_row_v2(row: pd.Series, as_of: date, medians: dict[str, float]) -> dict[str, str] | None:
    hit = _anchors(row, as_of)
    if hit is None or isinstance(hit, dict):
        return hit

    order_date: date = row["order_date"].date()
    stage_4_1 = row["current_stage"]
    last_l: date = row["last_activity_date"].date()
    completed = row["completed_date"]
    completed_d: date | None = completed.date() if pd.notna(completed) else None
    pieces = int(row["pieces"])

    if completed_d is not None:
        # COMPLETE starts on completed_d; paint the four production stages before that.
        path = STAGES
        anchor = last_working_on_or_before(completed_d - timedelta(days=1), order_date)
        if anchor is None:
            return emit_ordered(row, as_of)
        painted = paint_backward(order_date, anchor, path, pieces, medians)
        return emit_from_paint(row, as_of, order_date, painted)

    # as_of < L: have not entered the 4/1 stage yet.
    prev_stages = STAGES[: STAGES.index(stage_4_1)]
    if not prev_stages:
        return emit_ordered(row, as_of)
    anchor = last_working_on_or_before(last_l - timedelta(days=1), order_date)
    if anchor is None:
        return emit_ordered(row, as_of)
    painted = paint_backward(order_date, anchor, prev_stages, pieces, medians)
    return emit_from_paint(row, as_of, order_date, painted)


def snapshot_row_v1(row: pd.Series, as_of: date, weights: dict[str, float]) -> dict[str, str] | None:
    hit = _anchors(row, as_of)
    if hit is None or isinstance(hit, dict):
        return hit

    order_date: date = row["order_date"].date()
    stage_4_1 = row["current_stage"]
    last_l: date = row["last_activity_date"].date()
    completed = row["completed_date"]
    completed_d: date | None = completed.date() if pd.notna(completed) else None

    if completed_d is not None:
        work = working_day_list(order_date, completed_d - timedelta(days=1))
        dwells = allocate_dwells_v1(len(work), STAGES, weights)
        painted = paint_forward_v1(work, STAGES, dwells)
        stage = previous_filled(as_of, order_date, painted) or "KNITTING"
        last_act = last_day_in_stage(as_of, order_date, stage, painted)
        return emit_row(row, as_of, "IN_PROGRESS", stage, last_act, None, "imputed")

    path = STAGES[: STAGES.index(stage_4_1) + 1]
    work = working_day_list(order_date, last_l)
    dwells = allocate_dwells_v1(len(work), path, weights)
    painted = paint_forward_v1(work, path, dwells)
    painted[last_l] = stage_4_1
    stage = previous_filled(as_of, order_date, painted) or path[0]
    last_act = last_day_in_stage(as_of, order_date, stage, painted)
    return emit_row(row, as_of, "IN_PROGRESS", stage, last_act, None, "imputed")


def workshop_rng(workshop_id: str) -> random.Random:
    seed = int(hashlib.md5(f"queue-v1|{workshop_id}".encode()).hexdigest()[:8], 16)
    return random.Random(seed)


def markov_prev_queue(q_today: float, rng: random.Random) -> float:
    """If today is q, yesterday is 0 (new job arrived today) or q+1 (same pile, not yet finished)."""
    q_today = float(q_today)
    if rng.random() < 0.5:
        return 0.0
    if q_today <= 0:
        return 1.0
    return q_today + 1.0


def backward_workshop_queues(
    workshops: pd.DataFrame, days: tuple[date, ...]
) -> dict[date, dict[str, float]]:
    last = max(days)
    queues: dict[date, dict[str, float]] = {
        last: {
            str(row["workshop_id"]): float(row["current_queue_days"] or 0)
            for _, row in workshops.iterrows()
        }
    }
    rngs = {wid: workshop_rng(wid) for wid in queues[last]}
    for d in sorted(days, reverse=True):
        if d == last or d.weekday() == CLOSED_WEEKDAY:
            continue
        nxt = d + timedelta(days=1)
        while nxt not in queues:
            nxt += timedelta(days=1)
        src = queues[nxt]
        queues[d] = {wid: markov_prev_queue(q, rngs[wid]) for wid, q in src.items()}
    for d in days:
        if d.weekday() == CLOSED_WEEKDAY:
            saturday = d - timedelta(days=1)
            queues[d] = dict(queues[saturday])
    return queues


def write_orders_csv(path: Path, order_rows: list[dict[str, str]]) -> Path:
    """Write orders.csv; if the target is locked, leave a .new.csv beside it."""
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ORDER_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in sorted(order_rows, key=lambda r: r["order_id"]):
            writer.writerow(row)
    for _ in range(8):
        try:
            tmp.replace(path)
            return path
        except PermissionError:
            time.sleep(0.4)
    alt = path.with_name("orders.new.csv")
    alt.write_bytes(tmp.read_bytes())
    tmp.unlink(missing_ok=True)
    print(f"  WARN locked {path.name}, wrote {alt.name} instead")
    return alt


def write_day(
    as_of: date,
    order_rows: list[dict[str, str]],
    log: pd.DataFrame,
    master_by_id: dict[str, pd.Series],
    workshops: pd.DataFrame,
    queues_today: dict[str, float],
    queues_apr1: dict[str, float],
) -> None:
    folder = EXAMPLES / as_of.isoformat()
    folder.mkdir(parents=True, exist_ok=True)

    write_orders_csv(folder / "orders.csv", order_rows)

    snap_path = folder / "order_daily_snapshot.csv"
    if snap_path.exists():
        snap_path.unlink()

    cutoff = as_of - timedelta(days=1)
    day_slice = log[log["date"].dt.date <= cutoff][["date", "stage", "pieces_completed"]].copy()
    day_slice["date"] = day_slice["date"].dt.strftime("%Y-%m-%d")
    log_empty = day_slice.empty
    day_slice.to_csv(folder / "production_log.csv", index=False)

    shop = workshops.copy()
    shop["current_queue_days"] = shop["workshop_id"].map(lambda w: queues_today[str(w)])
    shop.to_csv(folder / "workshops.csv", index=False)

    counts: dict[str, int] = {}
    for row in order_rows:
        counts[row["stage_source"]] = counts.get(row["stage_source"], 0) + 1
    write_day_readme(
        folder,
        as_of,
        order_rows,
        master_by_id,
        counts,
        log_empty=log_empty,
        log_cutoff=cutoff,
        queues_today=queues_today,
        queues_apr1=queues_apr1,
    )
    bad = [
        r["order_id"]
        for r in order_rows
        if r["last_activity_date"] and r["last_activity_date"] > as_of.isoformat()
    ]
    if bad:
        raise ValueError(f"{as_of}: last_activity after snapshot {bad}")
    print(f"{as_of.isoformat()}: {len(order_rows)} orders {counts} log<= {cutoff} -> {folder}")


def write_day_readme(
    folder: Path,
    as_of: date,
    order_rows: list[dict[str, str]],
    master_by_id: dict[str, pd.Series],
    counts: dict[str, int],
    log_empty: bool = False,
    log_cutoff: date | None = None,
    queues_today: dict[str, float] | None = None,
    queues_apr1: dict[str, float] | None = None,
) -> None:
    rows = sorted(order_rows, key=lambda r: r["order_id"])
    pipeline: dict[str, int] = {}
    for row in rows:
        key = f"{row['status']} / {row['current_stage']}"
        pipeline[key] = pipeline.get(key, 0) + 1

    missing = sorted(
        oid for oid, master in master_by_id.items() if master["order_date"].date() > as_of
    )
    cutoff = log_cutoff or (as_of - timedelta(days=1))
    log_note = (
        f"产量 log **看不到当天**：截止 {cutoff.isoformat()}（含）。"
        + (" 源文件在该截止日前无行。" if log_empty else "")
    )

    lines = [
        f"# {as_of.isoformat()} 当天订单说明",
        "",
        "对照 4/1 的 `orders.csv`。倒推规则：L 为进入 4/1 当前站的日期，见 [backward_stage_imputation.md](../backward_stage_imputation.md)。",
        "",
        f"本日共 **{len(rows)}** 单。"
        + (f" 还没下单、不在表里：{', '.join(missing)}。" if missing else ""),
        "",
        "## 当天进度（结束时）",
        "",
        "| 状态 | 单数 |",
        "|---|---|",
    ]
    for key in sorted(pipeline):
        lines.append(f"| {key} | {pipeline[key]} |")

    lines += [
        "",
        "## 未完工订单：4/1 真实工序 → 本日（含 ORDERED）",
        "",
        "`last_activity_date`（L）= 进入 4/1 那一站的日期。`D ≥ L` 停在该站；尚未进织则 `status=IN_PROGRESS`、`current_stage=ORDERED`，`last_activity_date` = 下单日。",
        "",
        "| order_id | 4/1 真实工序 | 本日 | 说明 |",
        "|---|---|---|---|",
    ]
    open_rows = [r for r in rows if r["status"] == "IN_PROGRESS"]
    for row in open_rows:
        m = master_by_id[row["order_id"]]
        apr1 = m["current_stage"]
        today = row["current_stage"]
        src = row["stage_source"]
        entered = m["last_activity_date"].date().isoformat()
        if today == ORDERED:
            note = f"已下单未开工（4/1 的 {apr1} 从 {entered} 才开始；L=下单日）"
        elif src == "imputed":
            note = "倒推上一站（尚未到 4/1 那一站）"
        else:
            note = f"已于 {entered} 进入 {apr1}"
        lines.append(f"| {row['order_id']} | {apr1} | {today} | {note} |")
    if not open_rows:
        lines.append("| （无） | | | |")
    lines += [
        "",
        log_note,
        "",
        "## 外发车间 current_queue_days（马尔可夫假定）",
        "",
        "与本厂订单无关。4/1 为真值；往前每一工作日：要么是 **当天新单进来前队列为 0**，要么是 **同一堆积压再多 1 天**。周日抄周六。",
        "",
        "| workshop_id | 本日 queue_days | 4/1 真值 |",
        "|---|---|---|",
    ]
    if queues_today and queues_apr1:
        for wid in sorted(queues_today, key=lambda x: int(x[1:]) if x[1:].isdigit() else x):
            lines.append(f"| {wid} | {queues_today[wid]:g} | {queues_apr1[wid]:g} |")
    lines += [""]
    (folder / "README.md").write_text("\n".join(lines), encoding="utf-8")


def abbrev(built: dict[str, str] | None) -> str:
    if built is None:
        return "—"
    if built["status"] == "COMPLETE":
        return "DONE"
    if built["current_stage"] == ORDERED:
        return "O"
    return {
        "KNITTING": "K",
        "ASSEMBLY": "A",
        "WASHING": "W",
        "PACKING": "P",
    }[built["current_stage"]]


def write_comparison(
    orders: pd.DataFrame,
    weights: dict[str, float],
    medians: dict[str, float],
) -> None:
    days = AS_OF_DATES
    headers = [d.isoformat()[5:] for d in days]
    ever_imp: list[str] = []
    for _, row in orders.iterrows():
        for d in days:
            b = snapshot_row_v2(row, d, medians)
            if b and b["stage_source"] in ("imputed", "ordered"):
                ever_imp.append(row["order_id"])
                break

    lines = [
        "# 倒推 v1 vs v2（2026-03-23 至 2026-04-01）",
        "",
        "v2：L = 进入 4/1 当前站的日期。`D < L` 为上一站或 ORDERED（O，status 仍是 IN_PROGRESS）。v1 仍按旧规则把织单从下单日起写成 KNITTING。",
        "",
        "## 规则差别",
        "",
        "| | v1（旧） | v2（现用） |",
        "|---|---|---|",
        "| L 的含义 | 最后一次干活，当前站可在 L 之前就开始 | **进入 4/1 那一站的日期**；当天结束才在那一站 |",
        "| 织单 D < L | 全程 KNITTING | **IN_PROGRESS / ORDERED**，last_activity = 下单日 |",
        "| 其它站 D < L | 当前站占满窗口末尾 | 填 L 之前各前序站的加工日，更早为 ORDERED |",
        "",
        "`dwell_s = max(1, round(pieces / median_working_day_output_s))` 只用于 L 之前的前序站。",
        "",
        f"工作日产量中位数：KNITTING {medians['KNITTING']:.0f}，ASSEMBLY {medians['ASSEMBLY']:.0f}，"
        f"WASHING {medians['WASHING']:.0f}，PACKING {medians['PACKING']:.0f}。",
        "",
        "## 路径链（O/K/A/W/P/DONE）",
        "",
        "旧 = v1，新 = v2。日期为 03-23 … 04-01。",
        "",
        "| order_id | 4/1 | L 或完成日 | 旧 23–4/1 | 新 23–4/1 |",
        "|---|---|---|---|---|",
    ]

    mix_old: dict[date, dict[str, int]] = {d: {} for d in days}
    mix_new: dict[date, dict[str, int]] = {d: {} for d in days}

    for _, row in orders.iterrows():
        oid = row["order_id"]
        for d in days:
            o = snapshot_row_v1(row, d, weights)
            n = snapshot_row_v2(row, d, medians)
            if o:
                mix_old[d][o["current_stage"]] = mix_old[d].get(o["current_stage"], 0) + 1
            if n:
                mix_new[d][n["current_stage"]] = mix_new[d].get(n["current_stage"], 0) + 1
        if oid not in ever_imp:
            continue
        old_path = " ".join(abbrev(snapshot_row_v1(row, d, weights)) for d in days)
        new_path = " ".join(abbrev(snapshot_row_v2(row, d, medians)) for d in days)
        stage_41 = row["current_stage"] if row["status"] != "COMPLETE" else "COMPLETE"
        completed = row["completed_date"]
        anchor = (
            str(completed.date())
            if pd.notna(completed)
            else str(row["last_activity_date"].date())
        )
        lines.append(f"| {oid} | {stage_41} | {anchor} | `{old_path}` | `{new_path}` |")

    lines += [
        "",
        f"日期顺序：`{' '.join(headers)}`",
        "",
        "## 全厂在制结构（全部订单，含冻结）",
        "",
        "| 日期 | 旧 COMPLETE / K / A / W / P | 新 COMPLETE / O / K / A / W / P |",
        "|---|---|---|",
    ]
    for d in days:
        def pack(mix: dict[str, int], with_n: bool = False) -> str:
            c = mix.get("COMPLETE", 0)
            n = mix.get(ORDERED, 0)
            k = mix.get("KNITTING", 0)
            a = mix.get("ASSEMBLY", 0)
            w = mix.get("WASHING", 0)
            p = mix.get("PACKING", 0)
            if with_n:
                return f"{c} / {n} / {k} / {a} / {w} / {p}"
            return f"{c} / {k} / {a} / {w} / {p}"

        lines.append(f"| {d.isoformat()} | {pack(mix_old[d])} | {pack(mix_new[d], with_n=True)} |")

    lines += [
        "",
        "O = ORDERED（已下单未开工）。4/1 两版都应等于源 `orders.csv`（无 ORDERED）。",
        "",
    ]
    path = EXAMPLES / "v1_vs_v2_comparison.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", path)


def write_stage_summary(entries: list[dict[str, str]]) -> None:
    """One row per stage occupancy: last_activity_date is when that stage started.

    To read day D: for that order_id take the row with the greatest
    last_activity_date that is still <= D.
    """
    fields = ["order_id", "status", "stage", "last_activity_date"]
    seen: set[tuple[str, str, str, str]] = set()
    unique: list[dict[str, str]] = []
    for row in entries:
        key = (row["order_id"], row["status"], row["stage"], row["last_activity_date"])
        if key in seen:
            continue
        seen.add(key)
        unique.append({k: row[k] for k in fields})
    unique.sort(key=lambda r: (r["order_id"], r["last_activity_date"]))
    path = EXAMPLES / "order_stage_summary.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in unique:
            writer.writerow(row)
    print("wrote", path, len(unique), "rows")


def load_snapshot_orders(as_of: date) -> pd.DataFrame:
    folder = EXAMPLES / as_of.isoformat()
    alt = folder / "orders.new.csv"
    path = alt if alt.exists() else folder / "orders.csv"
    return pd.read_csv(path)


def audit(master: pd.DataFrame, source_log: pd.DataFrame) -> list[str]:
    issues: list[str] = []
    rank = {s: i for i, s in enumerate(STAGES)}
    rank[ORDERED] = -1
    rank["COMPLETE"] = 4
    live_stages = set(STAGES) | {ORDERED}

    for as_of in AS_OF_DATES:
        folder = EXAMPLES / as_of.isoformat()
        orders = load_snapshot_orders(as_of)
        log = pd.read_csv(folder / "production_log.csv")
        shops = pd.read_csv(folder / "workshops.csv")
        cutoff = as_of - timedelta(days=1)

        if (orders["order_date"] > as_of.isoformat()).any():
            issues.append(f"{as_of}: order_date after as_of")
        late_act = orders[orders["last_activity_date"].fillna("") > as_of.isoformat()]
        if len(late_act):
            issues.append(f"{as_of}: last_activity after as_of {list(late_act.order_id)}")
        done = orders[orders["status"] == "COMPLETE"]
        if done["completed_date"].isna().any() or (done["completed_date"] == "").any():
            issues.append(f"{as_of}: COMPLETE missing completed_date")
        if (done["completed_date"].fillna("") > as_of.isoformat()).any():
            issues.append(f"{as_of}: completed_date after as_of")
        ip = orders[orders["status"] == "IN_PROGRESS"]
        filled = ip[ip["completed_date"].notna() & (ip["completed_date"].astype(str) != "nan") & (ip["completed_date"].astype(str) != "")]
        if len(filled):
            issues.append(f"{as_of}: IN_PROGRESS has completed_date {list(filled.order_id)}")

        pending = orders[orders["current_stage"] == ORDERED]
        if len(pending) and (pending["status"] != "IN_PROGRESS").any():
            issues.append(f"{as_of}: ORDERED must be IN_PROGRESS")
        for _, r in pending.iterrows():
            last = str(r["last_activity_date"])[:10]
            od = str(r["order_date"])[:10]
            if last != od:
                issues.append(f"{as_of} {r['order_id']}: ORDERED last_activity {last} != order_date {od}")

        should_exist = master[master["order_date"].dt.date <= as_of]
        extra = set(orders.order_id) - set(should_exist.order_id)
        missing = set(should_exist.order_id) - set(orders.order_id)
        if extra:
            issues.append(f"{as_of}: extra orders {sorted(extra)}")
        if missing:
            issues.append(f"{as_of}: missing orders {sorted(missing)}")

        merged = orders.merge(master, on="order_id", suffixes=("", "_m"))
        for _, r in merged.iterrows():
            cd = r["completed_date_m"]
            completed_m = cd.date() if pd.notna(cd) else None
            last_m = r["last_activity_date_m"].date()
            stage_m = r["current_stage_m"]
            if completed_m is not None and completed_m <= as_of:
                if r["status"] != "COMPLETE" or r["current_stage"] != "COMPLETE":
                    issues.append(f"{as_of} {r['order_id']}: should be frozen COMPLETE")
            if completed_m is not None and completed_m > as_of and r["status"] == "COMPLETE":
                issues.append(f"{as_of} {r['order_id']}: COMPLETE before real completed_date")
            if r["status"] == "IN_PROGRESS" and r["current_stage"] not in live_stages:
                issues.append(f"{as_of} {r['order_id']}: bad stage {r['current_stage']}")
            if str(r["customer"]) != str(r["customer_m"]) or int(r["pieces"]) != int(r["pieces_m"]):
                issues.append(f"{as_of} {r['order_id']}: identity drifted")
            if completed_m is None:
                if as_of >= last_m:
                    if r["status"] != "IN_PROGRESS" or r["current_stage"] != stage_m:
                        issues.append(
                            f"{as_of} {r['order_id']}: D>=L should be IN_PROGRESS/{stage_m}, got {r['status']}/{r['current_stage']}"
                        )
                    snap_l = str(r["last_activity_date"])[:10]
                    if snap_l != last_m.isoformat():
                        issues.append(
                            f"{as_of} {r['order_id']}: last_activity should stay L={last_m}, got {snap_l}"
                        )
                elif stage_m == "KNITTING" and (
                    r["status"] != "IN_PROGRESS"
                    or r["current_stage"] != ORDERED
                    or str(r["last_activity_date"])[:10] != str(r["order_date"])[:10]
                ):
                    issues.append(
                        f"{as_of} {r['order_id']}: knitting D<L should be IN_PROGRESS/ORDERED "
                        f"last=order_date, got {r['status']}/{r['current_stage']}/{r['last_activity_date']}"
                    )

        if as_of == ANCHOR_DATE and (
            (orders["current_stage"] == ORDERED).any() or (orders["status"] == "NOT_STARTED").any()
        ):
            issues.append("4/1 must not contain ORDERED")

        if len(log):
            mx = pd.to_datetime(log["date"]).dt.date.max()
            if mx > cutoff:
                issues.append(f"{as_of}: log max {mx} > cutoff {cutoff}")
            if (pd.to_datetime(log["date"]).dt.date == as_of).any():
                issues.append(f"{as_of}: log contains today")
            src = source_log[source_log["date"].dt.date <= cutoff]
            if len(src) != len(log):
                issues.append(f"{as_of}: log rows {len(log)} != source through cutoff {len(src)}")

        if as_of.weekday() == CLOSED_WEEKDAY:
            sat = as_of - timedelta(days=1)
            prev = load_snapshot_orders(sat)
            m = orders.merge(prev, on="order_id", suffixes=("_sun", "_sat"))
            for _, r in m.iterrows():
                if r["status_sun"] == "IN_PROGRESS" and (
                    r["status_sat"] != r["status_sun"] or r["current_stage_sat"] != r["current_stage_sun"]
                ):
                    issues.append(
                        f"{as_of} {r['order_id']}: Sunday in-progress != Saturday "
                        f"{r['current_stage_sat']} -> {r['current_stage_sun']}"
                    )
            ps = pd.read_csv(EXAMPLES / sat.isoformat() / "workshops.csv")
            if not (shops.current_queue_days.values == ps.current_queue_days.values).all():
                issues.append(f"{as_of}: Sunday workshop queue != Saturday")

    by_id: dict[str, list[tuple[date, str, str]]] = {}
    for as_of in AS_OF_DATES:
        orders = load_snapshot_orders(as_of)
        for _, r in orders.iterrows():
            by_id.setdefault(r["order_id"], []).append((as_of, r["status"], r["current_stage"]))
    for oid, seq in by_id.items():
        seq = sorted(seq)
        for (d0, st0, s0), (d1, st1, s1) in zip(seq, seq[1:]):
            if (d1 - d0).days != 1:
                continue
            r0 = rank.get(s0 if st0 != "COMPLETE" else "COMPLETE", -9)
            r1 = rank.get(s1 if st1 != "COMPLETE" else "COMPLETE", -9)
            if r1 < r0:
                issues.append(f"{oid}: stage went backward {d0} {s0} -> {d1} {s1}")
            if r1 - r0 > 2:
                issues.append(f"{oid}: stage skipped {d0} {s0} -> {d1} {s1}")

    return issues


def main() -> None:
    orders = pd.read_csv(
        DATA / "orders.csv",
        parse_dates=["order_date", "due_date", "last_activity_date", "completed_date"],
    )
    log = pd.read_csv(DATA / "production_log.csv", parse_dates=["date"])
    workshops = pd.read_csv(DATA / "workshops.csv")
    queue_by_day = backward_workshop_queues(workshops, QUEUE_DATES)
    queues_apr1 = queue_by_day[ANCHOR_DATE]
    master_by_id = {row["order_id"]: row for _, row in orders.iterrows()}
    weights, medians = fit_params(orders, log)
    print("v2 service dwell = round(pieces / median TH), min 1 working day")
    for s in STAGES:
        print(f"  {s} median {medians[s]:.0f}")

    summary: list[dict[str, str]] = []
    for as_of in AS_OF_DATES:
        rows = []
        for _, row in orders.iterrows():
            built = snapshot_row_v2(row, as_of, medians)
            if built is not None:
                rows.append(built)
                summary.append(
                    {
                        "snapshot_date": as_of.isoformat(),
                        "order_id": built["order_id"],
                        "status": built["status"],
                        "stage": built["current_stage"],
                        "last_activity_date": built["last_activity_date"],
                    }
                )
        write_day(
            as_of,
            rows,
            log,
            master_by_id,
            workshops,
            queue_by_day[as_of],
            queues_apr1,
        )
    write_stage_summary(summary)

    for as_of in AS_OF_DATES:
        folder = EXAMPLES / as_of.isoformat()
        alt = folder / "orders.new.csv"
        dest = folder / "orders.csv"
        if alt.exists():
            try:
                alt.replace(dest)
                print(f"promoted {alt} -> orders.csv")
            except PermissionError:
                print(f"STILL LOCKED {dest}; close it and rename {alt.name}")

    issues = audit(orders, log)
    if issues:
        print("AUDIT ISSUES", len(issues))
        for line in issues:
            print(" -", line)
    else:
        print("AUDIT OK: no logic issues found for 2026-03-23 .. 2026-04-01")

    write_comparison(orders, weights, medians)


if __name__ == "__main__":
    main()
