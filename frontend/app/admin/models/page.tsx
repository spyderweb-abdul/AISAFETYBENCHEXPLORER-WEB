// Destination path: frontend/app/admin/models/page.tsx
// New file.
//
// Admin CRUD UI for the ModelOption catalogue (backend/app/routers/models.py).
// Lists all models (including inactive ones, unlike the dropdowns
// elsewhere which default to active_only=true), and lets an admin add,
// edit, toggle active/inactive, or delete a model. Deleting or
// deactivating a model here never affects historical ExtractionJob/
// Submission records, since model_used on those tables is a plain
// string column, not a foreign key to this table.

"use client";

import { useEffect, useState } from "react";
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

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Model Catalogue</h1>
      <p className="text-sm text-gray-600 mb-6">
        Models listed here (when active) appear in the Agent Extraction Panel
        and the community submissions re-extract dropdown. Deactivating or
        deleting a model never changes any job or submission that already
        used it -- those keep the exact model string they were run with.
      </p>

      <section className="bg-white rounded-lg border p-5 mb-8 shadow-sm">
        <h2 className="text-lg font-semibold mb-4">Add Model</h2>
        <form onSubmit={handleCreate} className="space-y-3">
          <div className="flex gap-3 flex-wrap">
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium">Provider</label>
              <select
                value={form.provider}
                onChange={(e) => setForm((f) => ({ ...f, provider: e.target.value }))}
                className="border rounded px-3 py-2 text-sm"
              >
                {PROVIDERS.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1 flex-1 min-w-56">
              <label className="text-sm font-medium">Identifier (provider/model)</label>
              <input
                type="text"
                value={form.identifier}
                onChange={(e) => setForm((f) => ({ ...f, identifier: e.target.value }))}
                placeholder="openai/gpt-4o"
                required
                className="border rounded px-3 py-2 text-sm"
              />
            </div>
            <div className="flex flex-col gap-1 flex-1 min-w-48">
              <label className="text-sm font-medium">Display name (optional)</label>
              <input
                type="text"
                value={form.display_name}
                onChange={(e) => setForm((f) => ({ ...f, display_name: e.target.value }))}
                placeholder="GPT-4o"
                className="border rounded px-3 py-2 text-sm"
              />
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium">Notes (optional)</label>
            <input
              type="text"
              value={form.notes}
              onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
              placeholder="e.g. cost tier, rate limits, when to prefer this model"
              className="border rounded px-3 py-2 text-sm"
            />
          </div>
          {createError && <p className="text-red-600 text-sm">{createError}</p>}
          <button
            type="submit"
            disabled={creating}
            className="bg-indigo-600 text-white px-5 py-2 rounded text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
          >
            {creating ? "Adding..." : "Add Model"}
          </button>
        </form>
      </section>

      <section className="bg-white rounded-lg border p-5 shadow-sm">
        <h2 className="text-lg font-semibold mb-4">All Models</h2>
        {error && <p className="text-red-600 text-sm mb-3">{error}</p>}
        {loading && <p className="text-sm text-gray-500">Loading...</p>}
        {!loading && models.length === 0 && (
          <p className="text-sm text-gray-500">No models yet -- add one above.</p>
        )}
        <div className="divide-y">
          {models.map((m) => (
            <div key={m.id} className="py-3">
              {editingId === m.id ? (
                <div className="flex flex-col gap-2">
                  <div className="flex gap-3 flex-wrap">
                    <select
                      value={editForm.provider}
                      onChange={(e) => setEditForm((f) => ({ ...f, provider: e.target.value }))}
                      className="border rounded px-3 py-1.5 text-sm"
                    >
                      {PROVIDERS.map((p) => <option key={p} value={p}>{p}</option>)}
                    </select>
                    <input
                      type="text"
                      value={editForm.identifier || ""}
                      onChange={(e) => setEditForm((f) => ({ ...f, identifier: e.target.value }))}
                      className="border rounded px-3 py-1.5 text-sm flex-1 min-w-48"
                    />
                    <input
                      type="text"
                      value={editForm.display_name || ""}
                      onChange={(e) => setEditForm((f) => ({ ...f, display_name: e.target.value }))}
                      placeholder="Display name"
                      className="border rounded px-3 py-1.5 text-sm flex-1 min-w-40"
                    />
                  </div>
                  <input
                    type="text"
                    value={editForm.notes || ""}
                    onChange={(e) => setEditForm((f) => ({ ...f, notes: e.target.value }))}
                    placeholder="Notes"
                    className="border rounded px-3 py-1.5 text-sm"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleSaveEdit(m.id)}
                      disabled={savingId === m.id}
                      className="bg-green-600 text-white px-4 py-1.5 rounded text-xs font-medium hover:bg-green-700 disabled:opacity-50"
                    >
                      Save
                    </button>
                    <button
                      onClick={() => setEditingId(null)}
                      className="bg-gray-100 px-4 py-1.5 rounded text-xs font-medium hover:bg-gray-200"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex justify-between items-center flex-wrap gap-2">
                  <div>
                    <p className="text-sm font-medium">
                      {m.display_name ? `${m.display_name} ` : ""}
                      <span className="text-gray-500 font-normal">({m.identifier})</span>
                      {" "}
                      <span
                        className={`text-xs px-2 py-0.5 rounded ${m.is_active ? "bg-green-100 text-green-700" : "bg-gray-200 text-gray-600"}`}
                      >
                        {m.is_active ? "active" : "inactive"}
                      </span>
                    </p>
                    <p className="text-xs text-gray-500">
                      Provider: {m.provider}
                      {m.notes ? ` | ${m.notes}` : ""}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleToggleActive(m)}
                      disabled={savingId === m.id}
                      className="bg-gray-100 px-3 py-1.5 rounded text-xs font-medium hover:bg-gray-200 disabled:opacity-50"
                    >
                      {m.is_active ? "Deactivate" : "Activate"}
                    </button>
                    <button
                      onClick={() => startEdit(m)}
                      className="bg-gray-100 px-3 py-1.5 rounded text-xs font-medium hover:bg-gray-200"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDelete(m)}
                      disabled={savingId === m.id}
                      className="bg-red-600 text-white px-3 py-1.5 rounded text-xs font-medium hover:bg-red-700 disabled:opacity-50"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
