export const fmtInt = (x: number) => Math.round(x).toLocaleString("en-US");
export const fmtNum = (x: number | null | undefined, d = 1) => (x === null || x === undefined || Number.isNaN(x) ? "n/a" : x.toLocaleString("en-US", { maximumFractionDigits: d, minimumFractionDigits: 0 }));
export const fmtPct = (x: number | null | undefined, d = 1) => (x === null || x === undefined || Number.isNaN(x) ? "n/a" : `${(x * 100).toFixed(d)}%`);
export const fmtMoney = (x: number | null | undefined) => (x === null || x === undefined ? "n/a" : x.toLocaleString("en-US", { maximumFractionDigits: 0 }));
export function download(name: string, content: string, mime: string) {
  const url = URL.createObjectURL(new Blob([content], { type: mime }));
  const a = document.createElement("a");
  a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
