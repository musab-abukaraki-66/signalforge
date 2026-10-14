"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [{ href: "/demo", label: "Live demo" }, { href: "/analyze", label: "Analyze your CSV" }, { href: "/methods", label: "Methods & privacy" }];
export function Nav() {
  const path = usePathname();
  return (
    <nav className="nav" aria-label="Main">
      {links.map((l) => <Link key={l.href} href={l.href} aria-current={path === l.href ? "page" : undefined}>{l.label}</Link>)}
    </nav>
  );
}
