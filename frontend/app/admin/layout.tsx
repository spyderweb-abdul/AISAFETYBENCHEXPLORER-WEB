// Destination path: frontend/app/admin/layout.tsx
// New file.
//
// FIX (this session): the previous session only hid admin nav links
// from non-admins in AppHeader.tsx -- that's cosmetic, not
// enforcement. Any researcher who typed /admin/benchmarks or
// /admin/extraction directly into the address bar could still see and
// use those pages, since no page under /admin/ ever checked role
// itself. Next.js App Router applies a layout.tsx to every nested
// route under its folder automatically, so this single file now gates
// EVERY /admin/* page (benchmarks, benchmarks/[id], benchmarks/new,
// submissions, extraction, audit-log, etc.) without needing to touch
// each individual page file -- including ones not read in this
// session, like /admin/extraction.
//
// Note: this is CLIENT-SIDE route protection only (checked after the
// page's JS loads), which is sufficient for this app's threat model
// (an internal admin/research tool, not a public multi-tenant SaaS)
// but is not a substitute for the backend's own require_admin
// dependency, which remains the actual security boundary -- every
// /admin/* page's data-fetching calls already hit admin-only backend
// endpoints (e.g. GET /submissions, POST /benchmarks) that return 403
// regardless of what this layout does. This layout's job is purely to
// stop a researcher from seeing the page shell/UI at all, not to be
// the security enforcement point.

"use client";

import { ReactNode, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Cookies from "js-cookie";
import { UserOut, fetchMe } from "../../lib/api";

export default function AdminLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [allowed, setAllowed] = useState(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    const token = Cookies.get("access_token");
    if (!token) {
      router.replace("/login");
      return;
    }
    fetchMe()
      .then((u: UserOut) => {
        if (u.role !== "admin") {
          router.replace("/submit");
          return;
        }
        setAllowed(true);
      })
      .catch(() => {
        Cookies.remove("access_token");
        router.replace("/login");
      })
      .finally(() => setChecking(false));
  }, [router]);

  if (checking) {
    return <div className="container"><p>Checking access...</p></div>;
  }
  if (!allowed) {
    // A redirect is already in-flight from the effect above -- render
    // nothing rather than a flash of admin content.
    return null;
  }
  return <>{children}</>;
}
