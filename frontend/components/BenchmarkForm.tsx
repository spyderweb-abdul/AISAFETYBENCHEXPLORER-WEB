"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Benchmark, classifyComplexity, createBenchmark, fetchVocab, listVocabTerms, updateBenchmark, Vocab
} from "../lib/api";
import { MetadataTag } from "./MetadataTags";
import TagMultiSelect from "./TagMultiSelect";

interface Props {
  initial?: Partial<Benchmark>;
  benchmarkId?: string;
}

export default function BenchmarkForm({ initial, benchmarkId }: Props) {
  const router = useRouter();
  const [vocab, setVocab] = useState<Vocab | null>(null);
  const [taskTypeOptions, setTaskTypeOptions] = useState<string[]>([]);
  const [form, setForm] = useState<Record<string, any>>({
    benchmark_name: "",
    task_type: [],
    benchmark_paper_title: "",
    release_date: "",
    description: "",
    code_dataset: "No",
    no_of_samples: "",
    created_by: "",
    entry_modalities: [],
    dev_purpose: "",
    license: "",
    evaluation_metrics: [],
    complexity_level: "Unknown",
    complexity_justification: "",
    language_support: [],
    integration_option: "NA",
    citation_range: "",
    cited_by: 0,
    code_repository: "",
    dataset_repository: "",
    paper_link: "",
    ...initial,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [signals, setSignals] = useState({
    citation_count: 0,
    cited_as_baseline_in_3plus_papers: false,
    is_community_standard: false,
    multi_hop_reasoning: false,
    adversarial_or_red_teaming: false,
    subjective_open_ended_generation: false,
    risk_critical_domain: false,
    novel_metric: false,
    complex_eval_pipeline: false,
    requires_domain_expertise: false,
    pluralistic_annotation_50plus: false,
    limited_reasoning_1_2_step: false,
    some_adversarial_testing: false,
    mixed_objective_subjective: false,
    standard_metrics_minor_adaptation: false,
    moderate_annotation_effort: false,
  });
  const [classifying, setClassifying] = useState(false);

  useEffect(() => { fetchVocab().then(setVocab); }, []);

  useEffect(() => {
    listVocabTerms({ category: "task_type", active_only: true })
      .then((terms) => setTaskTypeOptions(terms.map((t) => t.term)))
      .catch(() => setTaskTypeOptions([]));
  }, []);

  // Keep the "Run Complexity Classifier" signal in sync with the
  // Cited By field so the classifier and the citation_range display
  // (computed server-side) never disagree about the citation count.
  useEffect(() => {
    setSignals((prev) => ({ ...prev, citation_count: Number(form.cited_by) || 0 }));
  }, [form.cited_by]);

  function setField(name: string, value: any) {
    setForm((prev) => ({ ...prev, [name]: value }));
  }

  function toggleMultiValue(name: string, value: string) {
    setForm((prev) => {
      const current: string[] = prev[name] || [];
      const next = current.includes(value) ? current.filter((v) => v !== value) : [...current, value];
      return { ...prev, [name]: next };
    });
  }

  async function runClassifier() {
    setClassifying(true);
    try {
      const result = await classifyComplexity({ ...signals, citation_count: form.cited_by || 0 });
      setField("complexity_level", result.complexity_level);
      setField("complexity_justification", result.justification);
    } finally {
      setClassifying(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      // citation_range is excluded here too -- the backend always
      // recomputes it from cited_by (see app/routers/benchmarks.py's
      // _stamp_citation_range()), so submitting the disabled display
      // value would be a no-op at best; excluding it keeps the payload
      // honest about what this form actually controls.
      const { id, status, created_at, updated_at, use_cases, safety_dimensions, citation_range, ...updatableFields } = form as any;
      const payload = { ...updatableFields, cited_by: Number(form.cited_by) || 0 };

      if (benchmarkId) {
        await updateBenchmark(benchmarkId, payload);
      } else {
        await createBenchmark(payload);
      }
      router.push("/admin/benchmarks");
    } catch (err: any) {
      setError(err?.response?.data?.detail ? JSON.stringify(err.response.data.detail) : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  if (!vocab) return <p>Loading form...</p>;

  return (
    <form onSubmit={handleSubmit} className="card">
      {benchmarkId && (form.use_cases?.length > 0 || form.safety_dimensions?.length > 0) && (
        <div className="auto-classification">
          <strong>Auto-classified (recomputed on every save):</strong>
          {form.use_cases?.length > 0 && (
            <p className="auto-classification-row">
              Use Cases: {form.use_cases.map((u: string) => (
                <MetadataTag key={u} value={u} category="use-case" />
              ))}
            </p>
          )}
          {form.safety_dimensions?.length > 0 && (
            <p className="auto-classification-row">
              Safety Dimensions: {form.safety_dimensions.map((s: string) => (
                <MetadataTag key={s} value={s} />
              ))}
            </p>
          )}
          <p className="auto-classification-note">
            Derived from Task Type, Description, and Benchmark Name. These values are
            not directly editable. Change those fields and save to
            recompute.
          </p>
        </div>
      )}

      <div className="form-grid">
        <div className="field">
          <label>Benchmark Name</label>
          <input value={form.benchmark_name} onChange={(e) => setField("benchmark_name", e.target.value)} required />
        </div>
        <div className="field">
          <label>Release Date</label>
          <input type="date" value={form.release_date || ""} onChange={(e) => setField("release_date", e.target.value)} />
        </div>
      </div>

      <div className="field">
        <label>Benchmark Paper Title</label>
        <input value={form.benchmark_paper_title} onChange={(e) => setField("benchmark_paper_title", e.target.value)} required />
      </div>

      <div className="field">
        <label>Description</label>
        <textarea rows={3} value={form.description || ""} onChange={(e) => setField("description", e.target.value)} />
      </div>

      <TagMultiSelect
        label="Task Type (searchable, grows from the live catalogue)"
        options={taskTypeOptions}
        selected={form.task_type}
        onChange={(next) => setField("task_type", next)}
        placeholder="Search task types, e.g. Jailbreak, Bias, Hallucination..."
      />

      <div className="form-grid">
        <div className="field">
          <label>Created By</label>
          <select value={form.created_by || ""} onChange={(e) => setField("created_by", e.target.value)}>
            <option value="">-- select --</option>
            {vocab.created_by.map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Dev Purpose</label>
          <select value={form.dev_purpose || ""} onChange={(e) => setField("dev_purpose", e.target.value)}>
            <option value="">-- select --</option>
            {vocab.dev_purpose.map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Integration Option</label>
          <select value={form.integration_option} onChange={(e) => setField("integration_option", e.target.value)}>
            {vocab.integration_option.map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Code / Dataset Available</label>
          <select value={form.code_dataset} onChange={(e) => setField("code_dataset", e.target.value)}>
            {vocab.code_dataset.map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
        </div>
        <div className="field">
          <label>License</label>
          <input value={form.license || ""} onChange={(e) => setField("license", e.target.value)} />
        </div>
        <div className="field">
          <label>No. of Samples</label>
          <input value={form.no_of_samples || ""} onChange={(e) => setField("no_of_samples", e.target.value)} />
        </div>
        <div className="field">
          <label>Cited By</label>
          <input type="number" value={form.cited_by} onChange={(e) => setField("cited_by", e.target.value)} />
        </div>
        <div className="field">
          <label>Citation Range (auto-computed from Cited By)</label>
          <input className="disabled-input" value={form.citation_range || ""} disabled />
        </div>
        <label>Entry Modalities (controlled vocabulary, multi-select)</label>
        <div>
          {vocab.entry_modalities.map((m) => (
            <label key={m}>
              <input
                type="checkbox"
                checked={form.entry_modalities?.includes(m)}
                onChange={() => toggleMultiValue("entry_modalities", m)}
              /> {m}
            </label>
          ))}
        </div>

        <label>Language Support (full language names, or Multilingual if 5+ languages)</label>
        <div>
          {vocab.language_support.map((l) => (
            <label key={l}>
              <input
                type="checkbox"
                checked={form.language_support?.includes(l)}
                onChange={() => toggleMultiValue("language_support", l)}
              /> {l}
            </label>
          ))}
        </div>

        <label>Evaluation Metrics (comma-separated, exact paper terminology)</label>
        <input
          type="text"
          value={(form.evaluation_metrics || []).join(", ")}
          onChange={(e) =>
            setField(
              "evaluation_metrics",
              e.target.value.split(",").map((s) => s.trim()).filter(Boolean)
            )
          }
          placeholder="e.g. Attack Success Rate, Refusal Rate"
        />
        <div className="field">
          <label>Code Repository</label>
          <input value={form.code_repository || ""} onChange={(e) => setField("code_repository", e.target.value)} />
        </div>
        <div className="field">
          <label>Dataset Repository</label>
          <input value={form.dataset_repository || ""} onChange={(e) => setField("dataset_repository", e.target.value)} />
        </div>
        <div className="field">
          <label>Paper Link</label>
          <input value={form.paper_link || ""} onChange={(e) => setField("paper_link", e.target.value)} />
        </div>
      </div>

      <hr />
      <h3>Complexity Classifier</h3>
      <div className="form-grid">
        {Object.keys(signals).filter((k) => typeof (signals as any)[k] === "boolean").map((key) => (
          <label key={key} className="classifier-signal">
            <input
              type="checkbox"
              checked={(signals as any)[key]}
              onChange={(e) => setSignals((prev) => ({ ...prev, [key]: e.target.checked }))}
            /> {key.replaceAll("_", " ")}
          </label>
        ))}
      </div>
      <button type="button" className="secondary" onClick={runClassifier} disabled={classifying}>
        {classifying ? "Classifying..." : "Run Complexity Classifier"}
      </button>

      <div className="form-grid classifier-result">
        <div className="field">
          <label>Complexity Level</label>
          <select value={form.complexity_level} onChange={(e) => setField("complexity_level", e.target.value)}>
            {vocab.complexity_level.map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Complexity Reason (why this level was assigned)</label>
          <textarea
            rows={2}
            value={form.complexity_justification || ""}
            onChange={(e) => setField("complexity_justification", e.target.value)}
            placeholder="Filled automatically by Run Complexity Classifier -- editable if you need to refine the wording."
          />
        </div>
      </div>

      {error && <p className="error">{error}</p>}
      <button type="submit" disabled={saving}>{saving ? "Saving..." : "Save Benchmark"}</button>
    </form>
  );
}
