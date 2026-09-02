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

  if (!checked) return null;

  return (
    <div
      style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        padding: "10px 16px", borderBottom: "1px solid #e5e5e5", flexWrap: "wrap", gap: 8,
      }}
    >
      <div style={{ display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
        <Link href="/browse" style={{ fontWeight: 600 }}>AISafetyBenchExplorer</Link>
        {user?.role === "admin" && (
          <>
            <Link href="/admin/benchmarks">Benchmarks</Link>
            <Link href="/admin/extraction">Agent Extraction</Link>
            <Link href="/admin/submissions">Community Submissions</Link>
            <Link href="/admin/models">Models</Link>
            <Link href="/admin/vocab">Vocabulary</Link>
          </>
        )}
        {user?.role === "researcher" && <Link href="/submit">Submit a Benchmark</Link>}
      </div>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        {user ? (
          <>
            <span style={{ fontSize: 12, color: "#666" }}>
              {user.email} ({user.role})
            </span>
            <NotificationBell />
            <button className="secondary" onClick={handleLogout}>Log out</button>
          </>
        ) : (
          <>
            <Link href="/login"><button className="secondary">Log in</button></Link>
            <Link href="/signup"><button>Sign up</button></Link>
          </>
        )}
      </div>
    </div>
  );
}
