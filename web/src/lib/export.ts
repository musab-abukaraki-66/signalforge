/** Report and cleaned-data exports. Cleaning is opt-in and every removal is reported. */
import { Analysis } from "./analyze";
import { DatasetProfile } from "./profile";

export interface CleanOptions { dropDuplicateRows: boolean; dropRowsMissingMetric?: { index: number } | null }

export function csvEscape(v: string): string {
  return /[",\n\r]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v;
}

export function cleanedCsv(headers: string[], rows: string[][], profile: DatasetProfile, opt: CleanOptions): { csv: string; removed: { duplicates: number; missingMetric: number }; kept: number } {
  const dup = new Set(opt.dropDuplicateRows ? profile.duplicateRowIndexes : []);
  let duplicates = 0, missingMetric = 0;
  const kept: string[][] = [];
  rows.forEach((r, i) => {
    if (dup.has(i)) { duplicates++; return; }
    if (opt.dropRowsMissingMetric && !/^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$/.test((r[opt.dropRowsMissingMetric.index] ?? "").trim())) { missingMetric++; return; }
    kept.push(r);
  });
  const csv = [headers, ...kept].map((r) => r.map(csvEscape).join(",")).join("\n") + "\n";
  return { csv, removed: { duplicates, missingMetric }, kept: kept.length };
}

export function buildReport(fileName: string, profile: DatasetProfile, analysis: Analysis | null, generatedAt: Date = new Date()) {
  return {
    tool: "SIGNALFORGE",
    generatedAt: generatedAt.toISOString(),
    note: "Computed in the browser from the file you loaded. Rows are not included; value counts appear only for low-cardinality category and boolean columns. Nothing was uploaded.",
    file: fileName,
    rows: profile.rows,
    duplicateRows: profile.duplicateRows,
    qualityFlags: profile.flags,
    columns: profile.columns.map(({ name, type, inferredType, missing, missingPct, distinct, invalid, numeric, date, top }) => ({ name, type, inferredType, missing, missingPct, distinct, invalid, numeric: numeric ? { ...numeric, histogram: undefined } : undefined, date: date ? { min: new Date(date.min).toISOString(), max: new Date(date.max).toISOString() } : undefined, top: type === "category" || type === "boolean" ? top : undefined })),
    correlations: profile.correlations.slice(0, 10),
    analysis: analysis && { roles: analysis.roles, usedRows: analysis.usedRows, skippedRows: analysis.skippedRows, total: analysis.total, grain: analysis.grain, series: analysis.series, categories: analysis.categories, findings: analysis.findings, baseline: analysis.baseline },
  };
}
