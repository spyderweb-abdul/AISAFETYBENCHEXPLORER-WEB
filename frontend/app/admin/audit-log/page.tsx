"use client";

import { useEffect, useState } from "react";
import { AuditLogEntry, fetchAuditLog } from "../../../lib/api";

export default function AuditLogPage() {
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);

  useEffect(() => { fetchAuditLog().then(setEntries); }, []);

  return (
    <div className="container">
      <h2>Audit Log</h2>
      <div className="card">
        <table>
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
                <td><pre style={{ whiteSpace: "pre-wrap", fontSize: 11 }}>{JSON.stringify(e.diff, null, 2)}</pre></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
