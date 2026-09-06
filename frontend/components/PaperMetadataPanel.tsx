"use client";

import { useEffect, useState, type ReactNode } from "react";
import { PaperMetadata, getPaperMetadata } from "../lib/api";

function MetadataValue({ children }: { children: ReactNode }) {
  return <div className="detail-item-value">{children ?? "Not recorded"}</div>;
}

export default function PaperMetadataPanel({ benchmarkId }: { benchmarkId: string }) {
  const [metadata, setMetadata] = useState<PaperMetadata | null | undefined>(undefined);

  useEffect(() => {
    setMetadata(undefined);
    getPaperMetadata(benchmarkId).then(setMetadata).catch(() => setMetadata(null));
  }, [benchmarkId]);

  return (
    <section className="card" aria-labelledby="paper-metadata-heading">
      <h2 id="paper-metadata-heading" className="detail-section-title">Paper metadata</h2>
      {metadata === undefined ? (
        <p className="muted-copy">Loading source-backed paper metadata...</p>
      ) : metadata === null ? (
        <p className="muted-copy">
          Source-backed metadata has not been recorded yet. It will be added at the next extraction or activity refresh.
        </p>
      ) : (
        <>
          <div className="detail-grid">
            <div className="detail-item"><span className="detail-item-label">Canonical title</span><MetadataValue>{metadata.canonical_title}</MetadataValue></div>
            <div className="detail-item"><span className="detail-item-label">Authors</span><MetadataValue>{metadata.authors}</MetadataValue></div>
            <div className="detail-item"><span className="detail-item-label">Venue</span><MetadataValue>{metadata.venue}</MetadataValue></div>
            <div className="detail-item"><span className="detail-item-label">Publication date</span><MetadataValue>{metadata.publication_date}</MetadataValue></div>
            <div className="detail-item"><span className="detail-item-label">DOI</span><MetadataValue>{metadata.doi ? <a href={`https://doi.org/${metadata.doi}`} target="_blank" rel="noreferrer">{metadata.doi} ↗</a> : null}</MetadataValue></div>
            <div className="detail-item"><span className="detail-item-label">arXiv</span><MetadataValue>{metadata.arxiv_id ? <a href={`https://arxiv.org/abs/${metadata.arxiv_id}`} target="_blank" rel="noreferrer">{metadata.arxiv_id} ↗</a> : null}</MetadataValue></div>
            <div className="detail-item"><span className="detail-item-label">Citation count</span><MetadataValue>{metadata.citation_count ?? "Not recorded"}</MetadataValue></div>
            <div className="detail-item"><span className="detail-item-label">Citation source</span><MetadataValue>{metadata.citation_source}</MetadataValue></div>
            <div className="detail-item"><span className="detail-item-label">Last checked</span><MetadataValue>{metadata.citation_checked_at ? new Date(metadata.citation_checked_at).toLocaleString() : null}</MetadataValue></div>
            <div className="detail-item"><span className="detail-item-label">Open access</span><MetadataValue>{metadata.is_open_access === null ? "Not recorded" : metadata.is_open_access ? "Available" : "Not available"}</MetadataValue></div>
            <div className="detail-item"><span className="detail-item-label">Metadata source</span><MetadataValue>{metadata.metadata_source}</MetadataValue></div>
            <div className="detail-item"><span className="detail-item-label">Open access link</span><MetadataValue>{metadata.open_access_url ? <a href={metadata.open_access_url} target="_blank" rel="noreferrer">Open paper ↗</a> : null}</MetadataValue></div>
          </div>
          {metadata.last_error && <p className="paper-metadata-warning">Last source lookup: {metadata.last_error}</p>}
        </>
      )}
    </section>
  );
}
