/** Demo-bundle types and the browser-side KPI engine (same definitions as the Python pipeline). */

export const NON_SALES = new Set(["canceled", "unavailable"]);
export interface Order {
  date: string; state: string | null; sellerState: string | null; category: string | null; status: string;
  itemsValue: number | null; freight: number | null; late: number | null; deliveryDays: number | null; delayDays: number | null; review: number | null;
}
export interface Filters { dateFrom?: string; dateTo?: string; states: string[]; categories: string[] }

export interface Bundle {
  meta: { data_source: string; generated_at: string; date_min: string; date_max: string; states: string[]; categories: string[]; gold_rows: Record<string, number>; bronze_rows: Record<string, number> };
  definitions: Record<string, string>;
  order_columns: string[];
  orders: (string | number | null)[][];
  expected: { overview_all: Overview; parity_filters: { states: string[]; categories: string[]; date_from: string; date_to: string }; overview_filtered: Overview };
  cohorts: { cohort_month: string; customers: number; repeat_rate_90d: number }[];
  segments: { segment: string; customers: number; avg_item_value: number; avg_recency_days: number }[];
  quality: { name: string; severity: string; violations: number; passed: boolean; description: string }[];
  forecast: Record<"orders" | "gmv", ForecastBlock>;
  model?: ModelBlock;
}
export interface ForecastBlock {
  series: { week: string; value: number }[];
  metrics: Record<string, { mae: number; wmape: number; bias: number; coverage_80?: number }>;
  best_baseline: string; horizon: number;
  backtest: { week_start: string; actual: number; naive: number; moving_average: number; holt: number; holt_lo80: number; holt_hi80: number }[];
  future: { week_start: string; forecast: number; lo80: number; hi80: number }[];
}
export interface ModelBlock {
  chosen: string; validation_pr_auc: Record<string, number>; threshold: number;
  test: Record<string, Record<string, number | null | Record<string, number>>>;
  calibration: { mean_predicted: number; observed_rate: number; n: number }[];
  segments: Record<string, { segment: string; n: number; late_rate: number; flag_rate: number; precision: number | null; recall: number | null }[]>;
  split: Record<string, { n: number; late_rate: number; from: string; to: string }>;
  features: string[]; excluded: string[]; scored: [number, number][];
  expected_threshold_table: Record<string, number>[];
}
export interface Overview {
  orders: number; gmv: number; aov: number | null; freight_share: number | null; late_rate: number | null; on_time_rate: number | null;
  avg_delivery_days: number | null; avg_review_score: number | null; cancellation_rate: number | null; delivered_scored: number; reviewed_orders: number;
}

export function toOrders(b: Bundle): Order[] {
  return b.orders.map((r) => ({
    date: r[0] as string, state: r[1] as string | null, sellerState: r[2] as string | null, category: r[3] as string | null, status: r[4] as string,
    itemsValue: r[5] as number | null, freight: r[6] as number | null, late: r[7] as number | null, deliveryDays: r[8] as number | null, delayDays: r[9] as number | null, review: r[10] as number | null,
  }));
}

export function applyFilters(orders: Order[], f: Filters): Order[] {
  return orders.filter((o) =>
    (!f.dateFrom || o.date >= f.dateFrom) && (!f.dateTo || o.date <= f.dateTo) &&
    (f.states.length === 0 || (o.state !== null && f.states.includes(o.state))) &&
    (f.categories.length === 0 || (o.category !== null && f.categories.includes(o.category))));
}

const avg = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);
const isSale = (o: Order) => !NON_SALES.has(o.status);

export function overview(orders: Order[]): Overview {
  const sales = orders.filter(isSale);
  const withItems = sales.filter((o) => o.itemsValue !== null);
  const gmv = sales.reduce((a, o) => a + (o.itemsValue ?? 0), 0);
  const freight = sales.reduce((a, o) => a + (o.freight ?? 0), 0);
  const scored = orders.filter((o) => o.late !== null);
  const late = scored.filter((o) => o.late === 1).length;
  const lateRate = scored.length ? late / scored.length : null;
  const reviews = orders.filter((o) => o.review !== null).map((o) => o.review as number);
  return {
    orders: sales.length, gmv, aov: withItems.length ? gmv / withItems.length : null, freight_share: gmv ? freight / gmv : null,
    late_rate: lateRate, on_time_rate: lateRate === null ? null : 1 - lateRate,
    avg_delivery_days: avg(orders.filter((o) => o.deliveryDays !== null).map((o) => o.deliveryDays as number)),
    avg_review_score: avg(reviews), cancellation_rate: orders.length ? orders.filter((o) => o.status === "canceled").length / orders.length : null,
    delivered_scored: scored.length, reviewed_orders: reviews.length,
  };
}

export function monthly(orders: Order[]) {
  const m = new Map<string, Order[]>();
  for (const o of orders) { const k = o.date.slice(0, 7); (m.get(k) ?? m.set(k, []).get(k)!).push(o); }
  return [...m.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([month, os]) => ({ month, ...overview(os) }));
}

export function groupBy(orders: Order[], key: "state" | "category") {
  const m = new Map<string, Order[]>();
  for (const o of orders) { const k = o[key]; if (k) (m.get(k) ?? m.set(k, []).get(k)!).push(o); }
  return [...m.entries()].map(([name, os]) => ({ name, ...overview(os) })).sort((a, b) => b.gmv - a.gmv);
}

export function routeLate(orders: Order[]) {
  const scored = orders.filter((o) => o.late !== null && o.sellerState !== null);
  return (["Same state", "Different state"] as const).map((route) => {
    const g = scored.filter((o) => (o.sellerState === o.state) === (route === "Same state"));
    return { route, n: g.length, lateRate: g.length ? g.filter((o) => o.late === 1).length / g.length : null };
  });
}

export function reviewByDelay(orders: Order[]) {
  const bucket = (d: number) => (d <= -7 ? "7+ days early" : d <= 0 ? "0-6 days early / on the day" : d <= 7 ? "1-7 days late" : "8+ days late");
  const names = ["7+ days early", "0-6 days early / on the day", "1-7 days late", "8+ days late"];
  return names.map((name) => {
    const g = orders.filter((o) => o.delayDays !== null && bucket(o.delayDays) === name && o.review !== null);
    return { name, n: g.length, avgReview: avg(g.map((o) => o.review as number)) };
  });
}

/** Python's round() is banker's rounding; match it so browser and pipeline agree on ties. */
export function roundHalfEven(x: number): number {
  const f = Math.floor(x), diff = x - f;
  if (Math.abs(diff - 0.5) < 1e-12) return f % 2 === 0 ? f : f + 1;
  return Math.round(x);
}

export function holdoutOutcome(scored: [number, number][], share: number) {
  if (!(share > 0 && share <= 1)) throw new Error("share must be in (0, 1]");
  const n = scored.length;
  const k = Math.max(1, roundHalfEven(n * share));
  const order = scored.map((s, i) => ({ risk: s[0], late: s[1], i })).sort((a, b) => b.risk - a.risk || a.i - b.i);
  const caught = order.slice(0, k).reduce((a, o) => a + o.late, 0);
  const lateTotal = scored.reduce((a, s) => a + s[1], 0);
  const base = n ? lateTotal / n : NaN;
  const precision = k ? caught / k : NaN;
  return { flagged: k, caught, lateTotal, n, precision, recall: lateTotal ? caught / lateTotal : NaN, baseRate: base, lift: base ? precision / base : NaN };
}

export interface Assumptions { successRate: number | null; costPerCase: number | null; valuePerRescue: number | null }

export function scenario(scored: [number, number][], share: number, a: Assumptions) {
  const ev = holdoutOutcome(scored, share);
  const avoided = a.successRate !== null ? ev.caught * a.successRate : null;
  const cost = a.costPerCase !== null ? ev.flagged * a.costPerCase : null;
  const net = avoided !== null && cost !== null && a.valuePerRescue !== null ? avoided * a.valuePerRescue - cost : null;
  const missing = [a.successRate === null && "rescue rate", a.costPerCase === null && "cost per case", a.valuePerRescue === null && "value per rescued order"].filter(Boolean) as string[];
  return { evidence: ev, avoided, cost, net, missing };
}
