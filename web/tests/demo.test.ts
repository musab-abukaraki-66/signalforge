import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { Bundle, applyFilters, holdoutOutcome, overview, roundHalfEven, scenario, toOrders } from "../src/lib/demo";

const bundle: Bundle = JSON.parse(readFileSync("public/demo/demo-bundle.json", "utf8"));
const orders = toOrders(bundle);
// The bundle stores floats rounded to 4 decimals, so compare within that rounding.
const close = (a: number | null, b: number | null) => (a === null || b === null ? expect(a).toBe(b) : expect(Math.abs(a - b)).toBeLessThanOrEqual(6e-5 * Math.max(1, Math.abs(b))));

describe("parity with the Python pipeline", () => {
  it("the bundle is labelled synthetic", () => expect(bundle.meta.data_source).toBe("synthetic-demo"));
  it("browser KPIs equal Python KPIs with no filters", () => {
    const js = overview(orders), py = bundle.expected.overview_all;
    for (const k of ["orders", "gmv", "aov", "freight_share", "late_rate", "on_time_rate", "avg_delivery_days", "avg_review_score", "cancellation_rate", "delivered_scored", "reviewed_orders"] as const) close(js[k], py[k]);
  });
  it("browser KPIs equal Python KPIs under date and state filters", () => {
    const f = bundle.expected.parity_filters;
    const js = overview(applyFilters(orders, { dateFrom: f.date_from, dateTo: f.date_to, states: f.states, categories: f.categories }));
    const py = bundle.expected.overview_filtered;
    for (const k of ["orders", "gmv", "aov", "late_rate", "avg_review_score"] as const) close(js[k], py[k]);
  });
  it("decision-room outcomes equal Python's threshold table", () => {
    for (const row of bundle.model!.expected_threshold_table) {
      const js = holdoutOutcome(bundle.model!.scored, row.review_share);
      expect(js.flagged).toBe(row.orders_flagged);
      expect(js.caught).toBe(row.late_orders_caught);
      close(js.precision, row.precision);
      close(js.recall, row.recall);
    }
  });
});

describe("scenario arithmetic", () => {
  const scored: [number, number][] = [[0.9, 1], [0.8, 1], [0.7, 1], [0.4, 0], [0.3, 0], [0.2, 0], [0.1, 0], [0.1, 0], [0.05, 0], [0.01, 0]];
  it("matches the worked example", () => {
    const r = scenario(scored, 0.3, { successRate: 0.5, costPerCase: 2, valuePerRescue: 10 });
    expect(r.avoided).toBeCloseTo(1.5);
    expect(r.cost).toBe(6);
    expect(r.net).toBeCloseTo(9);
  });
  it("invents nothing when inputs are missing", () => {
    const r = scenario(scored, 0.3, { successRate: null, costPerCase: null, valuePerRescue: null });
    expect([r.avoided, r.cost, r.net]).toEqual([null, null, null]);
    expect(r.missing.length).toBe(3);
  });
  it("rounds ties like Python and rejects bad shares", () => {
    expect([roundHalfEven(0.5), roundHalfEven(1.5), roundHalfEven(2.5)]).toEqual([0, 2, 2]);
    expect(() => holdoutOutcome(scored, 0)).toThrow();
  });
});
