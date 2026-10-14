import Link from "next/link";

export default function NotFound() {
  return (
    <div className="panel" style={{ marginTop: "2rem" }}>
      <h1 style={{ fontSize: "2.2rem" }}>Page not found</h1>
      <p>That address does not exist in SIGNALFORGE.</p>
      <div className="cta-row"><Link className="btn" href="/demo">Explore the live demo</Link><Link className="btn secondary" href="/analyze">Analyze your CSV</Link></div>
    </div>
  );
}
