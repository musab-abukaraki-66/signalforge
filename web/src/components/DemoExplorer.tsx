"use client";
import { useEffect, useMemo, useState } from "react";
import { Bundle, Filters, Order, applyFilters, groupBy, holdoutOutcome, monthly, overview, reviewByDelay, routeLate, scenario, toOrders } from "@/lib/demo";
import { fmtInt, fmtMoney, fmtNum, fmtPct } from "@/lib/format";
import { ChartFrame, Columns, HBars, LineChart } from "./charts";
import { Kpi, SyntheticBanner, Tabs, Tag } from "./ui";

const TABS = [
  { id: "overview", label: "Overview" }, { id: "explore", label: "Explorer" }, { id: "quality", label: "Data quality" },
  { id: "forecast", label: "Trends & forecast" }, { id: "decision", label: "Decision room" }, { id: "methods", label: "Definitions & methods" },
];

export function DemoExplorer() {
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState("overview");
  const [filters, setFilters] = useState<Filters>({ states: [], categories: [] });

  useEffect(() => {
    let alive = true;
    fetch("/demo/demo-bundle.json")
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() as Promise<Bundle>; })
      .then((b) => { if (alive) setBundle(b); })
      .catch((e: Error) => { if (alive) setError(e.message); });
    return () => { alive = false; };
  }, []);

  const orders = useMemo(() => (bundle ? toOrders(bundle) : []), [bundle]);
  const filtered = useMemo(() => applyFilters(orders, filters), [orders, filters]);

  if (error) return <p className="banner danger" role="alert">The demo data could not be loaded ({error}). Reload the page; if it persists the deployment is missing its demo bundle.</p>;
  if (!bundle) return <div className="skeleton" role="status" aria-label="Loading demo data" />;

  return (
    <>
      <SyntheticBanner />
      <Tabs tabs={TABS} active={tab} onChange={setTab} idPrefix="demo">
        {(tab === "overview" || tab === "explore") && <FilterBar bundle={bundle} filters={filters} setFilters={setFilters} matched={filtered.length} total={orders.length} />}
        {tab === "overview" && <Overview bundle={bundle} orders={filtered} />}
        {tab === "explore" && <Explorer orders={filtered} />}
        {tab === "quality" && <Quality bundle={bundle} />}
        {tab === "forecast" && <Forecast bundle={bundle} />}
        {tab === "decision" && <Decision bundle={bundle} />}
        {tab === "methods" && <Methods bundle={bundle} />}
      </Tabs>
    </>
  );
}

function FilterBar({ bundle, filters, setFilters, matched, total }: { bundle: Bundle; filters: Filters; setFilters: (f: Filters) => void; matched: number; total: number }) {
  const set = (p: Partial<Filters>) => setFilters({ ...filters, ...p });
  return (
    <div className="filters" role="group" aria-label="Filters">
      <label className="field">From<input type="date" min={bundle.meta.date_min} max={bundle.meta.date_max} value={filters.dateFrom ?? ""} onChange={(e) => set({ dateFrom: e.target.value || undefined })} /></label>
      <label className="field">To<input type="date" min={bundle.meta.date_min} max={bundle.meta.date_max} value={filters.dateTo ?? ""} onChange={(e) => set({ dateTo: e.target.value || undefined })} /></label>
      <label className="field">Customer state
        <select value={filters.states[0] ?? ""} onChange={(e) => set({ states: e.target.value ? [e.target.value] : [] })}><option value="">All states</option>{bundle.meta.states.map((s) => <option key={s}>{s}</option>)}</select></label>
      <label className="field">Primary category
        <select value={filters.categories[0] ?? ""} onChange={(e) => set({ categories: e.target.value ? [e.target.value] : [] })}><option value="">All categories</option>{bundle.meta.categories.map((s) => <option key={s}>{s}</option>)}</select></label>
      <button className="btn secondary small" onClick={() => setFilters({ states: [], categories: [] })}>Reset</button>
      <span className="muted" aria-live="polite">{fmtInt(matched)} of {fmtInt(total)} orders match</span>
    </div>
  );
}

function Empty() { return <p className="banner info">No orders match these filters. Widen the date range or reset.</p>; }

function Overview({ bundle, orders }: { bundle: Bundle; orders: Order[] }) {
  const o = overview(orders);
  const m = monthly(orders);
  if (orders.length === 0) return <Empty />;
  const d = bundle.definitions;
  return (
    <>
      <Tag kind="fact" />
      <div className="kpi-row" style={{ marginBottom: "1rem" }}>
        <Kpi label="Orders" value={fmtInt(o.orders)} help={d["Orders"]} />
        <Kpi label="GMV" value={fmtMoney(o.gmv)} help={d["GMV"]} />
        <Kpi label="Avg order value" value={fmtNum(o.aov, 0)} help={d["Average order value"]} />
        <Kpi label="On-time rate" value={fmtPct(o.on_time_rate)} help={d["On-time rate"]} />
        <Kpi label="Avg review" value={fmtNum(o.avg_review_score, 2)} help={d["Average review score"]} />
        <Kpi label="Cancellation rate" value={fmtPct(o.cancellation_rate)} help={d["Cancellation rate"]} />
      </div>
      <p className="muted">Delivery KPIs use {fmtInt(o.delivered_scored)} delivered orders; review score uses {fmtInt(o.reviewed_orders)} reviewed orders. Hover a KPI for its definition.</p>
      <div className="grid">
        <ChartFrame title="GMV by purchase month" caption="Sum of item price, sales orders only." table={{ head: ["Month", "GMV"], rows: m.map((r) => [r.month, fmtMoney(r.gmv)]) }}>
          <Columns label="GMV by purchase month" items={m.map((r) => ({ x: r.month, y: r.gmv }))} yFormat={(v) => `${fmtNum(v / 1000, 0)}k`} />
        </ChartFrame>
        <ChartFrame title="Late-delivery rate by purchase month" caption="Latest months lack outcomes for orders still in transit." table={{ head: ["Month", "Late rate", "Delivered (n)"], rows: m.map((r) => [r.month, fmtPct(r.late_rate), r.delivered_scored]) }}>
          <LineChart label="Late-delivery rate by purchase month" series={[{ name: "Late rate", color: "#b45309", points: m.map((r) => ({ x: r.month, y: r.late_rate })) }]} yFormat={(v) => fmtPct(v, 0)} />
        </ChartFrame>
      </div>
    </>
  );
}

function Explorer({ orders }: { orders: Order[] }) {
  if (orders.length === 0) return <Empty />;
  const cats = groupBy(orders, "category").slice(0, 12);
  const states = groupBy(orders, "state");
  const route = routeLate(orders);
  const rbd = reviewByDelay(orders);
  return (
    <>
      <Tag kind="fact" />
      <div className="grid">
        <ChartFrame title="GMV by primary category" caption="Order GMV attributed to each order's first item's category." table={{ head: ["Category", "GMV", "Orders"], rows: cats.map((c) => [c.name, fmtMoney(c.gmv), c.orders]) }}>
          <HBars label="GMV by primary category" items={cats.map((c) => ({ name: c.name, value: c.gmv, note: `${c.orders} orders` }))} format={fmtMoney} />
        </ChartFrame>
        <ChartFrame title="GMV by customer state" table={{ head: ["State", "GMV", "Late rate", "Delivered (n)"], rows: states.map((s) => [s.name, fmtMoney(s.gmv), fmtPct(s.late_rate), s.delivered_scored]) }}>
          <HBars label="GMV by customer state" color="#374151" items={states.map((s) => ({ name: s.name, value: s.gmv, note: `late rate ${fmtPct(s.late_rate)}` }))} format={fmtMoney} />
        </ChartFrame>
        <ChartFrame title="Late rate: same state vs different state" caption="Seller state vs customer state. An association; distance and carriers are not controlled." table={{ head: ["Route", "Late rate", "Delivered (n)"], rows: route.map((r) => [r.route, fmtPct(r.lateRate), r.n]) }}>
          <HBars label="Late rate by route" color="#b45309" items={route.map((r) => ({ name: `${r.route} (n=${fmtInt(r.n)})`, value: r.lateRate ?? 0 }))} format={(v) => fmtPct(v)} />
        </ChartFrame>
        <ChartFrame title="Average review score by delivery outcome" caption="Only customers who chose to review; lateness is associated with lower scores, not proven to cause them." table={{ head: ["Outcome", "Avg review", "Reviewed (n)"], rows: rbd.map((r) => [r.name, fmtNum(r.avgReview, 2), r.n]) }}>
          <HBars label="Average review score by delivery outcome" items={rbd.map((r) => ({ name: r.name, value: r.avgReview ?? 0, note: `n=${r.n}` }))} format={(v) => fmtNum(v, 2)} />
        </ChartFrame>
      </div>
    </>
  );
}

function Quality({ bundle }: { bundle: Bundle }) {
  const blocking = bundle.quality.filter((q) => q.severity === "error");
  const failed = blocking.filter((q) => !q.passed);
  return (
    <>
      <p className="muted">Fixed scope: the build that produced this demo. Checks ran in the Python pipeline; filters do not apply.</p>
      <div className="kpi-row" style={{ marginBottom: "1rem" }}>
        <Kpi label="Blocking checks passed" value={`${blocking.length - failed.length} / ${blocking.length}`} />
        <Kpi label="Warnings raised" value={String(bundle.quality.filter((q) => q.severity === "warn" && !q.passed).length)} />
        <Kpi label="Orders" value={fmtInt(bundle.meta.gold_rows.fact_order ?? 0)} />
        <Kpi label="Built" value={bundle.meta.generated_at.slice(0, 10)} />
      </div>
      <p className="banner info">Lineage: raw CSV → bronze (text, hashed) → silver (typed, de-duplicated) → gold (facts, dimensions) → this app.</p>
      <div className="tablewrap panel"><table className="data"><thead><tr><th>Status</th><th>Severity</th><th>Check</th><th className="num">Violations</th><th>Note</th></tr></thead>
        <tbody>{[...bundle.quality].sort((a, b) => Number(a.passed) - Number(b.passed)).map((q) => <tr key={q.name}><td>{q.passed ? "PASS" : "FAIL"}</td><td>{q.severity}</td><td className="mono">{q.name}</td><td className="num">{q.violations}</td><td>{q.description}</td></tr>)}</tbody></table></div>
    </>
  );
}

function Forecast({ bundle }: { bundle: Bundle }) {
  const [measure, setMeasure] = useState<"orders" | "gmv">("orders");
  const f = bundle.forecast[measure];
  const m = f.metrics, base = f.best_baseline;
  const gain = 1 - m.holt.mae / m[base].mae;
  const baseName = base.replace("_", " ");
  const verdict = gain >= 0.05 ? `The model beat the best baseline by ${fmtPct(gain, 0)} on the last ${f.horizon} weeks (MAE ${fmtNum(m.holt.mae)} vs ${fmtNum(m[base].mae)}). That is ${f.horizon} data points: modest evidence.`
    : gain > -0.05 ? `The model and the ${baseName} baseline are effectively tied on the held-out weeks (MAE ${fmtNum(m.holt.mae)} vs ${fmtNum(m[base].mae)}). The simpler baseline is as good a guide.`
    : `The model did NOT beat the ${baseName} baseline (MAE ${fmtNum(m.holt.mae)} vs ${fmtNum(m[base].mae)}). Prefer the simpler baseline.`;
  const fmt = measure === "gmv" ? fmtMoney : (v: number) => fmtNum(v, 0);
  return (
    <>
      <p className="muted">Fixed scope: weekly, complete weeks only, last {f.horizon} weeks held out. Computed by the Python pipeline on the synthetic demo.</p>
      <div role="radiogroup" aria-label="Series" style={{ display: "flex", gap: ".5rem", marginBottom: "1rem" }}>
        {(["orders", "gmv"] as const).map((k) => <button key={k} role="radio" aria-checked={measure === k} className={`btn small ${measure === k ? "" : "secondary"}`} onClick={() => setMeasure(k)}>{k === "orders" ? "Weekly orders" : "Weekly GMV"}</button>)}
      </div>
      <Tag kind="pred" />
      <div className="kpi-row" style={{ marginBottom: "1rem" }}>
        <Kpi label="Model MAE (held-out)" value={fmtNum(m.holt.mae)} />
        <Kpi label={`Best baseline MAE (${baseName})`} value={fmtNum(m[base].mae)} />
        <Kpi label="80% interval coverage" value={fmtPct(m.holt.coverage_80, 0)} help="Share of held-out weeks inside the interval; tiny sample." />
      </div>
      <p className={gain >= 0.05 ? "banner info" : "banner"}>{verdict}</p>
      <div className="grid">
        <ChartFrame title="Backtest: forecasts made from earlier weeks only" legend={[{ name: "Actual", color: "#14161a" }, { name: "Model", color: "#0b7a6b" }, { name: "Naive", color: "#9ca3af" }, { name: "4-week average", color: "#b45309" }]} table={{ head: ["Week", "Actual", "Model", "Naive", "4-wk avg"], rows: f.backtest.map((b) => [b.week_start, fmt(b.actual), fmt(b.holt), fmt(b.naive), fmt(b.moving_average)]) }}>
          <LineChart label="Backtest of weekly forecast against baselines" yMin={0} yFormat={fmt} band={f.backtest.map((b) => ({ x: b.week_start, lo: b.holt_lo80, hi: b.holt_hi80 }))}
            series={[{ name: "Actual", color: "#14161a", points: f.backtest.map((b) => ({ x: b.week_start, y: b.actual })) }, { name: "Model", color: "#0b7a6b", points: f.backtest.map((b) => ({ x: b.week_start, y: b.holt })) }, { name: "Naive", color: "#9ca3af", dashed: true, points: f.backtest.map((b) => ({ x: b.week_start, y: b.naive })) }, { name: "4-week average", color: "#b45309", dashed: true, points: f.backtest.map((b) => ({ x: b.week_start, y: b.moving_average })) }]} />
        </ChartFrame>
        <ChartFrame title={`Forecast: next ${f.horizon} weeks`} caption="Shaded band is an approximate 80% interval (normal errors from in-sample residuals). A forecast extrapolates the past; it says nothing about causes." table={{ head: ["Week", "Forecast", "Low", "High"], rows: f.future.map((r) => [r.week_start, fmt(r.forecast), fmt(r.lo80), fmt(r.hi80)]) }}>
          <LineChart label="Forecast for the coming weeks" yFormat={fmt} band={f.future.map((r) => ({ x: r.week_start, lo: r.lo80, hi: r.hi80 }))}
            series={[{ name: "Observed", color: "#14161a", points: f.series.slice(-20).map((s) => ({ x: s.week, y: s.value })) }, { name: "Forecast", color: "#0b7a6b", width: 3, points: f.future.map((r) => ({ x: r.week_start, y: r.forecast })) }]} />
        </ChartFrame>
      </div>
    </>
  );
}

function Decision({ bundle }: { bundle: Bundle }) {
  const model = bundle.model;
  const [share, setShare] = useState(0.2);
  const [rescue, setRescue] = useState("");
  const [cost, setCost] = useState("");
  const [value, setValue] = useState("");
  if (!model) return <p className="banner info">No model output is bundled with this build.</p>;
  const num = (s: string) => { const x = parseFloat(s); return s.trim() === "" || Number.isNaN(x) || x < 0 ? null : x; };
  const rescueRate = num(rescue);
  const ev = holdoutOutcome(model.scored, share);
  const sc = scenario(model.scored, share, { successRate: rescueRate !== null && rescueRate <= 1 ? rescueRate : null, costPerCase: num(cost), valuePerRescue: num(value) });
  const chosen = model.test[model.chosen], base = model.test.baseline_prior;
  const rule = model.test.rule_cross_state;
  const pr = (r: Record<string, number | null | Record<string, number>>) => r.pr_auc as number;
  const table = [0.05, 0.1, 0.2, 0.3, 0.5].map((s) => ({ s, ...holdoutOutcome(model.scored, s) }));
  return (
    <>
      <p><strong>Question:</strong> which orders should operations review first to catch late deliveries, given limited capacity?</p>
      <Tag kind="pred" />
      <div className="kpi-row" style={{ marginBottom: ".75rem" }}>
        <Kpi label="Model PR-AUC (held-out later window)" value={fmtNum(pr(chosen), 3)} />
        <Kpi label="Baseline PR-AUC (= base rate)" value={fmtNum(pr(base), 3)} />
        <Kpi label="Cross-state rule recall / precision" value={`${fmtPct(rule.recall as number, 0)} / ${fmtPct(rule.precision as number, 0)}`} />
      </div>
      {pr(chosen) < 1.5 * pr(base) && <p className="banner">On this held-out window the model ranks late orders only modestly better than the base rate. Treat prioritisation as weak evidence and compare it with the simple cross-state rule before acting. The synthetic generator was not tuned to improve this.</p>}
      <p className="muted">Model {model.chosen}; trained on {fmtInt(model.split.train.n)} orders up to {model.split.train.to.slice(0, 10)}, tested on {fmtInt(model.split.test.n)} orders from {model.split.test.from.slice(0, 10)}. Features known at purchase only. Synthetic data.</p>
      <div className="panel" style={{ marginBottom: "1rem" }}>
        <label className="field" style={{ maxWidth: 420 }}>Share of orders operations can review (highest risk first): <strong>{fmtPct(share, 0)}</strong>
          <input type="range" min={0.05} max={0.5} step={0.05} value={share} onChange={(e) => setShare(Number(e.target.value))} aria-valuetext={`${Math.round(share * 100)} percent`} /></label>
        <Tag kind="fact" />
        <p style={{ margin: 0 }}>On the held-out window, reviewing the top {fmtPct(share, 0)} by model risk means <strong>{fmtInt(ev.flagged)}</strong> orders, of which <strong>{fmtInt(ev.caught)}</strong> were actually late: <strong>{fmtPct(ev.recall, 0)}</strong> of the {fmtInt(ev.lateTotal)} late orders. Precision {fmtPct(ev.precision, 0)} vs {fmtPct(ev.baseRate, 0)} base rate (lift {fmtNum(ev.lift, 2)}x).</p>
      </div>
      <ChartFrame title="Precision and recall by share reviewed" legend={[{ name: "Precision", color: "#0b7a6b" }, { name: "Recall", color: "#b45309" }]} table={{ head: ["Share reviewed", "Orders", "Late caught", "Precision", "Recall"], rows: table.map((r) => [fmtPct(r.s, 0), r.flagged, r.caught, fmtPct(r.precision), fmtPct(r.recall)]) }}>
        <LineChart label="Precision and recall by share of orders reviewed" yFormat={(v) => fmtPct(v, 0)} series={[{ name: "Precision", color: "#0b7a6b", points: table.map((r) => ({ x: fmtPct(r.s, 0), y: r.precision })) }, { name: "Recall", color: "#b45309", points: table.map((r) => ({ x: fmtPct(r.s, 0), y: r.recall })) }]} />
      </ChartFrame>
      <div className="panel" style={{ marginTop: "1rem" }}>
        <h3>What-if: you supply the assumptions</h3>
        <Tag kind="scen" />
        <div className="filters" style={{ border: 0, padding: 0 }}>
          <label className="field">Rescue rate (0–1)<input inputMode="decimal" value={rescue} onChange={(e) => setRescue(e.target.value)} placeholder="unknown" /></label>
          <label className="field">Cost per reviewed case<input inputMode="decimal" value={cost} onChange={(e) => setCost(e.target.value)} placeholder="unknown" /></label>
          <label className="field">Value of one rescued order<input inputMode="decimal" value={value} onChange={(e) => setValue(e.target.value)} placeholder="unknown" /></label>
        </div>
        <p className="mono" style={{ fontSize: ".85rem" }}>avoided = late caught × rescue rate; cost = orders reviewed × cost per case; net = avoided × value − cost</p>
        {sc.avoided !== null && <p>Late deliveries avoided in a window this size: <strong>{fmtNum(sc.avoided, 1)}</strong> ({fmtInt(ev.caught)} × {fmtNum(rescueRate, 2)}).</p>}
        {sc.cost !== null && <p>Review cost: <strong>{fmtMoney(sc.cost)}</strong>.</p>}
        {sc.net !== null && <p>Net value under your inputs: <strong>{fmtMoney(sc.net)}</strong>.</p>}
        {sc.missing.length > 0 && <p className="muted">Not computed — missing: {sc.missing.join(", ")}. The data contains no cost or benefit figures, so none are assumed.</p>}
        {rescue.trim() !== "" && (rescueRate === null || rescueRate > 1) && <p className="banner danger" role="alert">Rescue rate must be a number between 0 and 1.</p>}
      </div>
    </>
  );
}

function Methods({ bundle }: { bundle: Bundle }) {
  const model = bundle.model;
  return (
    <>
      <div className="panel"><h3>KPI definitions</h3>
        <dl style={{ margin: 0 }}>{Object.entries(bundle.definitions).map(([k, v]) => <div key={k} style={{ marginBottom: ".6rem" }}><dt><strong>{k}</strong></dt><dd style={{ margin: 0 }} className="muted">{v}</dd></div>)}</dl></div>
      <div className="panel" style={{ marginTop: "1rem" }}><h3>Labels</h3>
        <p><Tag kind="fact" /> computed directly from validated data. <Tag kind="pred" /> a score or projection with a baseline on a held-out later period. <Tag kind="scen" /> depends on assumptions you enter. No causal claims are made.</p></div>
      {model && <div className="panel" style={{ marginTop: "1rem" }}><h3>Model card: late-delivery risk</h3>
        <p>Target: delivered after the estimated date. Prediction time: order placement. Split: chronological, preprocessing fitted on train only, threshold chosen on validation. Compared with the base rate and a cross-state rule.</p>
        <p><strong>Features (known at purchase):</strong> <span className="mono">{model.features.join(", ")}</span></p>
        <p><strong>Excluded as post-outcome:</strong> <span className="mono">{model.excluded.join(", ")}</span></p>
        <p className="muted">Only delivered orders have a label, so the latest purchases are missing. Synthetic data only; no real-world performance is implied.</p></div>}
    </>
  );
}
