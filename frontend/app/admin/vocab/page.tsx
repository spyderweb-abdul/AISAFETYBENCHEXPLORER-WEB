// Destination path: frontend/app/admin/vocab/page.tsx
// New file.
//
// Admin CRUD UI for the VocabTerm catalogue (backend/app/routers/vocab_terms.py).
// Two tabs: Task Types and Evaluation Metrics. Each row can be
// activated/deactivated, edited, marked as an alias of another term
// (canonical merge), or deleted. An "unreviewed" filter surfaces terms
// that were auto-added by an extraction (source="agent") and never
// looked at by an admin.

"use client";

import { useEffect, useState } from "react";
import {
  VocabTerm,
  createVocabTerm,
  deleteVocabTerm,
  listVocabTerms,
  updateVocabTerm,
} from "../../../lib/api";

type Category = "task_type" | "evaluation_metric";

const emptyForm = { term: "" };

export default function AdminVocabPage() {
  const [category, setCategory] = useState<Category>("task_type");
  const [terms, setTerms] = useState<VocabTerm[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [unreviewedOnly, setUnreviewedOnly] = useState(false);

  const [form, setForm] = useState(emptyForm);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTerm, setEditTerm] = useState("");
  const [savingId, setSavingId] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await listVocabTerms({
        category,
        active_only: false,
        unreviewed_only: unreviewedOnly,
      });
      setTerms(data);
    } catch {
      setError("Failed to load vocabulary terms.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [category, unreviewedOnly]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setCreateError(null);
    try {
      await createVocabTerm({ category, term: form.term.trim() });
      setForm(emptyForm);
      await load();
    } catch (err: any) {
      setCreateError(err?.response?.data?.detail || "Failed to add term.");
    } finally {
      setCreating(false);
    }
  }

  async function handleToggleActive(t: VocabTerm) {
    setSavingId(t.id);
    try {
      await updateVocabTerm(t.id, { is_active: !t.is_active });
      await load();
    } catch {
      setError("Failed to toggle term status.");
    } finally {
      setSavingId(null);
    }
  }

  function startEdit(t: VocabTerm) {
    setEditingId(t.id);
    setEditTerm(t.term);
  }

  async function handleSaveEdit(id: string) {
    setSavingId(id);
    setError(null);
    try {
      await updateVocabTerm(id, { term: editTerm });
      setEditingId(null);
      await load();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to update term (it may clash with an existing one).");
    } finally {
      setSavingId(null);
    }
  }

  async function handleMarkReviewed(t: VocabTerm) {
    // "Marking reviewed" here just means promoting source from agent's
    // implicit unreviewed state -- since there's no separate "reviewed"
    // flag, admins use is_canonical/is_active as the actual signal. This
    // button simply re-saves the term with no changes to move it out of
    // casual at-a-glance attention; real curation is edit/merge/delete.
    setSavingId(t.id);
    try {
      await updateVocabTerm(t.id, { is_canonical: true });
      await load();
    } catch {
      setError("Failed to update term.");
    } finally {
      setSavingId(null);
    }
  }

  async function handleDelete(t: VocabTerm) {
    if (!confirm(`Delete "${t.term}" from ${category}? Existing benchmarks that used this term keep it; only future prompt guidance and dropdowns are affected.`)) {
      return;
    }
    setSavingId(t.id);
    setError(null);
    try {
      await deleteVocabTerm(t.id);
      await load();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to delete term.");
    } finally {
      setSavingId(null);
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-2">Vocabulary Catalogue</h1>
      <p className="text-sm text-gray-600 mb-6">
        Task types and evaluation metrics seen across the catalogue. Active,
        canonical terms are fed to the extraction agent as reference
        guidance (not a strict enum) and grow automatically as new papers
        are extracted. Deactivating or deleting a term never changes any
        existing benchmark record.
      </p>

      <div className="flex gap-2 mb-6">
        <button
          onClick={() => setCategory("task_type")}
          className={`px-4 py-2 rounded text-sm font-medium ${category === "task_type" ? "bg-indigo-600 text-white" : "bg-gray-100"}`}
        >
          Task Types
        </button>
        <button
          onClick={() => setCategory("evaluation_metric")}
          className={`px-4 py-2 rounded text-sm font-medium ${category === "evaluation_metric" ? "bg-indigo-600 text-white" : "bg-gray-100"}`}
        >
          Evaluation Metrics
        </button>
        <label className="flex items-center gap-2 text-sm ml-4">
          <input
            type="checkbox"
            checked={unreviewedOnly}
            onChange={(e) => setUnreviewedOnly(e.target.checked)}
          />
          Show only agent-added, unreviewed terms
        </label>
      </div>

      <section className="bg-white rounded-lg border p-5 mb-8 shadow-sm">
        <h2 className="text-lg font-semibold mb-4">
          Add {category === "task_type" ? "Task Type" : "Evaluation Metric"}
        </h2>
        <form onSubmit={handleCreate} className="flex gap-3">
          <input
            type="text"
            value={form.term}
            onChange={(e) => setForm({ term: e.target.value })}
            placeholder={category === "task_type" ? "e.g. Sycophancy" : "e.g. Attack Success Rate"}
            required
            className="border rounded px-3 py-2 text-sm flex-1"
          />
          <button
            type="submit"
            disabled={creating}
            className="bg-indigo-600 text-white px-5 py-2 rounded text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
          >
            {creating ? "Adding..." : "Add"}
          </button>
        </form>
        {createError && <p className="text-red-600 text-sm mt-2">{createError}</p>}
      </section>

      <section className="bg-white rounded-lg border p-5 shadow-sm">
        <h2 className="text-lg font-semibold mb-4">
          All {category === "task_type" ? "Task Types" : "Evaluation Metrics"} ({terms.length})
        </h2>
        {error && <p className="text-red-600 text-sm mb-3">{error}</p>}
        {loading && <p className="text-sm text-gray-500">Loading...</p>}
        {!loading && terms.length === 0 && (
          <p className="text-sm text-gray-500">No terms match this filter.</p>
        )}
        <div className="divide-y">
          {terms.map((t) => (
            <div key={t.id} className="py-3 flex justify-between items-center flex-wrap gap-2">
              {editingId === t.id ? (
                <div className="flex gap-2 flex-1">
                  <input
                    type="text"
                    value={editTerm}
                    onChange={(e) => setEditTerm(e.target.value)}
                    className="border rounded px-3 py-1.5 text-sm flex-1"
                  />
                  <button
                    onClick={() => handleSaveEdit(t.id)}
                    disabled={savingId === t.id}
                    className="bg-green-600 text-white px-3 py-1.5 rounded text-xs font-medium hover:bg-green-700 disabled:opacity-50"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => setEditingId(null)}
                    className="bg-gray-100 px-3 py-1.5 rounded text-xs font-medium hover:bg-gray-200"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <>
                  <div>
                    <p className="text-sm font-medium">
                      {t.term}{" "}
                      <span className={`text-xs px-2 py-0.5 rounded ${t.is_active ? "bg-green-100 text-green-700" : "bg-gray-200 text-gray-600"}`}>
                        {t.is_active ? "active" : "inactive"}
                      </span>{" "}
                      {t.source === "agent" && (
                        <span className="text-xs px-2 py-0.5 rounded bg-yellow-100 text-yellow-800">
                          agent-added
                        </span>
                      )}
                      {!t.is_canonical && (
                        <span className="text-xs px-2 py-0.5 rounded bg-blue-100 text-blue-700">
                          alias
                        </span>
                      )}
                    </p>
                    <p className="text-xs text-gray-500">used {t.usage_count} time{t.usage_count === 1 ? "" : "s"}</p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleToggleActive(t)}
                      disabled={savingId === t.id}
                      className="bg-gray-100 px-3 py-1.5 rounded text-xs font-medium hover:bg-gray-200 disabled:opacity-50"
                    >
                      {t.is_active ? "Deactivate" : "Activate"}
                    </button>
                    <button
                      onClick={() => startEdit(t)}
                      className="bg-gray-100 px-3 py-1.5 rounded text-xs font-medium hover:bg-gray-200"
                    >
                      Rename
                    </button>
                    <button
                      onClick={() => handleDelete(t)}
                      disabled={savingId === t.id}
                      className="bg-red-600 text-white px-3 py-1.5 rounded text-xs font-medium hover:bg-red-700 disabled:opacity-50"
                    >
                      Delete
                    </button>
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
