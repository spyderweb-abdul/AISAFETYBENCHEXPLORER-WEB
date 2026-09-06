"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  AppNotification,
  NotificationPage,
  listNotificationPage,
  markAllNotificationsRead,
  markNotificationRead,
} from "../../lib/api";

const PAGE_SIZE = 20;

const NOTIFICATION_AUDIENCE_LABEL: Record<string, { label: string; color: string }> = {
  submission_queued_for_review: { label: "For admins", color: "#3730a3" },
  submission_approved: { label: "For you (submitter)", color: "#166534" },
  submission_declined: { label: "For you (submitter)", color: "#991b1b" },
  submission_needs_reextraction: { label: "For you (submitter)", color: "#78350f" },
  submission_failed_extraction: { label: "For you (submitter)", color: "#991b1b" },
};

function formatTimestamp(value: string) {
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(timestamp);
}

export default function NotificationsPage() {
  const [page, setPage] = useState(1);
  const [notificationPage, setNotificationPage] = useState<NotificationPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadPage = useCallback(async (pageNumber: number) => {
    setLoading(true);
    setError(null);
    try {
      setNotificationPage(await listNotificationPage(pageNumber, PAGE_SIZE));
    } catch {
      setError("Unable to load notification history. Please try again.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPage(page);
  }, [loadPage, page]);

  async function handleMarkRead(notification: AppNotification) {
    if (notification.is_read) return;
    setBusy(true);
    setError(null);
    try {
      await markNotificationRead(notification.id);
      setNotificationPage((current) => current && {
        ...current,
        items: current.items.map((item) => item.id === notification.id ? { ...item, is_read: true } : item),
      });
    } catch {
      setError("Unable to mark this notification as read. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function handleMarkAllRead() {
    setBusy(true);
    setError(null);
    try {
      await markAllNotificationsRead();
      setNotificationPage((current) => current && {
        ...current,
        items: current.items.map((item) => ({ ...item, is_read: true })),
      });
    } catch {
      setError("Unable to mark all notifications as read. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  const total = notificationPage?.total ?? 0;
  const totalPages = notificationPage?.total_pages ?? 1;

  return (
    <main className="container notifications-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Personal inbox</p>
          <h1>Notifications</h1>
          <p className="page-description">Review your complete activity trail, including submission and review updates.</p>
        </div>
      </header>

      {error && <p className="error" role="alert">{error}</p>}

      <section className="card notification-history-card" aria-labelledby="notification-history-heading">
        <div className="notification-history-toolbar">
          <div>
            <h2 id="notification-history-heading">Notification trail</h2>
            <p>{total === 1 ? "1 notification" : `${total} notifications`}</p>
          </div>
          <div className="notification-history-actions">
            <button className="secondary" type="button" onClick={() => loadPage(page)} disabled={loading || busy}>Refresh</button>
            <button type="button" onClick={handleMarkAllRead} disabled={loading || busy || total === 0}>Mark all read</button>
          </div>
        </div>

        {loading ? (
          <div className="browse-state" role="status">Loading notifications.</div>
        ) : !notificationPage || notificationPage.items.length === 0 ? (
          <div className="notification-history-empty">No notifications on this page.</div>
        ) : (
          <div className="notification-history-list">
            {notificationPage.items.map((notification) => {
              const audience = NOTIFICATION_AUDIENCE_LABEL[notification.notification_type];
              return (
                <article
                  key={notification.id}
                  className={notification.is_read ? "notification-history-item" : "notification-history-item notification-history-item-unread"}
                >
                  <div className="notification-history-item-header">
                    <div>
                      <h3>{notification.title}</h3>
                      <time dateTime={notification.created_at}>{formatTimestamp(notification.created_at)}</time>
                    </div>
                    {audience && <span className="notification-audience" style={{ backgroundColor: audience.color }}>{audience.label}</span>}
                  </div>
                  {notification.body && <p>{notification.body}</p>}
                  <div className="notification-history-item-actions">
                    {notification.link_path ? <Link href={notification.link_path}>View related item →</Link> : <span />}
                    {!notification.is_read && <button className="secondary" type="button" onClick={() => handleMarkRead(notification)} disabled={busy}>Mark read</button>}
                  </div>
                </article>
              );
            })}
          </div>
        )}

        {!loading && totalPages > 1 && (
          <nav className="notification-history-pagination" aria-label="Notification page navigation">
            <span>Page {page} of {totalPages}</span>
            <div>
              <button className="secondary" type="button" onClick={() => setPage((current) => current - 1)} disabled={page <= 1 || busy}>Previous</button>
              <button className="secondary" type="button" onClick={() => setPage((current) => current + 1)} disabled={page >= totalPages || busy}>Next</button>
            </div>
          </nav>
        )}
      </section>
    </main>
  );
}
