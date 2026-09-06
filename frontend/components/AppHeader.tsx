// Destination path: frontend/components/AppHeader.tsx
// Replaces the existing file in full.
//
// CHANGE (2026-09-01): added persistent admin nav links for
// /admin/models (model catalogue CRUD) and /admin/vocab (task type /
// evaluation metric catalogue CRUD), alongside the existing
// Benchmarks, Agent Extraction, and Community Submissions links. Both
// pages previously only had ad-hoc "Manage models ->" / no link at all
// scattered inline on individual pages -- they're now reachable from
// every admin page via this shared header, matching how every other
// admin section is exposed. No other logic changed -- role fetching,
// logout, and the researcher-only Submit link are unchanged.

"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import Cookies from "js-cookie";
import { UserOut, fetchMe } from "../lib/api";
import NotificationBell from "./NotificationBell";

export default function AppHeader() {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<UserOut | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (!Cookies.get("access_token")) {
      setChecked(true);
      return;
    }
    fetchMe()
      .then(setUser)
      .catch(() => {
        Cookies.remove("access_token");
        setUser(null);
      })
      .finally(() => setChecked(true));
  }, [pathname]);

  function handleLogout() {
    Cookies.remove("access_token");
    setUser(null);
    router.push("/login");
  }

  function navClass(href: string) {
    const isBrowseCatalogue =
      href === "/browse" &&
      (pathname === "/browse" || (pathname.startsWith("/browse/") && pathname !== "/browse/heatmap"));

    return isBrowseCatalogue || pathname === href || (href !== "/browse" && pathname.startsWith(`${href}/`))
      ? "site-nav-link site-nav-link-active"
      : "site-nav-link";
  }

  if (!checked) return null;

  return (
    <header className="site-header">
      <div className="site-header-inner">
        <Link href="/browse" className="site-brand" aria-label="AISafetyBenchExplorer catalogue">
          <span className="site-brand-mark" aria-hidden="true" />
          <span>AISafetyBenchExplorer</span>
        </Link>

        <nav className="site-nav" aria-label="Primary navigation">
          <Link href="/browse" className={navClass("/browse")}>Catalogue</Link>
          <Link href="/browse/heatmap" className={navClass("/browse/heatmap")}>Research gaps</Link>
        {user?.role === "admin" && (
          <>
            <Link href="/admin/benchmarks" className={navClass("/admin/benchmarks")}>Manage benchmarks</Link>
            <Link href="/admin/extraction" className={navClass("/admin/extraction")}>Extraction</Link>
            <Link href="/admin/submissions" className={navClass("/admin/submissions")}>Submissions</Link>
            <Link href="/admin/models" className={navClass("/admin/models")}>Models</Link>
            <Link href="/admin/vocab" className={navClass("/admin/vocab")}>Vocabulary</Link>
          </>
        )}
        {user?.role === "researcher" && <Link href="/submit" className={navClass("/submit")}>Submit a benchmark</Link>}
        </nav>

        <div className="site-account">
        {user ? (
          <>
            <span className="site-user" title={user.email}>
              <span className="site-user-status" aria-hidden="true" />
              {user.role}
            </span>
            <NotificationBell />
            <button className="secondary site-logout" onClick={handleLogout}>Log out</button>
          </>
        ) : (
          <>
            <Link href="/login" className="button secondary">Log in</Link>
            <Link href="/signup" className="button">Sign up</Link>
          </>
        )}
        </div>
      </div>
    </header>
  );
}
