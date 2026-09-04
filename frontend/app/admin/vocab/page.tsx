"use client";

import { Fragment, useEffect, useState } from "react";
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

  const PAGE_SIZE = 20;

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">("all");
  const [page, setPage] = useState(1);

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
  async function updateFilters(
    nextSearch = search,
    nextStatus = statusFilter,
  ) {
    setSearch(nextSearch);
    setStatusFilter(nextStatus);
    setPage(1);
  }

  async function changeCategory(nextCategory: Category) {
    setCategory(nextCategory);
    setSearch("");
    setStatusFilter("all");
    setPage(1);
  }

  const activeCount = terms.filter((term) => term.is_active).length;
  const agentAddedCount = terms.filter((term) => term.source === "agent").length;

  const filteredTerms = terms.filter((term) => {
    const matchesSearch = term.term.toLowerCase().includes(search.trim().toLowerCase());

    const matchesStatus =
      statusFilter === "all" ||
      (statusFilter === "active" && term.is_active) ||
      (statusFilter === "inactive" && !term.is_active);

    return matchesSearch && matchesStatus;
  });

  const pageCount = Math.max(1, Math.ceil(filteredTerms.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);

  const visibleTerms = filteredTerms.slice(
    (safePage - 1) * PAGE_SIZE,
    safePage * PAGE_SIZE,
  );

  return (
    <div className="vocab-page">
      <div className="vocab-page-header">
        <div>
          <h1>Vocabulary Catalogue</h1>
          <p>
            Curate task types and evaluation metrics used throughout the benchmark
            catalogue. Active canonical terms guide extraction without changing
            historical benchmark records.
          </p>
        </div>

        <div className="vocab-summary">
          <span><strong>{activeCount}</strong> active</span>
          <span><strong>{terms.length}</strong> total</span>
          <span><strong>{agentAddedCount}</strong> agent-added</span>
        </div>
      </div>

      <div className="vocab-controls">
        <div className="vocab-tabs" role="tablist" aria-label="Vocabulary category">
          <button
            className={category === "task_type" ? "tab-button active" : "tab-button"}
            onClick={() => changeCategory("task_type")}
            type="button"
            role="tab"
            aria-selected={category === "task_type"}
          >
            Task Types
          </button>

          <button
            className={category === "evaluation_metric" ? "tab-button active" : "tab-button"}
            onClick={() => changeCategory("evaluation_metric")}
            type="button"
            role="tab"
            aria-selected={category === "evaluation_metric"}
          >
            Evaluation Metrics
          </button>
        </div>

        <label className="vocab-review-filter">
          <input
            type="checkbox"
            checked={unreviewedOnly}
            onChange={(e) => {
              setUnreviewedOnly(e.target.checked);
              setPage(1);
            }}
          />
          Show agent-added terms only
        </label>
      </div>

      <section className="card">
        <div className="vocab-section-header">
          <div>
            <h2>Add {category === "task_type" ? "Task Type" : "Evaluation Metric"}</h2>
            <p>Add a controlled term for future curation and extraction guidance.</p>
          </div>

          <button
            className="secondary"
            onClick={() => setShowCreateForm((value) => !value)}
            type="button"
            aria-expanded={showCreateForm}
          >
            {showCreateForm ? "Collapse" : "Add Term"}
          </button>
        </div>

        {showCreateForm && (
          <form className="vocab-create-row" onSubmit={handleCreate}>
            <div className="vocab-create-field">
              <label htmlFor="vocab-term">Term</label>
              <input
                id="vocab-term"
                type="text"
                value={form.term}
                onChange={(e) => setForm({ term: e.target.value })}
                placeholder={
                  category === "task_type"
                    ? "e.g. Sycophancy"
                    : "e.g. Attack Success Rate"
                }
                required
              />
            </div>

            <div className="vocab-create-action">
              <span>Action</span>
              <button type="submit" disabled={creating}>
                {creating ? "Adding..." : "Add Term"}
              </button>
            </div>
          </form>
        )}

        {createError && <p className="error">{createError}</p>}
      </section>

      <section className="card">
        <h2 className="detail-section-title">
          All {category === "task_type" ? "Task Types" : "Evaluation Metrics"} ({terms.length})
        </h2>
        {error && <p className="error">{error}</p>}
        {loading && <p className="muted-copy">Loading...</p>}
        {!loading && terms.length === 0 && (
          <p className="muted-copy">No terms match this filter.</p>
        )}
        <div>
          <div className="vocab-toolbar">
            <input
              type="search"
              value={search}
              onChange={(e) => updateFilters(e.target.value, statusFilter)}
              placeholder="Search terms"
              aria-label="Search vocabulary terms"
            />

            <select
              value={statusFilter}
              onChange={(e) =>
                updateFilters(
                  search,
                  e.target.value as "all" | "active" | "inactive",
                )
              }
              aria-label="Filter vocabulary terms by status"
            >
              <option value="all">All statuses</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>

            <button className="secondary" onClick={load} type="button">
              Refresh
            </button>
          </div>

          <div className="vocab-table-scroll">
            <table className="vocab-table">
              <thead>
                <tr>
                  <th>Term</th>
                  <th>Status</th>
                  <th>Origin</th>
                  <th>Canonical</th>
                  <th>Usage</th>
                  <th>Actions</th>
                </tr>
              </thead>

              <tbody>
                {visibleTerms.map((term) => {
                  const isEditing = editingId === term.id;

                  return (
                    <Fragment key={term.id}>
                      <tr>
                        <td><strong>{term.term}</strong></td>

                        <td>
                          <span className={term.is_active ? "vocab-status vocab-status--active" : "vocab-status vocab-status--inactive"}>
                            {term.is_active ? "Active" : "Inactive"}
                          </span>
                        </td>

                        <td>
                          <span className={term.source === "agent" ? "vocab-origin vocab-origin--agent" : "vocab-origin"}>
                            {term.source === "agent" ? "Agent-added" : term.source}
                          </span>
                        </td>

                        <td>{term.is_canonical ? "Canonical" : "Alias"}</td>

                        <td>{term.usage_count}</td>

                        <td>
                          <div className="vocab-row-actions">
                            {term.source === "agent" && !term.is_canonical && (
                              <button
                                className="secondary"
                                type="button"
                                onClick={() => handleMarkReviewed(term)}
                                disabled={savingId === term.id}
                              >
                                Review
                              </button>
                            )}

                            <button
                              className="secondary"
                              type="button"
                              onClick={() => handleToggleActive(term)}
                              disabled={savingId === term.id}
                            >
                              {term.is_active ? "Deactivate" : "Activate"}
                            </button>

                            <button
                              className="secondary"
                              type="button"
                              onClick={() => isEditing ? setEditingId(null) : startEdit(term)}
                            >
                              {isEditing ? "Close" : "Rename"}
                            </button>

                            <button
                              className="danger"
                              type="button"
                              onClick={() => handleDelete(term)}
                              disabled={savingId === term.id}
                            >
                              Delete
                            </button>
                          </div>
                        </td>
                      </tr>

                      {isEditing && (
                        <tr className="vocab-edit-row">
                          <td colSpan={6}>
                            <div className="vocab-edit-form">
                              <div className="field">
                                <label htmlFor={`edit-term-${term.id}`}>Term</label>
                                <input
                                  id={`edit-term-${term.id}`}
                                  value={editTerm}
                                  onChange={(e) => setEditTerm(e.target.value)}
                                />
                              </div>

                              <button
                                className="success"
                                type="button"
                                onClick={() => handleSaveEdit(term.id)}
                                disabled={savingId === term.id}
                              >
                                {savingId === term.id ? "Saving..." : "Save"}
                              </button>

                              <button
                                className="secondary"
                                type="button"
                                onClick={() => setEditingId(null)}
                              >
                                Cancel
                              </button>
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="vocab-pagination">
            <span>
              Page {safePage} of {pageCount}
            </span>

            <div>
              <button
                className="secondary"
                disabled={safePage === 1}
                onClick={() => setPage((current) => current - 1)}
                type="button"
              >
                Previous
              </button>

              <button
                className="secondary"
                disabled={safePage === pageCount}
                onClick={() => setPage((current) => current + 1)}
                type="button"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
