import type { Metadata } from "next";

export const metadata: Metadata = { title: "Methods & privacy", description: "How SIGNALFORGE handles your data, what the demo is, and the limits of every number." };

export default function Methods() {
  return (
    <>
      <h1 style={{ fontSize: "clamp(1.8rem,4vw,2.6rem)", marginTop: "1rem" }}>Methods &amp; privacy</h1>
      <div className="two-col">
        <section className="panel"><h2>Your data</h2>
          <p>CSV files you choose are read with your browser&apos;s File API and analysed by JavaScript in this tab. There is no upload endpoint, no database, no analytics or tracking script, and no AI service involved. Nothing is written to local storage. Closing or reloading the page erases the file.</p>
          <p>The reports you download are generated on your device. The JSON report contains statistics, flags and aggregated findings, not your rows; value counts appear only for low-cardinality category columns.</p>
          <p>Limits: 10 MB, 200,000 rows, 200 columns. Very large files may be slow because everything runs on your device.</p></section>
        <section className="panel"><h2>The demo</h2>
          <p>The demo is a <strong>synthetic</strong> marketplace dataset created by a seeded generator in the open-source Python pipeline. It imitates the shape of an e-commerce dataset; it describes no real company and supports no real-world conclusion. Its numbers were computed by the pipeline (data quality checks, KPI reconciliation, forecast, model), then exported. The browser recomputes the KPIs from the exported orders and the tests check they equal the Python values.</p>
          <p>No real dataset has been validated yet. When one is, it will be labelled with its source and licence.</p></section>
      </div>
      <section className="panel" style={{ marginTop: "1rem" }}><h2>How to read the numbers</h2>
        <ul>
          <li><strong>Observed:</strong> a calculation on the data, with its sample size.</li>
          <li><strong>Prediction / forecast:</strong> checked against simple baselines on a later period the model never saw. If a baseline ties or wins, the page says so.</li>
          <li><strong>Scenario:</strong> arithmetic on assumptions you type. Leave an input empty and nothing is computed from it.</li>
          <li><strong>Causes:</strong> never claimed. Associations in observational data cannot show what would change if you intervened.</li>
          <li><strong>GMV</strong> means item price summed over sales orders. It is not revenue or profit.</li>
        </ul></section>
      <section className="panel" style={{ marginTop: "1rem" }}><h2>CSV analyzer rules</h2>
        <ul>
          <li>Types are inferred, shown, and overridable. Mixed columns are flagged, never silently fixed.</li>
          <li>Rows are never dropped without a count. The cleaned CSV only removes what you tick.</li>
          <li>Ambiguous dates (01/02/2024) are flagged; day-first is used only when the file proves it.</li>
          <li>Baselines need at least 20 complete periods; otherwise none is shown and the page says why.</li>
          <li>Statistics: quartiles by linear interpolation, outliers beyond 3 interquartile ranges, Pearson correlation on complete pairs (at least 10).</li>
        </ul></section>
    </>
  );
}
