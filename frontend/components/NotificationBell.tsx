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

import { useEffect, useRef, useState } from "react";
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
  const triggerRef = useRef<HTMLButtonElement>(null);

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

  useEffect(() => {
    if (!open) return;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open]);

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
    <div className="notification-menu">
      <button
        ref={triggerRef}
        className="secondary notification-trigger"
        onClick={toggleOpen}
        type="button"
        aria-expanded={open}
        aria-controls="notification-panel"
      >
        Notifications
        {unreadCount > 0 && (
          <span className="notification-count" aria-label={`${unreadCount} unread notifications`}>
            {unreadCount}
          </span>
        )}
      </button>
      {open && (
        <div
          id="notification-panel"
          className="notification-panel"
          role="dialog"
          aria-label="Notifications"
        >
          <div className="notification-panel-header">
            <strong>Notifications</strong>
            <button className="secondary notification-small-button" onClick={handleMarkAllRead} type="button">
              Mark all read
            </button>
          </div>
          {loading ? (
            <p className="notification-empty">Loading...</p>
          ) : notifications.length === 0 ? (
            <p className="notification-empty">No notifications yet.</p>
          ) : (
            notifications.map((n) => {
              const audience = NOTIFICATION_AUDIENCE_LABEL[n.notification_type];
              return (
                <div
                  key={n.id}
                  className={n.is_read ? "notification-item" : "notification-item notification-item-unread"}
                >
                  <div className="notification-item-heading">
                    <div className={n.is_read ? "notification-title" : "notification-title notification-title-unread"}>{n.title}</div>
                    {audience && (
                      <span
                        className="notification-audience"
                        style={{ backgroundColor: audience.color }}
                      >
                        {audience.label}
                      </span>
                    )}
                  </div>
                  {n.body && <div className="notification-body">{n.body}</div>}
                  <div className="notification-item-actions">
                    {n.link_path ? (
                      <Link href={n.link_path} className="notification-view-link" onClick={() => setOpen(false)}>View →</Link>
                    ) : <span />}
                    {!n.is_read && (
                      <button
                        className="secondary"
                        onClick={() => handleMarkRead(n.id)}
                        type="button"
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
