/** Guided analysis of an uploaded table: roles, aggregates, findings, transparent baselines. */
import { ColumnProfile, DatasetProfile, DateOrder, isMissing, parseDate } from "./profile";

export interface Roles { date?: string; metric?: string; category?: string }
export type Grain = "day" | "week" | "month";

export interface SeriesPoint { period: string; value: number; count: number }
export interface Finding { title: string; text: string; basis: string }

export interface BaselineResult {
  periods: number;
  holdout: number;
  rows: { period: string; actual: number; naive: number; movingAverage: number; trend: number }[];
  mae: { naive: number; movingAverage: number; trend: number };
  best: "naive" | "movingAverage" | "trend";
  note: string;
}

export interface Analysis {
  roles: Roles;
  usedRows: number;
  skippedRows: number; // rows lacking a valid date or metric; never silently dropped, always counted
  total: number;
  mean: number;
  grain?: Grain;
  series: SeriesPoint[];
  categories: { name: string; value: number; share: number; count: number }[];
  findings: Finding[];
  baseline?: BaselineResult | { unavailable: string };
}

const NUM = /^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$/;

export function suggestRoles(profile: DatasetProfile): Roles {
  const cols = profile.columns;
  const date = cols.find((c) => c.type === "date")?.name;
  const nums = cols.filter((c) => c.type === "number" && c.numeric && !(c.distinct === profile.rows && /id$/i.test(c.name)));
  const metric = (nums.find((c) => /(amount|revenue|sales|total|price|value|spend|cost|qty|quantity)/i.test(c.name)) ?? nums[0])?.name;
  const cats = cols.filter((c) => c.type === "category" && c.distinct > 1);
  const category = (cats.find((c) => /(category|product|country|region|state|segment|type|channel)/i.test(c.name)) ?? cats[0])?.name;
  return { date, metric, category };
}

const pad = (n: number) => String(n).padStart(2, "0");
function periodKey(t: number, grain: Grain): string {
  const d = new Date(t);
  if (grain === "month") return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}`;
  if (grain === "day") return d.toISOString().slice(0, 10);
  const monday = new Date(t - ((d.getUTCDay() + 6) % 7) * 86400000);
  return monday.toISOString().slice(0, 10);
}

export function chooseGrain(minT: number, maxT: number): Grain {
  const days = (maxT - minT) / 86400000;
  if (days >= 365) return "month";
  if (days >= 90) return "week";
  return "day";
}

const sum = (xs: number[]) => xs.reduce((a, b) => a + b, 0);
const pct = (x: number) => `${(x * 100).toFixed(1)}%`;
const fmt = (x: number) => Math.abs(x) >= 1000 ? x.toLocaleString("en-US", { maximumFractionDigits: 0 }) : x.toLocaleString("en-US", { maximumFractionDigits: 2 });

export function baselines(series: SeriesPoint[]): BaselineResult | { unavailable: string } {
  const n = series.length;
  if (n < 20) return { unavailable: `Only ${n} complete periods; at least 20 are needed for a holdout comparison, so no baseline forecast is shown.` };
  const holdout = Math.min(6, Math.floor(n / 4));
  const train = series.slice(0, n - holdout).map((p) => p.value);
  const test = series.slice(n - holdout);
  const ma = sum(train.slice(-4)) / 4;
  const xs = train.map((_, i) => i);
  const mx = sum(xs) / xs.length, my = sum(train) / train.length;
  const slope = sum(xs.map((x, i) => (x - mx) * (train[i] - my))) / sum(xs.map((x) => (x - mx) ** 2));
  const rows = test.map((p, k) => ({
    period: p.period, actual: p.value, naive: train[train.length - 1], movingAverage: ma, trend: my + slope * (train.length + k - mx),
  }));
  const mae = (key: "naive" | "movingAverage" | "trend") => sum(rows.map((r) => Math.abs(r.actual - r[key]))) / rows.length;
  const m = { naive: mae("naive"), movingAverage: mae("movingAverage"), trend: mae("trend") };
  const best = (Object.keys(m) as (keyof typeof m)[]).reduce((a, b) => (m[a] <= m[b] ? a : b));
  return { periods: n, holdout, rows, mae: m, best, note: "Simple baselines fitted on earlier periods only and scored on the last periods. No interval is computed and none of these is a promise about the future." };
}

export function analyze(headers: string[], rows: string[][], profile: DatasetProfile, roles: Roles): Analysis {
  const col = (name?: string): ColumnProfile | undefined => profile.columns.find((c) => c.name === name);
  const dateCol = col(roles.date), metricCol = col(roles.metric), catCol = col(roles.category);
  const order: DateOrder | null = dateCol?.date?.order ?? null;
  const parseOrder = order === "dmy" ? "dmy" : "mdy";
  const tmp: { t: number | null; v: number | null; c: string | null }[] = rows.map((r) => {
    const rawV = metricCol ? r[metricCol.index]?.trim() : undefined;
    const rawD = dateCol ? r[dateCol.index] : undefined;
    const rawC = catCol ? r[catCol.index] : undefined;
    return {
      t: rawD !== undefined && !isMissing(rawD) ? parseDate(rawD, parseOrder) : null,
      v: rawV !== undefined && NUM.test(rawV) ? Number(rawV) : null,
      c: rawC !== undefined && !isMissing(rawC) ? rawC.trim() : null,
    };
  });
  const need = (x: (typeof tmp)[number]) => (!metricCol || x.v !== null) && (!dateCol || x.t !== null);
  const used = tmp.filter(need);
  const values = used.map((x) => x.v ?? 0);
  const total = metricCol ? sum(values) : used.length;
  const findings: Finding[] = [];
  const out: Analysis = { roles, usedRows: used.length, skippedRows: rows.length - used.length, total, mean: used.length ? total / used.length : 0, series: [], categories: [], findings };
  const label = roles.metric ?? "rows";

  if (used.length === 0) {
    findings.push({ title: "Nothing to analyse", text: "No row has both a valid date and a numeric metric under the chosen roles.", basis: "role mapping" });
    return out;
  }
  if (out.skippedRows > 0) findings.push({ title: "Rows excluded from this analysis", text: `${out.skippedRows} of ${rows.length} rows lack a valid ${[dateCol && "date", metricCol && "numeric metric"].filter(Boolean).join(" or ")} and are not counted below. They remain in your file.`, basis: "role mapping" });

  if (dateCol) {
    const ts = used.map((x) => x.t as number);
    const grain = chooseGrain(Math.min(...ts), Math.max(...ts));
    out.grain = grain;
    const buckets = new Map<string, SeriesPoint>();
    for (const x of used) {
      const key = periodKey(x.t as number, grain);
      const p = buckets.get(key) ?? { period: key, value: 0, count: 0 };
      p.value += metricCol ? (x.v as number) : 1;
      p.count++;
      buckets.set(key, p);
    }
    const all = [...buckets.values()].sort((a, b) => a.period.localeCompare(b.period));
    // The first and last period are usually partial; they are shown but excluded from baselines and growth.
    out.series = all;
    const complete = all.length > 2 ? all.slice(1, -1) : all;
    if (complete.length >= 2) {
      const peak = complete.reduce((a, b) => (b.value > a.value ? b : a));
      findings.push({ title: "Peak period", text: `${peak.period} is the highest complete ${grain} at ${fmt(peak.value)} (${label}).`, basis: `${complete.length} complete ${grain}s` });
      const last = complete[complete.length - 1], prev = complete[complete.length - 2];
      if (prev.value !== 0) findings.push({ title: "Latest complete period vs the one before", text: `${last.period}: ${fmt(last.value)} vs ${prev.period}: ${fmt(prev.value)} (${pct(last.value / prev.value - 1)}). One change between two periods is not a trend.`, basis: "two periods" });
    }
    out.baseline = baselines(complete);
  }
  if (catCol) {
    const agg = new Map<string, { value: number; count: number }>();
    used.forEach((x) => {
      const key = x.c ?? "(missing)";
      const a = agg.get(key) ?? { value: 0, count: 0 };
      a.value += metricCol ? (x.v as number) : 1;
      a.count++;
      agg.set(key, a);
    });
    const all = [...agg.entries()].map(([name, a]) => ({ name, ...a })).sort((p, q) => q.value - p.value);
    const grand = sum(all.map((a) => a.value));
    out.categories = all.slice(0, 15).map((a) => ({ ...a, share: grand ? a.value / grand : 0 }));
    const top3 = all.slice(0, 3);
    if (all.length > 3 && grand > 0 && all.every((a) => a.value >= 0)) findings.push({ title: "Concentration", text: `The top 3 of ${all.length} "${roles.category}" groups hold ${pct(sum(top3.map((a) => a.value)) / grand)} of ${label}: ${top3.map((a) => a.name).join(", ")}.`, basis: `${all.length} groups` });
  }
  if (metricCol?.numeric) {
    const n = metricCol.numeric;
    findings.push({ title: `Distribution of ${label}`, text: `Median ${fmt(n.median)}, mean ${fmt(n.mean)}; the middle 90% lies between ${fmt(n.p5)} and ${fmt(n.p95)}.${n.mean > n.median * 1.3 ? " The mean is well above the median, so a few large values pull it up." : ""}`, basis: `${used.length} rows` });
    if (n.negatives > 0) findings.push({ title: "Negative values", text: `${n.negatives} negative value(s) in "${label}". They are included in totals; they may be refunds or errors, which this tool cannot tell.`, basis: "column profile" });
  }
  const topCorr = profile.correlations[0];
  if (topCorr && Math.abs(topCorr.r) >= 0.5) findings.push({ title: "Strongest numeric association", text: `"${topCorr.a}" and "${topCorr.b}" move together (r = ${topCorr.r.toFixed(2)}, n = ${topCorr.n}). Correlation is not causation.`, basis: "Pearson r" });
  return out;
}
