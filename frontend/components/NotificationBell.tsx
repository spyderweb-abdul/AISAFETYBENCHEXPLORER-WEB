// Destination path: frontend/components/NotificationBell.tsx
// Replaces the existing file in full. (Supersedes the earlier draft:
// adds a visible "For admins" / "For you as submitter" audience tag
// per notification, so even a single test account that historically
// received both kinds of notifications -- from before the
// require_researcher role split existed -- can immediately tell which
// context each one belongs to, instead of them looking
// interchangeable. This directly addresses "roles need to be clearly
// defined" at the notification level, independent of the backend
// cleanup script for actually removing stale mismatched rows.)

"use client";

import { useEffect, useState } from "react";
import Cookies from "js-cookie";
import Link from "next/link";
import {
  AppNotification,
  getUnreadNotificationCount,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "../lib/api";

const NOTIFICATION_AUDIENCE_LABEL: Record<string, { label: string; color: string }> = {
  submission_queued_for_review: { label: "For admins", color: "#3730a3" },
  submission_approved: { label: "For you (submitter)", color: "#166534" },
  submission_declined: { label: "For you (submitter)", color: "#991b1b" },
  submission_needs_reextraction: { label: "For you (submitter)", color: "#78350f" },
  submission_failed_extraction: { label: "For you (submitter)", color: "#991b1b" },
};

export default function NotificationBell() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoggedIn(!!Cookies.get("access_token"));
  }, []);

  useEffect(() => {
    if (!loggedIn) return;
    let cancelled = false;
    async function poll() {
      try {
        const count = await getUnreadNotificationCount();
        if (!cancelled) setUnreadCount(count);
      } catch {
        // Silently ignore -- a failed poll should not disrupt the page.
      }
    }
    poll();
    const interval = setInterval(poll, 30000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [loggedIn]);

  async function toggleOpen() {
    const next = !open;
    setOpen(next);
    if (next) {
      setLoading(true);
      try {
        const data = await listNotifications();
        setNotifications(data);
      } finally {
        setLoading(false);
      }
    }
  }

  async function handleMarkRead(id: string) {
    await markNotificationRead(id);
    setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)));
    setUnreadCount((c) => Math.max(0, c - 1));
  }

  async function handleMarkAllRead() {
    await markAllNotificationsRead();
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    setUnreadCount(0);
  }

  if (!loggedIn) return null;

  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      <button className="secondary" onClick={toggleOpen} style={{ position: "relative" }}>
        Notifications
        {unreadCount > 0 && (
          <span
            style={{
              position: "absolute", top: -6, right: -6, background: "#dc2626",
              color: "white", borderRadius: "50%", fontSize: 11, padding: "1px 6px",
            }}
          >
            {unreadCount}
          </span>
        )}
      </button>
      {open && (
        <div
          style={{
            position: "absolute", right: 0, top: "110%", width: 360, maxHeight: 420,
            overflowY: "auto", background: "white", border: "1px solid #e5e5e5",
            borderRadius: 8, boxShadow: "0 4px 12px rgba(0,0,0,0.1)", zIndex: 50, padding: 8,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <strong style={{ fontSize: 13 }}>Notifications</strong>
            <button className="secondary" onClick={handleMarkAllRead} style={{ fontSize: 11 }}>
              Mark all read
            </button>
          </div>
          {loading ? (
            <p style={{ fontSize: 12, color: "#666" }}>Loading...</p>
          ) : notifications.length === 0 ? (
            <p style={{ fontSize: 12, color: "#666" }}>No notifications yet.</p>
          ) : (
            notifications.map((n) => {
              const audience = NOTIFICATION_AUDIENCE_LABEL[n.notification_type];
              return (
                <div
                  key={n.id}
                  style={{
                    padding: 8, borderBottom: "1px solid #f0f0f0",
                    background: n.is_read ? "white" : "#fef9e7",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
                    <div style={{ fontSize: 12, fontWeight: n.is_read ? 400 : 600 }}>{n.title}</div>
                    {audience && (
                      <span
                        style={{
                          fontSize: 10, whiteSpace: "nowrap", color: "white",
                          background: audience.color, borderRadius: 4, padding: "1px 6px",
                        }}
                      >
                        {audience.label}
                      </span>
                    )}
                  </div>
                  {n.body && <div style={{ fontSize: 11, color: "#666", marginTop: 2 }}>{n.body}</div>}
                  <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
                    {n.link_path ? (
                      <Link href={n.link_path} style={{ fontSize: 11 }}>View &rarr;</Link>
                    ) : <span />}
                    {!n.is_read && (
                      <button
                        className="secondary"
                        style={{ fontSize: 10 }}
                        onClick={() => handleMarkRead(n.id)}
                      >
                        Mark read
                      </button>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
