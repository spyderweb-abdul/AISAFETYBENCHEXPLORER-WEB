CREATE TYPE created_by_enum AS ENUM ('Human', 'Machine', 'Hybrid');
CREATE TYPE dev_purpose_enum AS ENUM ('Eval', 'Train', 'Train & Eval');
CREATE TYPE integration_enum AS ENUM ('API', 'Export', 'API & Export', 'NA');
CREATE TYPE complexity_enum AS ENUM ('Popular', 'High', 'Medium', 'Low', 'Unknown');
CREATE TYPE code_dataset_enum AS ENUM ('Yes', 'No');
CREATE TYPE user_role_enum AS ENUM ('admin', 'researcher');
CREATE TYPE job_status_enum AS ENUM ('queued', 'running', 'done', 'failed', 'needs_review');

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role user_role_enum NOT NULL DEFAULT 'researcher',
    github_id VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE benchmarks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    benchmark_name VARCHAR(255) NOT NULL,
    task_type TEXT[] NOT NULL DEFAULT '{}',
    benchmark_paper_title TEXT NOT NULL,
    release_date DATE,
    description TEXT,
    code_dataset code_dataset_enum DEFAULT 'No',
    no_of_samples VARCHAR(100),
    created_by created_by_enum,
    entry_modalities TEXT[] NOT NULL DEFAULT '{}',
    dev_purpose dev_purpose_enum,
    license VARCHAR(100),
    evaluation_metrics TEXT[] NOT NULL DEFAULT '{}',
    complexity_level complexity_enum DEFAULT 'Unknown',
    complexity_justification TEXT,
    language_support TEXT[] NOT NULL DEFAULT '{}',
    integration_option integration_enum DEFAULT 'NA',
    citation_range VARCHAR(50),
    cited_by INTEGER DEFAULT 0,
    code_repository TEXT,
    dataset_repository TEXT,
    paper_link TEXT,
    status VARCHAR(30) NOT NULL DEFAULT 'published',
    created_by_user_id UUID REFERENCES users(id),
    updated_by_user_id UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_benchmarks_complexity ON benchmarks (complexity_level);
CREATE INDEX idx_benchmarks_task_type ON benchmarks USING GIN (task_type);
CREATE INDEX idx_benchmarks_name ON benchmarks (benchmark_name);

CREATE TABLE eval_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    benchmark_id UUID NOT NULL REFERENCES benchmarks(id) ON DELETE CASCADE,
    benchmark_name VARCHAR(255) NOT NULL,
    paper_title TEXT NOT NULL,
    paper_link TEXT,
    metric_name VARCHAR(255) NOT NULL,
    conceptual_description TEXT,
    methodological_details TEXT,
    mathematical_definition TEXT,
    differences_from_standard_definition TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_eval_metrics_benchmark_id ON eval_metrics (benchmark_id);

CREATE TABLE use_cases (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE benchmark_use_cases (
    benchmark_id UUID NOT NULL REFERENCES benchmarks(id) ON DELETE CASCADE,
    use_case_id INTEGER NOT NULL REFERENCES use_cases(id) ON DELETE CASCADE,
    PRIMARY KEY (benchmark_id, use_case_id)
);

CREATE TABLE repo_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    benchmark_id UUID NOT NULL REFERENCES benchmarks(id) ON DELETE CASCADE,
    source VARCHAR(20) NOT NULL,
    url TEXT NOT NULL,
    stars_or_likes INTEGER DEFAULT 0,
    last_commit_at TIMESTAMPTZ,
    activity_status VARCHAR(30),
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_repo_stats_benchmark_id ON repo_stats (benchmark_id);

CREATE TABLE extraction_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type VARCHAR(20) NOT NULL,
    source_value TEXT NOT NULL,
    model_used VARCHAR(100),
    status job_status_enum NOT NULL DEFAULT 'queued',
    quality_score NUMERIC(3,2),
    requires_review BOOLEAN DEFAULT TRUE,
    result_benchmark_id UUID REFERENCES benchmarks(id),
    submitted_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name VARCHAR(100) NOT NULL,
    record_id UUID NOT NULL,
    action VARCHAR(20) NOT NULL,
    changed_by UUID REFERENCES users(id),
    diff JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
