/** Column typing and profiling. Everything is computed from the parsed rows; nothing is dropped. */

export type ColType = "number" | "date" | "boolean" | "category" | "text" | "empty";

export const NA_TOKENS = new Set(["", "na", "n/a", "null", "nan", "none", "#n/a"]);
const BOOL_TOKENS = new Set(["true", "false", "yes", "no", "t", "f", "y", "n"]);
const NUMBER_RE = /^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$/;
const ISO_DATE_RE = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?$/;
const SLASH_DATE_RE = /^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?$/;

export const isMissing = (v: string): boolean => NA_TOKENS.has(v.trim().toLowerCase());

export type DateOrder = "dmy" | "mdy" | "ambiguous-mdy";

/** Decide day/month order from evidence across the column; ambiguous columns assume month-first. */
export function detectDateOrder(values: string[]): DateOrder | null {
  let sawFirstOver12 = false;
  let sawSecondOver12 = false;
  let any = false;
  for (const v of values) {
    const m = SLASH_DATE_RE.exec(v.trim());
    if (!m) continue;
    any = true;
    if (Number(m[1]) > 12) sawFirstOver12 = true;
    if (Number(m[2]) > 12) sawSecondOver12 = true;
  }
  if (!any) return null;
  if (sawFirstOver12 && !sawSecondOver12) return "dmy";
  if (sawSecondOver12 && !sawFirstOver12) return "mdy";
  return "ambiguous-mdy";
}

/** Parse to UTC milliseconds, or null. Impossible calendar dates (31 Feb) are rejected. */
export function parseDate(value: string, order: DateOrder | null = "mdy"): number | null {
  const v = value.trim();
  let y: number, mo: number, d: number, h = 0, mi = 0, s = 0;
  const iso = ISO_DATE_RE.exec(v);
  if (iso) {
    [y, mo, d] = [Number(iso[1]), Number(iso[2]), Number(iso[3])];
    h = Number(iso[4] ?? 0);
    mi = Number(iso[5] ?? 0);
    s = Number(iso[6] ?? 0);
  } else {
    const m = SLASH_DATE_RE.exec(v);
    if (!m) return null;
    const dayFirst = order === "dmy";
    d = Number(dayFirst ? m[1] : m[2]);
    mo = Number(dayFirst ? m[2] : m[1]);
    y = Number(m[3]);
    h = Number(m[4] ?? 0);
    mi = Number(m[5] ?? 0);
    s = Number(m[6] ?? 0);
  }
  if (mo < 1 || mo > 12 || d < 1 || h > 23 || mi > 59 || s > 59) return null;
  const t = Date.UTC(y, mo - 1, d, h, mi, s);
  const check = new Date(t);
  if (check.getUTCFullYear() !== y || check.getUTCMonth() !== mo - 1 || check.getUTCDate() !== d) return null;
  return t;
}

export interface Quantiles { min: number; p5: number; p25: number; median: number; p75: number; p95: number; max: number }

export function quantile(sorted: number[], q: number): number {
  if (sorted.length === 0) return NaN;
  const pos = (sorted.length - 1) * q;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}

export interface Flag { level: "info" | "warn" | "high"; column?: string; code: string; message: string }

export interface ColumnProfile {
  name: string;
  index: number;
  type: ColType;
  inferredType: ColType;
  rows: number;
  missing: number;
  missingPct: number;
  distinct: number;
  invalid: number; // non-missing values that do not fit the column type
  top: { value: string; count: number }[];
  numeric?: Quantiles & { mean: number; std: number; negatives: number; zeros: number; outliers: number; histogram: { from: number; to: number; count: number }[] };
  date?: { min: number; max: number; order: DateOrder | null };
}

export interface Correlation { a: string; b: string; r: number; n: number }

export interface DatasetProfile {
  rows: number;
  columns: ColumnProfile[];
  duplicateRows: number;
  duplicateRowIndexes: number[]; // indexes of later copies of an earlier identical row
  flags: Flag[];
  correlations: Correlation[];
}

export function inferType(values: string[]): { type: ColType; order: DateOrder | null } {
  const present = values.filter((v) => !isMissing(v)).map((v) => v.trim());
  if (present.length === 0) return { type: "empty", order: null };
  const share = (pred: (v: string) => boolean) => present.filter(pred).length / present.length;
  const order = detectDateOrder(present);
  if (share((v) => BOOL_TOKENS.has(v.toLowerCase())) >= 0.98) return { type: "boolean", order: null };
  if (share((v) => NUMBER_RE.test(v)) >= 0.9) return { type: "number", order };
  if (share((v) => parseDate(v, order === "dmy" ? "dmy" : "mdy") !== null) >= 0.9) return { type: "date", order };
  const distinct = new Set(present).size;
  const type = distinct <= Math.max(20, present.length * 0.05) ? "category" : "text";
  return { type, order: null };
}

const mean = (xs: number[]) => xs.reduce((a, b) => a + b, 0) / xs.length;

function profileColumn(name: string, index: number, values: string[], type: ColType, inferred: ColType, order: DateOrder | null): ColumnProfile {
  const present = values.filter((v) => !isMissing(v));
  const counts = new Map<string, number>();
  for (const v of present) counts.set(v, (counts.get(v) ?? 0) + 1);
  const top = [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, 5).map(([value, count]) => ({ value, count }));
  const base: ColumnProfile = {
    name, index, type, inferredType: inferred, rows: values.length, missing: values.length - present.length,
    missingPct: values.length ? (values.length - present.length) / values.length : 0, distinct: counts.size, invalid: 0, top,
  };
  if (type === "number") {
    const nums = present.filter((v) => NUMBER_RE.test(v.trim())).map(Number).filter(Number.isFinite);
    base.invalid = present.length - nums.length;
    if (nums.length) {
      const sorted = [...nums].sort((a, b) => a - b);
      const q1 = quantile(sorted, 0.25), q3 = quantile(sorted, 0.75), iqr = q3 - q1;
      const mu = mean(nums);
      const std = nums.length > 1 ? Math.sqrt(nums.reduce((a, b) => a + (b - mu) ** 2, 0) / (nums.length - 1)) : 0;
      const lo = sorted[0], hi = sorted[sorted.length - 1];
      const bins = 10;
      const width = (hi - lo) / bins || 1;
      const histogram = Array.from({ length: bins }, (_, k) => ({ from: lo + k * width, to: lo + (k + 1) * width, count: 0 }));
      for (const x of nums) histogram[Math.min(bins - 1, Math.floor((x - lo) / width))].count++;
      base.numeric = {
        min: lo, p5: quantile(sorted, 0.05), p25: q1, median: quantile(sorted, 0.5), p75: q3, p95: quantile(sorted, 0.95), max: hi,
        mean: mu, std, negatives: nums.filter((x) => x < 0).length, zeros: nums.filter((x) => x === 0).length,
        outliers: iqr > 0 ? nums.filter((x) => x < q1 - 3 * iqr || x > q3 + 3 * iqr).length : 0, histogram,
      };
    }
  } else if (type === "date") {
    const ts = present.map((v) => parseDate(v, order === "dmy" ? "dmy" : "mdy")).filter((t): t is number => t !== null);
    base.invalid = present.length - ts.length;
    if (ts.length) base.date = { min: Math.min(...ts), max: Math.max(...ts), order };
  }
  return base;
}

export function profileDataset(headers: string[], rows: string[][], overrides: Record<string, ColType> = {}): DatasetProfile {
  const flags: Flag[] = [];
  const columns: ColumnProfile[] = headers.map((name, index) => {
    const values = rows.map((r) => r[index] ?? "");
    const inf = inferType(values);
    const type = overrides[name] ?? inf.type;
    const order = type === "date" ? (inf.order ?? detectDateOrder(values.filter((v) => !isMissing(v)))) : inf.order;
    return profileColumn(name, index, values, type, inf.type, order);
  });

  for (const c of columns) {
    if (c.type === "empty") flags.push({ level: "warn", column: c.name, code: "empty-column", message: `"${c.name}" has no values.` });
    if (c.missingPct > 0.2 && c.type !== "empty") flags.push({ level: c.missingPct > 0.5 ? "high" : "warn", column: c.name, code: "missing", message: `"${c.name}" is ${(c.missingPct * 100).toFixed(1)}% missing (${c.missing} of ${c.rows}).` });
    if (c.invalid > 0) flags.push({ level: "warn", column: c.name, code: "mixed-type", message: `"${c.name}" is treated as ${c.type}, but ${c.invalid} value(s) do not fit. They are kept, not deleted.` });
    if (c.distinct === 1 && c.rows - c.missing > 1) flags.push({ level: "info", column: c.name, code: "constant", message: `"${c.name}" holds a single value.` });
    if (c.numeric && c.numeric.outliers > 0) flags.push({ level: "info", column: c.name, code: "outliers", message: `"${c.name}" has ${c.numeric.outliers} value(s) beyond 3 interquartile ranges; check they are real.` });
    if (c.type === "date" && c.date?.order === "ambiguous-mdy") flags.push({ level: "warn", column: c.name, code: "date-order", message: `Dates in "${c.name}" could be day-first or month-first. Month-first is assumed; override the type or fix the file if wrong.` });
    if (c.type === "date" && c.date && c.date.max - c.date.min < 0) flags.push({ level: "warn", column: c.name, code: "date-range", message: `"${c.name}" has an invalid date range.` });
  }

  const seen = new Map<string, number>();
  const duplicateRowIndexes: number[] = [];
  rows.forEach((r, i) => {
    const key = r.join("\u0001");
    if (seen.has(key)) duplicateRowIndexes.push(i);
    else seen.set(key, i);
  });
  if (duplicateRowIndexes.length > 0) {
    flags.push({ level: "warn", code: "duplicate-rows", message: `${duplicateRowIndexes.length} row(s) exactly repeat an earlier row. Nothing was removed; the cleaned export lets you choose.` });
  }

  const numeric = columns.filter((c) => c.type === "number" && c.numeric && c.distinct > 2).slice(0, 8);
  const correlations: Correlation[] = [];
  for (let a = 0; a < numeric.length; a++) {
    for (let b = a + 1; b < numeric.length; b++) {
      const xs: number[] = [], ys: number[] = [];
      for (const r of rows) {
        const x = r[numeric[a].index], y = r[numeric[b].index];
        if (NUMBER_RE.test(x?.trim() ?? "") && NUMBER_RE.test(y?.trim() ?? "")) { xs.push(Number(x)); ys.push(Number(y)); }
      }
      if (xs.length < 10) continue;
      const mx = mean(xs), my = mean(ys);
      let sxy = 0, sxx = 0, syy = 0;
      for (let k = 0; k < xs.length; k++) { sxy += (xs[k] - mx) * (ys[k] - my); sxx += (xs[k] - mx) ** 2; syy += (ys[k] - my) ** 2; }
      if (sxx === 0 || syy === 0) continue;
      correlations.push({ a: numeric[a].name, b: numeric[b].name, r: sxy / Math.sqrt(sxx * syy), n: xs.length });
    }
  }
  correlations.sort((p, q) => Math.abs(q.r) - Math.abs(p.r));
  return { rows: rows.length, columns, duplicateRows: duplicateRowIndexes.length, duplicateRowIndexes, flags, correlations };
}
