"use client";
import { DragEvent, useCallback, useMemo, useRef, useState } from "react";
import { Analysis, Roles, analyze, suggestRoles } from "@/lib/analyze";
import { CsvError, MAX_BYTES, MAX_ROWS, ParsedCsv, parseCsv } from "@/lib/csv";
import { buildReport, cleanedCsv } from "@/lib/export";
import { download, fmtInt, fmtNum, fmtPct } from "@/lib/format";
import { ColType, DatasetProfile, profileDataset } from "@/lib/profile";
import { ChartFrame, Columns, HBars, LineChart } from "./charts";
import { Kpi, Tag } from "./ui";

const TYPES: ColType[] = ["number", "date", "category", "text", "boolean", "empty"];

function sampleCsv(): string {
  // Invented sample, generated locally with a fixed formula. Not real data.
  const rows = ["order_date,region,product,amount"];
  const regions = ["North", "South", "East", "West"], products = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"];
  for (let d = 0; d < 420; d++) {
    const date = new Date(Date.UTC(2023, 0, 1 + d)).toISOString().slice(0, 10);
    for (let k = 0; k < 3; k++) rows.push(`${date},${regions[(d + k) % 4]},${products[(d * 3 + k) % 5]},${(40 + ((d * 7 + k * 13) % 60) + d / 20).toFixed(2)}`);
  }
  rows.push("2023-02-03,North,Alpha,", "2023-02-03,North,Alpha,", "not-a-date,South,Beta,55");
  return rows.join("\n");
}

export function Analyzer() {
  const [fileName, setFileName] = useState("");
  const [parsed, setParsed] = useState<ParsedCsv | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const [overrides, setOverrides] = useState<Record<string, ColType>>({});
  const [roles, setRoles] = useState<Roles>({});
  const [dropDup, setDropDup] = useState(false);
  const [dropMissing, setDropMissing] = useState(false);
  const [focusCol, setFocusCol] = useState<string>("");
  const input = useRef<HTMLInputElement>(null);

  const profile: DatasetProfile | null = useMemo(() => (parsed ? profileDataset(parsed.headers, parsed.rows, overrides) : null), [parsed, overrides]);
  const analysis: Analysis | null = useMemo(() => (parsed && profile ? analyze(parsed.headers, parsed.rows, profile, roles) : null), [parsed, profile, roles]);

  const reset = useCallback(() => { setParsed(null); setFileName(""); setError(null); setOverrides({}); setRoles({}); setFocusCol(""); setDropDup(false); setDropMissing(false); if (input.current) input.current.value = ""; }, []);

  const load = useCallback(async (name: string, getText: () => Promise<string>, size: number) => {
    setError(null); setBusy(true);
    try {
      if (size > MAX_BYTES) throw new CsvError(`The file is ${(size / 1048576).toFixed(1)} MB; the maximum is ${MAX_BYTES / 1048576} MB.`);
      if (size === 0) throw new CsvError("The file is empty.");
      const text = await getText();
      await new Promise((r) => setTimeout(r, 0)); // let the loading state paint
      const p = parseCsv(text);
      const prof = profileDataset(p.headers, p.rows);
      setParsed(p); setFileName(name); setOverrides({}); setRoles(suggestRoles(prof)); setFocusCol(prof.columns.find((c) => c.numeric)?.name ?? prof.columns[0]?.name ?? "");
    } catch (e) {
      setParsed(null);
      setError(e instanceof CsvError ? e.message : "The file could not be read as text. Is it a CSV?");
    } finally { setBusy(false); }
  }, []);

  const onFile = (f: File | undefined) => { if (f) void load(f.name, () => f.text(), f.size); };
  const onDrop = (e: DragEvent) => { e.preventDefault(); setOver(false); onFile(e.dataTransfer.files[0]); };

  const metricIdx = parsed && roles.metric ? parsed.headers.indexOf(roles.metric) : -1;
  const exportReport = () => profile && download("signalforge-report.json", JSON.stringify(buildReport(fileName, profile, analysis), null, 2), "application/json");
  const exportClean = () => {
    if (!parsed || !profile) return;
    const out = cleanedCsv(parsed.headers, parsed.rows, profile, { dropDuplicateRows: dropDup, dropRowsMissingMetric: dropMissing && metricIdx >= 0 ? { index: metricIdx } : null });
    download("signalforge-cleaned.csv", out.csv, "text/csv");
  };
  const preview = dropDup || dropMissing ? cleanedCsv(parsed?.headers ?? [], parsed?.rows ?? [], profile ?? ({ duplicateRowIndexes: [] } as unknown as DatasetProfile), { dropDuplicateRows: dropDup, dropRowsMissingMetric: dropMissing && metricIdx >= 0 ? { index: metricIdx } : null }) : null;
  const focus = profile?.columns.find((c) => c.name === focusCol);

  return (
    <>
      <p className="banner info" role="note"><strong>Private by design.</strong> Your file is read and analysed in this browser tab. It is never uploaded, logged, or stored; reloading the page erases it. Limits: {MAX_BYTES / 1048576} MB, {fmtInt(MAX_ROWS)} rows, CSV text (comma, semicolon, tab or pipe delimited, UTF-8). Profiling is not a guarantee that your data is correct.</p>

      {!parsed && (
        <div className={`dropzone${over ? " over" : ""}`} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={onDrop}>
          <p><strong>Drag a CSV here</strong> or choose a file.</p>
          <input ref={input} id="csv-file" type="file" accept=".csv,text/csv,text/plain" className="sr-only" onChange={(e) => onFile(e.target.files?.[0])} />
          <label htmlFor="csv-file" className="btn" tabIndex={0} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.current?.click(); } }}>Choose CSV file</label>{" "}
          <button className="btn secondary" onClick={() => { const t = sampleCsv(); void load("sample-invented-sales.csv", async () => t, t.length); }}>Try an invented sample</button>
          {busy && <p role="status">Reading and profiling…</p>}
        </div>
      )}
      {error && <p className="banner danger" role="alert">{error}</p>}

      {parsed && profile && analysis && (
        <>
          <div className="filters" style={{ marginTop: "1rem" }}>
            <span><strong>{fileName}</strong> · {fmtInt(profile.rows)} rows · {profile.columns.length} columns · delimiter “{parsed.delimiter === "\t" ? "tab" : parsed.delimiter}”</span>
            <button className="btn secondary small" onClick={reset}>Remove file / start over</button>
          </div>

          <h2>1. Data quality</h2>
          {parsed.issues.raggedRows > 0 && <div className="flag warn">{parsed.issues.raggedRows} row(s) had a different number of fields than the header; short rows were padded with blanks, extra fields ignored. Check the file.</div>}
          {parsed.issues.blankLinesSkipped > 0 && <div className="flag">{parsed.issues.blankLinesSkipped} blank line(s) skipped.</div>}
          {parsed.issues.duplicateHeaders.length > 0 && <div className="flag warn">Duplicate column names were renamed: {parsed.issues.duplicateHeaders.join(", ")}.</div>}
          {profile.flags.length === 0 ? <div className="flag">No quality flags raised. That does not prove the data is right.</div> : profile.flags.map((f, i) => <div key={i} className={`flag ${f.level === "info" ? "" : f.level}`}>{f.message}</div>)}

          <h2 style={{ marginTop: "1.5rem" }}>2. Columns</h2>
          <p className="muted">Types are inferred cautiously. If one is wrong, change it; everything recalculates.</p>
          <div className="tablewrap panel"><table className="data"><caption className="sr-only">Column profile</caption>
            <thead><tr><th>Column</th><th>Type</th><th className="num">Missing</th><th className="num">Distinct</th><th>Range / top value</th></tr></thead>
            <tbody>{profile.columns.map((c) => (
              <tr key={c.name}><td><button className="btn secondary small" onClick={() => setFocusCol(c.name)} aria-pressed={focusCol === c.name}>{c.name}</button></td>
                <td><select aria-label={`Type of ${c.name}`} value={c.type} onChange={(e) => setOverrides({ ...overrides, [c.name]: e.target.value as ColType })}>{TYPES.map((t) => <option key={t}>{t}</option>)}</select>{c.type !== c.inferredType && <span className="muted"> (inferred {c.inferredType})</span>}</td>
                <td className="num">{fmtPct(c.missingPct)}</td><td className="num">{fmtInt(c.distinct)}</td>
                <td>{c.numeric ? `${fmtNum(c.numeric.min, 2)} – ${fmtNum(c.numeric.max, 2)}, median ${fmtNum(c.numeric.median, 2)}` : c.date ? `${new Date(c.date.min).toISOString().slice(0, 10)} – ${new Date(c.date.max).toISOString().slice(0, 10)}` : c.top[0] ? `${c.top[0].value.slice(0, 30)} (${c.top[0].count}×)` : "—"}</td></tr>))}</tbody></table></div>
          {focus?.numeric && (
            <ChartFrame title={`Distribution of ${focus.name}`} caption={`n=${fmtInt(focus.rows - focus.missing)}; quartiles ${fmtNum(focus.numeric.p25, 2)} / ${fmtNum(focus.numeric.median, 2)} / ${fmtNum(focus.numeric.p75, 2)}; mean ${fmtNum(focus.numeric.mean, 2)}; std ${fmtNum(focus.numeric.std, 2)}.`} table={{ head: ["From", "To", "Count"], rows: focus.numeric.histogram.map((h) => [fmtNum(h.from, 2), fmtNum(h.to, 2), h.count]) }}>
              <Columns label={`Histogram of ${focus.name}`} items={focus.numeric.histogram.map((h) => ({ x: fmtNum(h.from, 1), y: h.count }))} />
            </ChartFrame>
          )}
          {focus && !focus.numeric && focus.top.length > 0 && (
            <ChartFrame title={`Most common values in ${focus.name}`}><HBars label={`Top values of ${focus.name}`} items={focus.top.map((t) => ({ name: t.value, value: t.count }))} format={fmtInt} /></ChartFrame>
          )}
          {profile.correlations.length > 0 && <p className="muted" style={{ marginTop: ".75rem" }}>Strongest numeric associations: {profile.correlations.slice(0, 3).map((c) => `${c.a} ↔ ${c.b} (r=${c.r.toFixed(2)}, n=${c.n})`).join("; ")}. Correlation is not causation.</p>}

          <h2 style={{ marginTop: "1.5rem" }}>3. Choose what to analyse</h2>
          <div className="filters">
            {(["date", "metric", "category"] as const).map((role) => (
              <label className="field" key={role}>{role === "date" ? "Date column" : role === "metric" ? "Numeric metric" : "Group by"}
                <select value={roles[role] ?? ""} onChange={(e) => setRoles({ ...roles, [role]: e.target.value || undefined })}>
                  <option value="">None</option>
                  {profile.columns.filter((c) => (role === "date" ? c.type === "date" : role === "metric" ? c.type === "number" : c.type === "category" || c.type === "text" || c.type === "boolean")).map((c) => <option key={c.name}>{c.name}</option>)}
                </select></label>))}
          </div>
          {!roles.date && !roles.metric && !roles.category && <p className="banner info">Pick at least a date, a numeric metric or a grouping column. {profile.columns.some((c) => c.type === "date") ? "" : "No date column was detected, so trends and baselines are disabled."}</p>}

          {(roles.date || roles.metric || roles.category) && (
            <>
              <Tag kind="fact" />
              <div className="kpi-row" style={{ marginBottom: "1rem" }}>
                <Kpi label={roles.metric ? `Total ${roles.metric}` : "Rows"} value={fmtNum(analysis.total, 2)} />
                <Kpi label={roles.metric ? `Mean ${roles.metric}` : "Rows used"} value={roles.metric ? fmtNum(analysis.mean, 2) : fmtInt(analysis.usedRows)} />
                <Kpi label="Rows used" value={fmtInt(analysis.usedRows)} />
                <Kpi label="Rows excluded" value={fmtInt(analysis.skippedRows)} help="Rows without a valid date or numeric metric under the chosen roles. They stay in your file." />
              </div>
              <div className="grid">
                {analysis.series.length > 0 && (
                  <ChartFrame title={`${roles.metric ?? "Rows"} by ${analysis.grain}`} caption="The first and last periods can be partial." table={{ head: ["Period", "Value", "Rows"], rows: analysis.series.map((s) => [s.period, fmtNum(s.value, 2), s.count]) }}>
                    <LineChart label={`${roles.metric ?? "Rows"} by ${analysis.grain}`} series={[{ name: roles.metric ?? "Rows", color: "#0b7a6b", points: analysis.series.map((s) => ({ x: s.period, y: s.value })) }]} yFormat={(v) => fmtNum(v, 0)} yMin={Math.min(0, ...analysis.series.map((s) => s.value))} />
                  </ChartFrame>)}
                {analysis.categories.length > 0 && (
                  <ChartFrame title={`${roles.metric ?? "Rows"} by ${roles.category}`} caption="Top 15 groups." table={{ head: ["Group", "Value", "Share"], rows: analysis.categories.map((c) => [c.name, fmtNum(c.value, 2), fmtPct(c.share)]) }}>
                    <HBars label={`${roles.metric ?? "Rows"} by ${roles.category}`} items={analysis.categories.map((c) => ({ name: c.name, value: c.value, note: fmtPct(c.share) }))} format={(v) => fmtNum(v, 0)} />
                  </ChartFrame>)}
              </div>
              <h3 style={{ marginTop: "1.25rem" }}>Findings</h3>
              <p className="muted">Each finding is a calculated statistic, stated with its basis. None claims a cause.</p>
              {analysis.findings.map((f, i) => <div className="flag" key={i}><strong>{f.title}.</strong> {f.text} <span className="muted">({f.basis})</span></div>)}
              {analysis.baseline && ("unavailable" in analysis.baseline
                ? <p className="banner info">{analysis.baseline.unavailable}</p>
                : <ChartFrame title={`Baseline check on the last ${analysis.baseline.holdout} periods`} caption={`${analysis.baseline.note} Best on this holdout: ${analysis.baseline.best}.`} legend={[{ name: "Actual", color: "#14161a" }, { name: "Naive", color: "#9ca3af" }, { name: "4-period average", color: "#b45309" }, { name: "Linear trend", color: "#0b7a6b" }]} table={{ head: ["Period", "Actual", "Naive", "4-period avg", "Trend"], rows: analysis.baseline.rows.map((r) => [r.period, fmtNum(r.actual, 1), fmtNum(r.naive, 1), fmtNum(r.movingAverage, 1), fmtNum(r.trend, 1)]) }}>
                  <LineChart label="Baselines against actual values on the holdout" yMin={0} yFormat={(v) => fmtNum(v, 0)} series={[
                    { name: "Actual", color: "#14161a", points: analysis.baseline.rows.map((r) => ({ x: r.period, y: r.actual })) },
                    { name: "Naive", color: "#9ca3af", dashed: true, points: analysis.baseline.rows.map((r) => ({ x: r.period, y: r.naive })) },
                    { name: "4-period average", color: "#b45309", dashed: true, points: analysis.baseline.rows.map((r) => ({ x: r.period, y: r.movingAverage })) },
                    { name: "Linear trend", color: "#0b7a6b", points: analysis.baseline.rows.map((r) => ({ x: r.period, y: r.trend })) }]} />
                  <p className="muted">MAE — naive {fmtNum(analysis.baseline.mae.naive, 2)}, 4-period average {fmtNum(analysis.baseline.mae.movingAverage, 2)}, linear trend {fmtNum(analysis.baseline.mae.trend, 2)}.</p>
                </ChartFrame>)}
            </>
          )}

          <h2 style={{ marginTop: "1.5rem" }}>4. Export</h2>
          <div className="panel">
            <p className="muted">The cleaned CSV removes nothing unless you tick a box, and tells you how many rows each choice removes.</p>
            <label style={{ display: "block" }}><input type="checkbox" checked={dropDup} onChange={(e) => setDropDup(e.target.checked)} /> Remove {fmtInt(profile.duplicateRows)} exact duplicate row(s)</label>
            <label style={{ display: "block", marginBottom: ".75rem" }}><input type="checkbox" checked={dropMissing} disabled={metricIdx < 0} onChange={(e) => setDropMissing(e.target.checked)} /> Remove rows where “{roles.metric ?? "metric"}” is missing or not a number</label>
            {preview && <p aria-live="polite">This export would keep {fmtInt(preview.kept)} of {fmtInt(profile.rows)} rows (removing {fmtInt(preview.removed.duplicates)} duplicates, {fmtInt(preview.removed.missingMetric)} without a metric).</p>}
            <div className="cta-row" style={{ marginTop: 0 }}>
              <button className="btn" onClick={exportReport}>Download report (JSON)</button>
              <button className="btn secondary" onClick={exportClean}>Download cleaned CSV</button>
            </div>
          </div>
        </>
      )}
    </>
  );
}
