"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/", label: "Home" },
  { href: "/profile", label: "Profile" },
  { href: "/matches", label: "Matches" },
];

export default function Nav() {
  const pathname = usePathname();

  return (
    <nav className="gc-nav">
      {navItems.map(({ href, label }) => {
        const isActive = pathname === href || (href !== "/" && pathname.startsWith(href));
        return (
          <Link
            key={href}
            href={href}
            className={`gc-nav-link ${isActive ? "gc-nav-active" : ""}`}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
