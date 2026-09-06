from datetime import date, datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID
from typing import List
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.languages import canonical_language_name


class CreatedBy(str, Enum):
    human = "Human"
    machine = "Machine"
    hybrid = "Hybrid"


class DevPurpose(str, Enum):
    eval = "Eval"
    train = "Train"
    train_and_eval = "Train & Eval"


class IntegrationOption(str, Enum):
    api = "API"
    export = "Export"
    api_and_export = "API & Export"
    na = "NA"


class ComplexityLevel(str, Enum):
    popular = "Popular"
    high = "High"
    medium = "Medium"
    low = "Low"
    unknown = "Unknown"


class CodeDataset(str, Enum):
    yes = "Yes"
    no = "No"


class EntryModality(str, Enum):
    prompts = "Prompts"
    conversations = "Conversations"
    examples = "Examples"
    binary_choice = "Binary-choice Questions"
    multiple_choice = "Multiple-choice Questions"
    scenarios = "Scenarios"
    sentences = "Sentences"
    excerpts = "Excerpts"
    transcripts = "Transcripts"
    sentence_pairs = "Sentence Pairs"
    entry_tuples = "Entry Tuples"

class LanguageSupport(str, Enum):
    english = "English"
    chinese = "Chinese"
    arabic = "Arabic"
    french = "French"
    hindi = "Hindi"
    korean = "Korean"
    multilingual = "Multilingual"


def _normalize_language_values(value: Any) -> Any:
    """Accept legacy ISO codes on input while always exposing full names."""
    if value is None:
        return value
    values = [value] if isinstance(value, str) else value
    normalized = []
    invalid = []
    for item in values:
        name = canonical_language_name(item)
        if name is None:
            invalid.append(str(item))
        elif name not in normalized:
            normalized.append(name)
    if invalid:
        raise ValueError(f"Unsupported language value(s): {', '.join(invalid)}")
    return normalized

class BenchmarkBase(BaseModel):
    benchmark_name: str = Field(..., max_length=255)
    task_type: list[str] = Field(default_factory=list)
    benchmark_paper_title: str
    release_date: Optional[date] = None
    description: Optional[str] = None
    code_dataset: CodeDataset = CodeDataset.no
    no_of_samples: Optional[str] = None
    created_by: Optional[CreatedBy] = None
    entry_modalities: list[EntryModality] = Field(default_factory=list)
    dev_purpose: Optional[DevPurpose] = None
    license: Optional[str] = None
    evaluation_metrics: list[str] = Field(default_factory=list)
    complexity_level: ComplexityLevel = ComplexityLevel.unknown
    complexity_justification: Optional[str] = None
    language_support: list[LanguageSupport] = Field(default_factory=list)
    integration_option: IntegrationOption = IntegrationOption.na
    citation_range: Optional[str] = None
    cited_by: int = 0
    code_repository: Optional[str] = None
    dataset_repository: Optional[str] = None
    paper_link: Optional[str] = None

    @field_validator("language_support", mode="before")
    @classmethod
    def normalize_language_support(cls, value: Any) -> Any:
        return _normalize_language_values(value)

class BenchmarkEntry(BaseModel):
    benchmark_name: str
    task_type: List[str]
    entry_modalities: List[EntryModality]
    evaluation_metrics: List[str]
    language_support: List[LanguageSupport]
    complexity_level: str
    integration_option: str

    @field_validator("language_support", mode="before")
    @classmethod
    def normalize_language_support(cls, value: Any) -> Any:
        return _normalize_language_values(value)

class BenchmarkCreate(BenchmarkBase):
    pass


class BenchmarkUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    benchmark_name: Optional[str] = None
    task_type: Optional[list[str]] = None
    benchmark_paper_title: Optional[str] = None
    release_date: Optional[date] = None
    description: Optional[str] = None
    code_dataset: Optional[CodeDataset] = None
    no_of_samples: Optional[str] = None
    created_by: Optional[CreatedBy] = None
    entry_modalities: Optional[list[EntryModality]] = None
    dev_purpose: Optional[DevPurpose] = None
    license: Optional[str] = None
    evaluation_metrics: Optional[list[str]] = None
    complexity_level: Optional[ComplexityLevel] = None
    complexity_justification: Optional[str] = None
    language_support: Optional[list[LanguageSupport]] = None
    integration_option: Optional[IntegrationOption] = None
    citation_range: Optional[str] = None
    cited_by: Optional[int] = None
    code_repository: Optional[str] = None
    dataset_repository: Optional[str] = None
    paper_link: Optional[str] = None

    @field_validator("language_support", mode="before")
    @classmethod
    def normalize_language_support(cls, value: Any) -> Any:
        return _normalize_language_values(value)


class BenchmarkOut(BenchmarkBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    # Phase 5: deterministic classifications computed server-side by
    # app/core/use_case_classifier.py / app/core/safety_dimension_classifier.py.
    # Deliberately absent from BenchmarkCreate/BenchmarkUpdate (which has
    # extra="forbid") -- these are never accepted as user input, only
    # ever computed and stamped onto the ORM object in
    # app/routers/benchmarks.py and app/core/agent_runner.py.
    use_cases: list[str] = Field(default_factory=list)
    safety_dimensions: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class BenchmarkPageOut(BaseModel):
    """Admin catalogue page with a stable total for server-side pagination."""

    items: list[BenchmarkOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class BenchmarkReextractRequest(BaseModel):
    """Model is explicit so re-extraction never silently uses a default."""

    model_used: str = Field(..., min_length=3, max_length=100)
