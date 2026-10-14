import { ReactNode } from "react";

const W = 640, H = 280, M = { l: 64, r: 12, t: 14, b: 40 };
const niceMax = (v: number) => { if (v <= 0) return 1; const p = 10 ** Math.floor(Math.log10(v)); const n = v / p; return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p; };

export interface Series { name: string; color: string; points: { x: string; y: number | null }[]; dashed?: boolean; width?: number }
export interface Band { x: string; lo: number; hi: number }

export function ChartFrame({ title, caption, legend, children, table }: { title: string; caption?: string; legend?: { name: string; color: string }[]; children: ReactNode; table?: { head: string[]; rows: (string | number)[][] } }) {
  return (
    <figure className="chart" style={{ margin: 0 }}>
      <h3>{title}</h3>
      {caption && <p className="cap">{caption}</p>}
      {children}
      {legend && <div className="legend">{legend.map((l) => <span key={l.name}><i style={{ background: l.color }} />{l.name}</span>)}</div>}
      {table && (
        <details>
          <summary>View as table</summary>
          <div className="tablewrap"><table className="data"><thead><tr>{table.head.map((h, i) => <th key={h} className={i ? "num" : ""}>{h}</th>)}</tr></thead>
            <tbody>{table.rows.slice(0, 60).map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} className={j ? "num" : ""}>{c}</td>)}</tr>)}</tbody></table></div>
        </details>
      )}
    </figure>
  );
}

export function LineChart({ series, band, yFormat = (v) => String(v), label, yMin = 0 }: { series: Series[]; band?: Band[]; yFormat?: (v: number) => string; label: string; yMin?: number }) {
  const xs = [...new Set(series.flatMap((s) => s.points.map((p) => p.x)).concat(band?.map((b) => b.x) ?? []))].sort();
  if (xs.length === 0) return <p className="muted">No data for the current selection.</p>;
  const ys = series.flatMap((s) => s.points.map((p) => p.y).filter((v): v is number => v !== null)).concat(band?.flatMap((b) => [b.lo, b.hi]) ?? []);
  const maxY = Math.max(...ys);
  const top = niceMax(maxY > 0 ? maxY : 1), bottom = Math.min(yMin, ...ys);
  const px = (i: number) => M.l + (xs.length === 1 ? (W - M.l - M.r) / 2 : (i / (xs.length - 1)) * (W - M.l - M.r));
  const py = (v: number) => H - M.b - ((v - bottom) / (top - bottom || 1)) * (H - M.t - M.b);
  const idx = new Map(xs.map((x, i) => [x, i]));
  const ticks = [0, 1, 2, 3, 4].map((k) => bottom + ((top - bottom) * k) / 4);
  const labelEvery = Math.max(1, Math.ceil(xs.length / 6));
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
      <title>{label}</title>
      <g className="axis">
        {ticks.map((t) => (<g key={t}><line className="gridline" x1={M.l} x2={W - M.r} y1={py(t)} y2={py(t)} /><text x={M.l - 6} y={py(t) + 4} textAnchor="end">{yFormat(t)}</text></g>))}
        {xs.map((x, i) => i % labelEvery === 0 && <text key={x} x={px(i)} y={H - 10} textAnchor="middle">{x.length > 7 ? x.slice(2) : x}</text>)}
      </g>
      {band && band.length > 0 && (
        <polygon fill="rgba(11,122,107,.16)" points={[...band.map((b) => `${px(idx.get(b.x)!)},${py(b.hi)}`), ...[...band].reverse().map((b) => `${px(idx.get(b.x)!)},${py(b.lo)}`)].join(" ")} />
      )}
      {series.map((s) => {
        const pts = s.points.filter((p) => p.y !== null);
        return (<polyline key={s.name} fill="none" stroke={s.color} strokeWidth={s.width ?? 2.2} strokeDasharray={s.dashed ? "5 4" : undefined} strokeLinejoin="round" points={pts.map((p) => `${px(idx.get(p.x)!)},${py(p.y as number)}`).join(" ")} />);
      })}
      {xs.length <= 60 && series[0]?.points.map((p) => p.y !== null && (<circle key={p.x} cx={px(idx.get(p.x)!)} cy={py(p.y)} r={3} fill={series[0].color}><title>{`${p.x}: ${yFormat(p.y)}`}</title></circle>))}
    </svg>
  );
}

export function Columns({ items, color = "#0b7a6b", yFormat = (v) => String(v), label }: { items: { x: string; y: number }[]; color?: string; yFormat?: (v: number) => string; label: string }) {
  if (items.length === 0) return <p className="muted">No data for the current selection.</p>;
  const maxY = Math.max(...items.map((i) => i.y));
  const top = niceMax(maxY > 0 ? maxY : 1);
  const bw = (W - M.l - M.r) / items.length;
  const labelEvery = Math.max(1, Math.ceil(items.length / 7));
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
      <title>{label}</title>
      <g className="axis">
        {[0, 1, 2, 3, 4].map((k) => { const v = (top * k) / 4, y = H - M.b - (v / top) * (H - M.t - M.b); return <g key={k}><line className="gridline" x1={M.l} x2={W - M.r} y1={y} y2={y} /><text x={M.l - 6} y={y + 4} textAnchor="end">{yFormat(v)}</text></g>; })}
        {items.map((it, i) => i % labelEvery === 0 && <text key={it.x} x={M.l + i * bw + bw / 2} y={H - 10} textAnchor="middle">{it.x.length > 7 ? it.x.slice(2, 7) : it.x}</text>)}
      </g>
      {items.map((it, i) => { const h = (it.y / top) * (H - M.t - M.b); return <rect key={it.x} x={M.l + i * bw + bw * 0.12} y={H - M.b - h} width={bw * 0.76} height={Math.max(h, 0)} fill={color} rx={2}><title>{`${it.x}: ${yFormat(it.y)}`}</title></rect>; })}
    </svg>
  );
}

export function HBars({ items, color = "#0b7a6b", format = (v) => String(v), label }: { items: { name: string; value: number; note?: string }[]; color?: string; format?: (v: number) => string; label: string }) {
  if (items.length === 0) return <p className="muted">No data for the current selection.</p>;
  const row = 32, left = 190, h = items.length * row + 8;
  const max = Math.max(...items.map((i) => Math.abs(i.value)), 1);
  return (
    <svg viewBox={`0 0 ${W} ${h}`} role="img" aria-label={label}>
      <title>{label}</title>
      {items.map((it, i) => { const w = (Math.abs(it.value) / max) * (W - left - 80); return (
        <g key={it.name} transform={`translate(0 ${i * row + 4})`}>
          <text x={left - 8} y={17} textAnchor="end" style={{ font: "15px var(--sans)", fill: "#14161a" }}>{it.name.length > 24 ? `${it.name.slice(0, 23)}…` : it.name}</text>
          <rect x={left} y={3} width={Math.max(w, 1)} height={20} fill={color} rx={2}><title>{`${it.name}: ${format(it.value)}${it.note ? ` (${it.note})` : ""}`}</title></rect>
          <text x={left + w + 6} y={18} style={{ font: "14px var(--mono)", fill: "#4b5563" }}>{format(it.value)}</text>
        </g>); })}
    </svg>
  );
}
