import type { Metadata } from "next";
import { DemoExplorer } from "@/components/DemoExplorer";

export const metadata: Metadata = { title: "Live demo", description: "Explore SIGNALFORGE on a labelled synthetic marketplace dataset: KPIs, data quality, forecast and a decision room." };

export default function DemoPage() {
  return (
    <>
      <h1 style={{ fontSize: "clamp(1.8rem,4vw,2.6rem)", marginTop: "1rem" }}>Live demo</h1>
      <DemoExplorer />
    </>
  );
}
