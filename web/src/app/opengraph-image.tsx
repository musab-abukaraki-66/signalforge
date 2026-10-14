import { ImageResponse } from "next/og";

export const alt = "SIGNALFORGE — From raw data to better decisions";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", background: "#14161a", color: "#f4f1ea", display: "flex", flexDirection: "column", justifyContent: "center", padding: 80 }}>
        <div style={{ display: "flex", fontSize: 34, letterSpacing: 6, fontWeight: 800 }}><span>SIGNAL</span><span style={{ color: "#2de2c0" }}>FORGE</span></div>
        <div style={{ fontSize: 76, lineHeight: 1.05, marginTop: 28, fontFamily: "serif" }}>Turn raw business data into decisions you can explain.</div>
        <div style={{ fontSize: 30, color: "#b8b3a6", marginTop: 32 }}>Labelled synthetic demo · analyse your CSV in your browser</div>
      </div>
    ),
    size,
  );
}
