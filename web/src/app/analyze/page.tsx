import type { Metadata } from "next";
import { Analyzer } from "@/components/Analyzer";

export const metadata: Metadata = { title: "Analyze your CSV", description: "Profile a CSV, check its quality and get data-driven charts and findings. Processed entirely in your browser." };

export default function AnalyzePage() {
  return (
    <>
      <h1 style={{ fontSize: "clamp(1.8rem,4vw,2.6rem)", marginTop: "1rem" }}>Analyze your CSV</h1>
      <Analyzer />
    </>
  );
}
