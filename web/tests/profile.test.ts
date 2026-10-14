import { describe, expect, it } from "vitest";
import { parseCsv } from "../src/lib/csv";
import { detectDateOrder, inferType, parseDate, profileDataset, quantile } from "../src/lib/profile";

const profileOf = (csv: string, over = {}) => { const p = parseCsv(csv); return profileDataset(p.headers, p.rows, over); };

describe("type inference", () => {
  it("recognises numbers, dates, booleans, categories", () => {
    expect(inferType(["1", "2.5", "-3", "1e3"]).type).toBe("number");
    expect(inferType(["2024-01-05", "2024-02-10"]).type).toBe("date");
    expect(inferType(["yes", "no", "yes"]).type).toBe("boolean");
    expect(inferType(Array.from({ length: 100 }, (_, i) => ["a", "b", "c"][i % 3])).type).toBe("category");
    expect(inferType(["", "NA", "null"]).type).toBe("empty");
  });
  it("rejects impossible dates and disambiguates day/month order from evidence", () => {
    expect(parseDate("2024-02-31")).toBeNull();
    expect(parseDate("13/02/2024", "dmy")).toBe(Date.UTC(2024, 1, 13));
    expect(detectDateOrder(["13/02/2024", "01/03/2024"])).toBe("dmy");
    expect(detectDateOrder(["02/13/2024"])).toBe("mdy");
    expect(detectDateOrder(["01/02/2024"])).toBe("ambiguous-mdy");
  });
  it("treats a mostly-numeric column as numeric and reports the odd values", () => {
    const rows = Array.from({ length: 20 }, (_, i) => `${i}`).concat(["oops"]).join("\n");
    const p = profileOf("v\n" + rows);
    expect(p.columns[0].type).toBe("number");
    expect(p.columns[0].invalid).toBe(1);
    expect(p.flags.some((f) => f.code === "mixed-type")).toBe(true);
  });
});

describe("profileDataset", () => {
  const csv = "id,amount,when,region\n1,10,2024-01-01,N\n2,20,2024-01-02,S\n2,20,2024-01-02,S\n3,,2024-01-04,N\n4,1000,2024-01-05,N\n";
  const p = profileOf(csv);
  it("counts rows, missing and duplicates without removing anything", () => {
    expect(p.rows).toBe(5);
    expect(p.duplicateRows).toBe(1);
    expect(p.duplicateRowIndexes).toEqual([2]);
    const amount = p.columns[1];
    expect(amount.missing).toBe(1);
    expect(amount.missingPct).toBeCloseTo(0.2);
  });
  it("computes numeric statistics", () => {
    const n = p.columns[1].numeric!;
    expect(n.min).toBe(10);
    expect(n.max).toBe(1000);
    expect(n.median).toBe(20);
    expect(n.mean).toBeCloseTo(262.5);
    expect(n.histogram.reduce((a, b) => a + b.count, 0)).toBe(4);
  });
  it("lets the user override an inferred type", () => {
    const o = profileOf(csv, { id: "category" });
    expect(o.columns[0].type).toBe("category");
    expect(o.columns[0].inferredType).toBe("number");
  });
  it("computes quantiles by interpolation and correlations only when meaningful", () => {
    expect(quantile([1, 2, 3, 4], 0.5)).toBe(2.5);
    const xs = Array.from({ length: 30 }, (_, i) => `${i},${i * 2},${(i * 7) % 5}`).join("\n");
    const q = profileOf("a,b,c\n" + xs);
    const ab = q.correlations.find((c) => c.a === "a" && c.b === "b")!;
    expect(ab.r).toBeCloseTo(1);
    expect(profileOf("a,b\n1,2\n2,4\n").correlations).toEqual([]); // too few pairs
  });
});
