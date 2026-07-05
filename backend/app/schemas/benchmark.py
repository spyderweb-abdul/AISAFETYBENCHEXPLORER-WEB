from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID
from typing import List
from pydantic import BaseModel, ConfigDict, Field


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
    en = "en"
    zh = "zh"
    ar = "ar"
    fr = "fr"
    hi = "hi"
    ko = "ko"
    multilingual = "Multilingual"

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

class BenchmarkEntry(BaseModel):
    benchmark_name: str
    task_type: List[str]
    entry_modalities: List[EntryModality]
    evaluation_metrics: List[str]
    language_support: List[LanguageSupport]
    complexity_level: str
    integration_option: str

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


class BenchmarkOut(BenchmarkBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
