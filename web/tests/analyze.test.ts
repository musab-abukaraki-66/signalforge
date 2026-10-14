import { describe, expect, it } from "vitest";
import { analyze, baselines, suggestRoles } from "../src/lib/analyze";
import { parseCsv } from "../src/lib/csv";
import { buildReport, cleanedCsv, csvEscape } from "../src/lib/export";
import { profileDataset } from "../src/lib/profile";

function make(csv: string) {
  const p = parseCsv(csv);
  const profile = profileDataset(p.headers, p.rows);
  return { p, profile };
}
const sales = () => {
  const lines = ["date,region,amount"];
  for (let d = 0; d < 400; d++) {
    const date = new Date(Date.UTC(2023, 0, 1 + d)).toISOString().slice(0, 10);
    lines.push(`${date},${["N", "S", "E", "W"][d % 4]},${100 + (d % 30)}`);
  }
  return lines.join("\n");
};

describe("analyze", () => {
  it("suggests roles from names and types", () => {
    const { profile } = make(sales());
    expect(suggestRoles(profile)).toEqual({ date: "date", metric: "amount", category: "region" });
  });
  it("aggregates a monthly series and reports totals matching a direct sum", () => {
    const { p, profile } = make(sales());
    const a = analyze(p.headers, p.rows, profile, suggestRoles(profile));
    const direct = p.rows.reduce((s, r) => s + Number(r[2]), 0);
    expect(a.total).toBe(direct);
    expect(a.grain).toBe("month");
    expect(a.series.reduce((s, x) => s + x.value, 0)).toBe(direct);
    expect(a.categories.length).toBe(4);
    expect(a.findings.length).toBeGreaterThan(2);
  });
  it("counts skipped rows instead of silently dropping them", () => {
    const { p, profile } = make("date,amount\n2024-01-01,5\nnot a date,7\n2024-01-03,\n2024-01-04,9\n");
    const a = analyze(p.headers, p.rows, profile, { date: "date", metric: "amount" });
    expect(a.usedRows).toBe(2);
    expect(a.skippedRows).toBe(2);
    expect(a.findings[0].title).toMatch(/excluded/);
  });
  it("declines to forecast a short series and says why", () => {
    const { p, profile } = make("date,amount\n2024-01-01,5\n2024-01-02,6\n2024-01-03,7\n");
    const a = analyze(p.headers, p.rows, profile, { date: "date", metric: "amount" });
    expect(a.baseline).toHaveProperty("unavailable");
  });
  it("scores baselines on a holdout made of the latest periods only", () => {
    const series = Array.from({ length: 30 }, (_, i) => ({ period: `p${i}`, value: 10 + i, count: 1 }));
    const b = baselines(series);
    if ("unavailable" in b) throw new Error("expected baseline");
    expect(b.holdout).toBe(6);
    expect(b.rows.map((r) => r.actual)).toEqual([34, 35, 36, 37, 38, 39]);
    expect(b.rows[0].naive).toBe(33);
    expect(b.best).toBe("trend");
  });
  it("handles an all-text file gracefully", () => {
    const { p, profile } = make("a,b\nx,y\nz,w\n");
    const a = analyze(p.headers, p.rows, profile, {});
    expect(a.usedRows).toBe(2);
    expect(a.series).toEqual([]);
  });
});

describe("export", () => {
  it("escapes CSV fields", () => {
    expect(csvEscape('a,"b"')).toBe('"a,""b"""');
    expect(csvEscape("plain")).toBe("plain");
  });
  it("removes duplicates only when asked and reports counts", () => {
    const { p, profile } = make("a,b\n1,2\n1,2\n3,4\n");
    const keep = cleanedCsv(p.headers, p.rows, profile, { dropDuplicateRows: false });
    expect(keep.kept).toBe(3);
    const drop = cleanedCsv(p.headers, p.rows, profile, { dropDuplicateRows: true });
    expect(drop.kept).toBe(2);
    expect(drop.removed.duplicates).toBe(1);
    expect(drop.csv).toBe("a,b\n1,2\n3,4\n");
  });
  it("builds a report that carries no raw rows or free-text values", () => {
    const rows = Array.from({ length: 40 }, (_, i) => `${i},free text ${i}-secret`).join("\n");
    const { profile } = make("n,note\n" + rows);
    const json = JSON.stringify(buildReport("f.csv", profile, null, new Date("2024-01-01")));
    expect(json).toContain("f.csv");
    expect(json).not.toContain("secret");
  });
});
