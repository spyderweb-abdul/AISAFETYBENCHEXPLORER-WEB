"use client";

import BenchmarkForm from "../../../../components/BenchmarkForm";

export default function NewBenchmarkPage() {
  return (
    <main className="admin-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Catalogue administration</p>
          <h1>New benchmark</h1>
          <p className="page-description">Add a curated benchmark record to the catalogue.</p>
        </div>
      </header>
      <BenchmarkForm />
    </main>
  );
}
