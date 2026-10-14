import Link from "next/link";
import bundleJson from "../../public/demo/demo-bundle.json";
import { Bundle, overview, toOrders } from "@/lib/demo";
import { fmtInt, fmtMoney, fmtPct } from "@/lib/format";
import { LineChart } from "@/components/charts";

export default function Home() {
  const bundle = bundleJson as unknown as Bundle;
  const o = overview(toOrders(bundle));
  const weekly = bundle.forecast.orders.series;
  return (
    <>
      <section className="hero" style={{ marginTop: "1.5rem" }}>
        <div>
          <h1>Turn raw business data into <em>decisions you can explain.</em></h1>
          <p className="lead">SIGNALFORGE checks the data, defines the metrics, tests a forecast against honest baselines, and keeps facts, predictions and what-ifs apart.</p>
          <div className="cta-row">
            <Link className="btn" href="/demo">Explore the live demo</Link>
            <Link className="btn secondary" href="/analyze">Analyze your own CSV</Link>
          </div>
        </div>
        <div className="preview" aria-label="Preview of the demo, computed from the demo dataset">
          <span className="label">Synthetic demo · {fmtInt(bundle.meta.gold_rows.fact_order ?? 0)} orders · {bundle.meta.date_min} to {bundle.meta.date_max}</span>
          <div className="kpi-row" style={{ margin: ".75rem 0" }}>
            <div className="kpi"><div className="k">Orders</div><div className="v">{fmtInt(o.orders)}</div></div>
            <div className="kpi"><div className="k">GMV</div><div className="v">{fmtMoney(o.gmv)}</div></div>
            <div className="kpi"><div className="k">On-time</div><div className="v">{fmtPct(o.on_time_rate)}</div></div>
          </div>
          <LineChart label="Weekly orders in the synthetic demo" series={[{ name: "Weekly orders", color: "#2de2c0", points: weekly.map((w) => ({ x: w.week, y: w.value })) }]} />
        </div>
      </section>

      <section className="block" aria-labelledby="flow">
        <h2 id="flow">From file to finding in five steps</h2>
        <ol className="steps">
          <li><strong>Inspect data quality.</strong><br />Missing values, duplicates, odd types, suspicious values.</li>
          <li><strong>Understand performance.</strong><br />KPIs with written definitions and the sample size behind them.</li>
          <li><strong>Explore patterns.</strong><br />Trends, categories and associations, never causes.</li>
          <li><strong>Test scenarios.</strong><br />Change assumptions; see formulas and trade-offs.</li>
          <li><strong>Export findings.</strong><br />A JSON report and a cleaned CSV you control.</li>
        </ol>
      </section>

      <section className="block two-col">
        <div className="panel">
          <h3>What this is</h3>
          <p>A working analytics product: a labelled synthetic demo you can filter, and a CSV analyzer that profiles your file and builds charts and plain-language findings from the numbers it calculates. The full Python pipeline behind the demo (data quality checks, reconciliation, forecasting, a late-delivery model) is open source.</p>
        </div>
        <div className="panel">
          <h3>What this is not</h3>
          <p>Not validated on real company data yet, not an enterprise platform, and it makes no ROI or savings claims. Findings are associations. Forecasts extrapolate the past. Scenarios are only as good as the assumptions you type in.</p>
        </div>
      </section>

      <section className="block panel dark" aria-labelledby="privacy">
        <h2 id="privacy">Your CSV stays in your browser</h2>
        <p>Files you load are parsed and analysed on your device. SIGNALFORGE has no upload endpoint, no analytics, and does not save your file. Reload the page and it is gone. Limits: 10 MB and 200,000 rows. <Link href="/methods" style={{ color: "#2de2c0" }}>Read the details</Link>.</p>
      </section>
    </>
  );
}
