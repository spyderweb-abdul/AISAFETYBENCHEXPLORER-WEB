"use client";

import { useEffect, useState } from "react";
import {
  EvalMetric,
  MetricsCompleteness,
  checkMetricsCompleteness,
  createMetric,
  deleteMetric,
  listMetricsForBenchmark,
  updateMetric,
} from "../lib/api";

interface Props {
  benchmarkId: string;
  benchmarkName: string;
  paperTitle: string;
  paperLink?: string | null;
}

const EMPTY_DRAFT = {
  metric_name: "",
  conceptual_description: "",
  methodological_details: "",
  mathematical_definition: "",
  differences_from_standard_definition: "",
  notes: "",
};

/**
 * Phase 2b: Sheet 2 (Evaluation Metrics Catalogue) tab on the benchmark
 * edit page. Lists/creates/edits/deletes eval_metrics rows linked to this
 * benchmark, and surfaces a Sheet 1 <-> Sheet 2 completeness warning when
 * a metric name listed in the benchmark's evaluation_metrics field has no
 * corresponding catalogue row yet (mirrors the server-side check already
 * enforced during agent extraction).
 */
export default function EvalMetricsPanel({
  benchmarkId,
  benchmarkName,
  paperTitle,
  paperLink,
}: Props) {
  const [metrics, setMetrics] = useState<EvalMetric[]>([]);
  const [completeness, setCompleteness] = useState<MetricsCompleteness | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>(EMPTY_DRAFT);
  const [showAddForm, setShowAddForm] = useState(false);
  const [saving, setSaving] = useState(false);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [metricsData, completenessData] = await Promise.all([
        listMetricsForBenchmark(benchmarkId),
        checkMetricsCompleteness(benchmarkId),
      ]);
      setMetrics(metricsData);
      setCompleteness(completenessData);
    } catch (err: any) {
      setError("Failed to load evaluation metrics.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [benchmarkId]);

  function startEdit(metric: EvalMetric) {
    setEditingId(metric.id);
    setShowAddForm(false);
    setDraft({
      metric_name: metric.metric_name,
      conceptual_description: metric.conceptual_description || "",
      methodological_details: metric.methodological_details || "",
      mathematical_definition: metric.mathematical_definition || "",
      differences_from_standard_definition: metric.differences_from_standard_definition || "",
      notes: metric.notes || "",
    });
  }

  function startAdd(prefillName?: string) {
    setEditingId(null);
    setShowAddForm(true);
    setDraft({ ...EMPTY_DRAFT, metric_name: prefillName || "" });
  }

  function cancelEdit() {
    setEditingId(null);
    setShowAddForm(false);
    setDraft(EMPTY_DRAFT);
  }

  async function saveEdit() {
    if (!editingId) return;
    setSaving(true);
    setError(null);
    try {
      await updateMetric(editingId, draft);
      cancelEdit();
      await refresh();
    } catch (err: any) {
      setError(err?.response?.data?.detail ? JSON.stringify(err.response.data.detail) : "Update failed.");
    } finally {
      setSaving(false);
    }
  }

  async function saveNew() {
    setSaving(true);
    setError(null);
    try {
      await createMetric(benchmarkId, {
        ...draft,
        benchmark_name: benchmarkName,
        paper_title: paperTitle,
        paper_link: paperLink || null,
      } as any);
      cancelEdit();
      await refresh();
    } catch (err: any) {
      setError(err?.response?.data?.detail ? JSON.stringify(err.response.data.detail) : "Create failed.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(metric: EvalMetric) {
    if (!confirm(`Delete metric "${metric.metric_name}"? This cannot be undone.`)) return;
    setError(null);
    try {
      await deleteMetric(metric.id);
      await refresh();
    } catch (err: any) {
      setError("Delete failed.");
    }
  }

  function renderDraftFields() {
    return (
      <div className="form-grid">
        <div className="field" style={{ gridColumn: "1 / -1" }}>
          <label>Metric Name (exact paper terminology)</label>
          <input
            value={draft.metric_name}
            onChange={(e) => setDraft((prev) => ({ ...prev, metric_name: e.target.value }))}
            required
          />
        </div>
        <div className="field" style={{ gridColumn: "1 / -1" }}>
          <label>Conceptual Description</label>
          <textarea
            rows={2}
            value={draft.conceptual_description}
            onChange={(e) => setDraft((prev) => ({ ...prev, conceptual_description: e.target.value }))}
          />
        </div>
        <div className="field" style={{ gridColumn: "1 / -1" }}>
          <label>Methodological Details</label>
          <textarea
            rows={2}
            value={draft.methodological_details}
            onChange={(e) => setDraft((prev) => ({ ...prev, methodological_details: e.target.value }))}
          />
        </div>
        <div className="field" style={{ gridColumn: "1 / -1" }}>
          <label>Mathematical Definition</label>
          <textarea
            rows={2}
            value={draft.mathematical_definition}
            onChange={(e) => setDraft((prev) => ({ ...prev, mathematical_definition: e.target.value }))}
          />
        </div>
        <div className="field" style={{ gridColumn: "1 / -1" }}>
          <label>Differences From Standard Definition</label>
          <textarea
            rows={2}
            value={draft.differences_from_standard_definition}
            onChange={(e) =>
              setDraft((prev) => ({ ...prev, differences_from_standard_definition: e.target.value }))
            }
          />
        </div>
        <div className="field" style={{ gridColumn: "1 / -1" }}>
          <label>Notes</label>
          <textarea
            rows={2}
            value={draft.notes}
            onChange={(e) => setDraft((prev) => ({ ...prev, notes: e.target.value }))}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="topbar">
        <h3 style={{ margin: 0 }}>Evaluation Metrics Catalogue (Sheet 2)</h3>
        {!showAddForm && !editingId && (
          <button type="button" onClick={() => startAdd()}>
            + Add Metric
          </button>
        )}
      </div>

      {completeness && !completeness.is_complete && (
        <div
          className="error"
          style={{
            background: "#fef3c7",
            color: "#92400e",
            border: "1px solid #fde68a",
            borderRadius: 6,
            padding: "10px 12px",
            marginBottom: 12,
          }}
        >
          <strong>Incomplete catalogue:</strong> the following metric name(s) are listed on this
          benchmark&apos;s Evaluation Metrics field but have no catalogue row yet:{" "}
          {completeness.missing_metric_names.map((name, i) => (
            <span key={name}>
              {i > 0 && ", "}
              <button
                type="button"
                className="secondary"
                style={{ padding: "2px 8px", fontSize: 12, marginLeft: 4 }}
                onClick={() => startAdd(name)}
              >
                + {name}
              </button>
            </span>
          ))}
        </div>
      )}

      {error && <p className="error">{error}</p>}

      {loading ? (
        <p>Loading metrics...</p>
      ) : metrics.length === 0 && !showAddForm ? (
        <p style={{ color: "#666", fontSize: 13 }}>
          No evaluation metrics catalogued for this benchmark yet.
        </p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Metric Name</th>
              <th>Conceptual Description</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {metrics.map((metric) =>
              editingId === metric.id ? (
                <tr key={metric.id}>
                  <td colSpan={3}>
                    {renderDraftFields()}
                    <button type="button" onClick={saveEdit} disabled={saving}>
                      {saving ? "Saving..." : "Save Metric"}
                    </button>{" "}
                    <button type="button" className="secondary" onClick={cancelEdit}>
                      Cancel
                    </button>
                  </td>
                </tr>
              ) : (
                <tr key={metric.id}>
                  <td>{metric.metric_name}</td>
                  <td style={{ maxWidth: 420 }}>
                    {metric.conceptual_description || <em style={{ color: "#999" }}>None</em>}
                  </td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    <button type="button" className="secondary" onClick={() => startEdit(metric)}>
                      Edit
                    </button>{" "}
                    <button type="button" className="danger" onClick={() => handleDelete(metric)}>
                      Delete
                    </button>
                  </td>
                </tr>
              )
            )}
          </tbody>
        </table>
      )}

      {showAddForm && (
        <div style={{ marginTop: 16, borderTop: "1px solid #eee", paddingTop: 16 }}>
          <h4 style={{ marginTop: 0 }}>Add Metric</h4>
          {renderDraftFields()}
          <button type="button" onClick={saveNew} disabled={saving || !draft.metric_name}>
            {saving ? "Saving..." : "Save Metric"}
          </button>{" "}
          <button type="button" className="secondary" onClick={cancelEdit}>
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}
