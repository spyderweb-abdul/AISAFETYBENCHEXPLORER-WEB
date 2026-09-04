"use client";

import { useEffect, useState } from "react";
import { AuditLogEntry, fetchAuditLog } from "../../../lib/api";

export default function AuditLogPage() {
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);

  useEffect(() => { fetchAuditLog().then(setEntries); }, []);

  return (
    <main className="admin-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Catalogue administration</p>
          <h1>Audit log</h1>
          <p className="page-description">A read-only record of catalogue and configuration changes.</p>
        </div>
      </header>
      <div className="card">
        <div className="table-scroll"><table>
          <thead>
            <tr><th>Time</th><th>Table</th><th>Action</th><th>Record ID</th><th>Diff</th></tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.id}>
                <td>{new Date(e.created_at).toLocaleString()}</td>
                <td>{e.table_name}</td>
                <td>{e.action}</td>
                <td>{e.record_id.slice(0, 8)}...</td>
                <td><pre className="code-block">{JSON.stringify(e.diff, null, 2)}</pre></td>
              </tr>
            ))}
          </tbody>
        </table></div>
      </div>
    </main>
  );
}
