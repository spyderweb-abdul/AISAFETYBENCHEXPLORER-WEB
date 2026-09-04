"use client";

import { Fragment, useEffect, useState } from "react";
import {
  ModelOption,
  createModel,
  deleteModel,
  listModels,
  updateModel,
} from "../../../lib/api";

const PROVIDERS = ["openai", "anthropic", "ollama"];

const emptyForm = {
  identifier: "",
  provider: "openai",
  display_name: "",
  notes: "",
};

export default function AdminModelsPage() {
  const [models, setModels] = useState<ModelOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState(emptyForm);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<Partial<ModelOption>>({});
  const [savingId, setSavingId] = useState<string | null>(null);

  const PAGE_SIZE = 15;

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">("all");
  const [providerFilter, setProviderFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await listModels(false);
      setModels(data);
    } catch {
      setError("Failed to load models.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setCreateError(null);
    try {
      await createModel({
        identifier: form.identifier.trim(),
        provider: form.provider,
        display_name: form.display_name.trim() || undefined,
        notes: form.notes.trim() || undefined,
      });
      setForm(emptyForm);
      await load();
    } catch (err: any) {
      setCreateError(err?.response?.data?.detail || "Failed to create model.");
    } finally {
      setCreating(false);
    }
  }

  function startEdit(m: ModelOption) {
    setEditingId(m.id);
    setEditForm({
      identifier: m.identifier,
      provider: m.provider,
      display_name: m.display_name || "",
      notes: m.notes || "",
      is_active: m.is_active,
    });
  }

  async function handleSaveEdit(id: string) {
    setSavingId(id);
    setError(null);
    try {
      await updateModel(id, {
        identifier: editForm.identifier,
        provider: editForm.provider,
        display_name: editForm.display_name || null,
        notes: editForm.notes || null,
        is_active: editForm.is_active,
      });
      setEditingId(null);
      await load();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to update model.");
    } finally {
      setSavingId(null);
    }
  }

  async function handleToggleActive(m: ModelOption) {
    setSavingId(m.id);
    setError(null);
    try {
      await updateModel(m.id, { is_active: !m.is_active });
      await load();
    } catch {
      setError("Failed to toggle model status.");
    } finally {
      setSavingId(null);
    }
  }

  async function handleDelete(m: ModelOption) {
    if (!confirm(`Delete model "${m.identifier}"? This cannot be undone (existing jobs that used it keep their record; only future dropdowns are affected).`)) {
      return;
    }
    setSavingId(m.id);
    setError(null);
    try {
      await deleteModel(m.id);
      await load();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to delete model.");
    } finally {
      setSavingId(null);
    }
  }

  async function updateFilters(
    nextStatus = statusFilter,
    nextProvider = providerFilter,
    nextSearch = search,
  ) {
    setStatusFilter(nextStatus);
    setProviderFilter(nextProvider);
    setSearch(nextSearch);
    setPage(1);
  }

  const activeCount = models.filter((model) => model.is_active).length;

  const filteredModels = models.filter((model) => {
    const matchesStatus =
      statusFilter === "all" ||
      (statusFilter === "active" && model.is_active) ||
      (statusFilter === "inactive" && !model.is_active);

    const matchesProvider =
      providerFilter === "all" || model.provider === providerFilter;

    const query = search.trim().toLowerCase();
    const matchesSearch =
      !query ||
      model.identifier.toLowerCase().includes(query) ||
      (model.display_name || "").toLowerCase().includes(query) ||
      (model.notes || "").toLowerCase().includes(query);

    return matchesStatus && matchesProvider && matchesSearch;
  });

  const pageCount = Math.max(1, Math.ceil(filteredModels.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);

  const visibleModels = filteredModels.slice(
    (safePage - 1) * PAGE_SIZE,
    safePage * PAGE_SIZE,
  );

  return (
    <div className="models-page">
      <div className="models-page-header">
        <div>
          <h1>Model Catalogue</h1>
          <p>
            Active models are available to new extraction and re-extraction jobs.
            Historical jobs retain their recorded model identifier.
            Models listed here (when active) appear in the Agent Extraction Panel
            and the community submissions re-extract dropdown. Deactivating or
            deleting a model never changes any job or submission that already
            used it. Those keep the exact model string they were run with.
          </p>
        </div>

        <div className="models-summary">
          <span><strong>{activeCount}</strong> active</span>
          <span><strong>{models.length}</strong> total</span>
        </div>
      </div>

      <section className="bg-white rounded-lg border p-5 mb-8 shadow-sm">
        <div className="models-section-header">
          <div>
            <h2>Add Model</h2>
            <p>Add an extraction model to the approved catalogue.</p>
          </div>

          <button
            className="secondary"
            type="button"
            onClick={() => setShowCreateForm((value) => !value)}
            aria-expanded={showCreateForm}
          >
            {showCreateForm ? "Collapse" : "Add Model"}
          </button>
        </div>
        {showCreateForm && (
          <form onSubmit={handleCreate} className="model-create-form">
            <div className="model-create-row">
              <div className="model-create-field model-create-field--provider">
                <label htmlFor="model-provider">Provider</label>
                <select
                  id="model-provider"
                  value={form.provider}
                  onChange={(e) =>
                    setForm((current) => ({
                      ...current,
                      provider: e.target.value,
                    }))
                  }
                >
                  {PROVIDERS.map((provider) => (
                    <option key={provider} value={provider}>
                      {provider}
                    </option>
                  ))}
                </select>
              </div>

              <div className="model-create-field model-create-field--identifier">
                <label htmlFor="model-identifier">Identifier</label>
                <input
                  id="model-identifier"
                  type="text"
                  value={form.identifier}
                  onChange={(e) =>
                    setForm((current) => ({
                      ...current,
                      identifier: e.target.value,
                    }))
                  }
                  placeholder="openai/gpt-4o"
                  required
                />
              </div>

              <div className="model-create-field model-create-field--display-name">
                <label htmlFor="model-display-name">Display Name</label>
                <input
                  id="model-display-name"
                  type="text"
                  value={form.display_name}
                  onChange={(e) =>
                    setForm((current) => ({
                      ...current,
                      display_name: e.target.value,
                    }))
                  }
                  placeholder="GPT-4o"
                />
              </div>

              <div className="model-create-field model-create-field--action">
                <span className="model-create-action-label">Action</span>
                <button type="submit" disabled={creating}>
                  {creating ? "Adding..." : "Add Model"}
                </button>
              </div>
            </div>

            <div className="model-create-notes">
              <label htmlFor="model-notes">Notes <span>(optional)</span></label>
              <input
                id="model-notes"
                type="text"
                value={form.notes}
                onChange={(e) =>
                  setForm((current) => ({
                    ...current,
                    notes: e.target.value,
                  }))
                }
                placeholder="Cost tier, rate limits, or preferred use case"
              />
            </div>

            {createError && <p className="error">{createError}</p>}
          </form>
        )}
      </section>

      <section className="bg-white rounded-lg border p-5 shadow-sm">
        <h2 className="text-lg font-semibold mb-4">All Models</h2>
        {error && <p className="text-red-600 text-sm mb-3">{error}</p>}
        {loading && <p className="text-sm text-gray-500">Loading...</p>}
        {!loading && models.length === 0 && (
          <p className="text-sm text-gray-500">No models yet -- add one above.</p>
        )}
        <div className="models-toolbar">
          <input
            type="search"
            value={search}
            onChange={(e) =>
              updateFilters(statusFilter, providerFilter, e.target.value)
            }
            placeholder="Search identifier, display name, or notes"
            aria-label="Search models"
          />

          <select
            value={providerFilter}
            onChange={(e) =>
              updateFilters(statusFilter, e.target.value, search)
            }
            aria-label="Filter models by provider"
          >
            <option value="all">All providers</option>
            {PROVIDERS.map((provider) => (
              <option key={provider} value={provider}>
                {provider}
              </option>
            ))}
          </select>

          <select
            value={statusFilter}
            onChange={(e) =>
              updateFilters(
                e.target.value as "all" | "active" | "inactive",
                providerFilter,
                search,
              )
            }
            aria-label="Filter models by status"
          >
            <option value="all">All statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>

          <button className="secondary" onClick={load} type="button">
            Refresh
          </button>
        </div>

        <div className="models-table-scroll">
          <table className="models-table">
            <thead>
              <tr>
                <th>Model</th>
                <th>Provider</th>
                <th>Status</th>
                <th>Notes</th>
                <th>Actions</th>
              </tr>
            </thead>

            <tbody>
              {visibleModels.map((model) => {
                const isEditing = editingId === model.id;

                return (
                  <Fragment key={model.id}>
                    <tr>
                      <td>
                        <strong>{model.display_name || model.identifier}</strong>
                        {model.display_name && (
                          <span className="model-identifier">
                            {model.identifier}
                          </span>
                        )}
                      </td>

                      <td>{model.provider}</td>

                      <td>
                        <span
                          className={
                            model.is_active
                              ? "model-status model-status--active"
                              : "model-status model-status--inactive"
                          }
                        >
                          {model.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>

                      <td className="model-notes-cell">
                        {model.notes || "No notes"}
                      </td>

                      <td>
                        <div className="model-row-actions">
                          <button
                            className="secondary"
                            type="button"
                            onClick={() => handleToggleActive(model)}
                            disabled={savingId === model.id}
                          >
                            {model.is_active ? "Deactivate" : "Activate"}
                          </button>

                          <button
                            className="secondary"
                            type="button"
                            onClick={() =>
                              isEditing ? setEditingId(null) : startEdit(model)
                            }
                          >
                            {isEditing ? "Close" : "Edit"}
                          </button>

                          <button
                            className="danger"
                            type="button"
                            onClick={() => handleDelete(model)}
                            disabled={savingId === model.id}
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>

                    {isEditing && (
                      <tr className="model-edit-row">
                        <td colSpan={5}>
                          <div className="model-edit-grid">
                            <div className="field">
                              <label>Provider</label>
                              <select
                                value={editForm.provider || "openai"}
                                onChange={(e) =>
                                  setEditForm((form) => ({
                                    ...form,
                                    provider: e.target.value,
                                  }))
                                }
                              >
                                {PROVIDERS.map((provider) => (
                                  <option key={provider} value={provider}>
                                    {provider}
                                  </option>
                                ))}
                              </select>
                            </div>

                            <div className="field">
                              <label>Identifier</label>
                              <input
                                value={editForm.identifier || ""}
                                onChange={(e) =>
                                  setEditForm((form) => ({
                                    ...form,
                                    identifier: e.target.value,
                                  }))
                                }
                              />
                            </div>

                            <div className="field">
                              <label>Display Name</label>
                              <input
                                value={editForm.display_name || ""}
                                onChange={(e) =>
                                  setEditForm((form) => ({
                                    ...form,
                                    display_name: e.target.value,
                                  }))
                                }
                              />
                            </div>

                            <div className="field model-edit-notes">
                              <label>Notes</label>
                              <input
                                value={editForm.notes || ""}
                                onChange={(e) =>
                                  setEditForm((form) => ({
                                    ...form,
                                    notes: e.target.value,
                                  }))
                                }
                              />
                            </div>

                            <div className="model-edit-actions">
                              <button
                                className="success"
                                type="button"
                                onClick={() => handleSaveEdit(model.id)}
                                disabled={savingId === model.id}
                              >
                                {savingId === model.id ? "Saving..." : "Save changes"}
                              </button>

                              <button
                                className="secondary"
                                type="button"
                                onClick={() => setEditingId(null)}
                              >
                                Cancel
                              </button>
                            </div>
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
      </section>
    </div>
  );
}
