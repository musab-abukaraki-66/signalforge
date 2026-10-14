import type { Metadata, Viewport } from "next";
import Link from "next/link";
import "./globals.css";
import { Nav } from "@/components/Nav";

const description = "Turn raw business data into decisions you can explain. Explore a labelled synthetic demo or analyse your own CSV entirely in your browser.";
export const metadata: Metadata = {
  metadataBase: new URL(process.env.VERCEL_PROJECT_PRODUCTION_URL ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}` : "http://localhost:3000"),
  title: { default: "SIGNALFORGE — From raw data to better decisions", template: "%s · SIGNALFORGE" },
  description,
  openGraph: { title: "SIGNALFORGE", description, type: "website", siteName: "SIGNALFORGE" },
  twitter: { card: "summary_large_image", title: "SIGNALFORGE", description },
};
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#14161a" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a className="skip" href="#main">Skip to content</a>
        <header className="site-header">
          <div className="wrap">
            <Link href="/" className="brand">SIGNAL<span>FORGE</span></Link>
            <Nav />
          </div>
        </header>
        <main id="main" className="wrap">{children}</main>
        <footer className="site-footer">
          <div className="wrap">SIGNALFORGE is an analytics project. Demo results are synthetic. Your CSV never leaves your browser. <Link href="/methods">Methods and privacy</Link></div>
        </footer>
      </body>
    </html>
  );
}
