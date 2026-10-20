from datetime import date
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ValidationStatus(StrEnum):
    detected = "detected"
    unclear = "unclear"
    proposed = "proposed"
    validated = "validated"
    rejected = "rejected"


class Profile(StrEnum):
    economy = "economy"
    balanced = "balanced"
    quality = "quality"


class ProjectInput(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10000)
    context: str = Field(default="", max_length=30000)
    glossary: dict[str, str] = Field(default_factory=dict, max_length=300)


class ProjectPatch(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    context: str | None = Field(default=None, max_length=30000)
    glossary: dict[str, str] | None = Field(default=None, max_length=300)


class MeetingInput(StrictModel):
    project_id: str
    title: str = Field(min_length=1, max_length=200)
    date: date
    profile: Profile = Profile.balanced
    language: str | None = Field(default="es", pattern=r"^[a-z]{2}$")


class TranscriptPatch(StrictModel):
    revised_text: str | None = Field(default=None, max_length=10000)
    reviewed: bool | None = None
    doubtful: bool | None = None
    revision: int


class Evidence(StrictModel):
    segment_id: str
    quote: str = Field(min_length=1, max_length=1000)


class GeneratedRequirement(StrictModel):
    code: str = Field(pattern=r"^R[FN]-\d{3,}$")
    kind: str = Field(pattern=r"^(functional|nonfunctional)$")
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=10000)
    actor: str = Field(max_length=300)
    module: str = Field(max_length=300)
    priority: str = Field(pattern=r"^(high|medium|low|unspecified)$")
    status: str = Field(pattern=r"^(detected|unclear|proposed)$")
    interpretation: str = Field(pattern=r"^(fact|proposal|inference)$")
    evidence: list[Evidence] = Field(min_length=1, max_length=30)
    dependencies: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)


class Story(StrictModel):
    code: str
    text: str = Field(min_length=1, max_length=5000)
    requirements: list[str] = Field(min_length=1)


class Criterion(StrictModel):
    code: str
    story_code: str
    given: str
    when: str
    then: str
    requirements: list[str] = Field(min_length=1)


class EvidencedNote(StrictModel):
    text: str = Field(max_length=10000)
    evidence: list[Evidence] = Field(default_factory=list)


class ExecutiveSummary(StrictModel):
    objective: str = ""
    context: str = ""
    problems: list[str] = Field(default_factory=list)
    needs: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    commitments: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class BacklogItem(StrictModel):
    code: str
    module: str
    story_code: str
    priority: str = Field(pattern=r"^(high|medium|low|unspecified)$")
    dependencies: list[str] = Field(default_factory=list)
    status: str = Field(default="proposed", pattern=r"^(detected|unclear|proposed)$")
    requirements: list[str] = Field(min_length=1)


class AnalysisResult(StrictModel):
    summary: ExecutiveSummary
    requirements: list[GeneratedRequirement] = Field(default_factory=list, max_length=500)
    stories: list[Story] = Field(default_factory=list)
    criteria: list[Criterion] = Field(default_factory=list)
    business_rules: list[EvidencedNote] = Field(default_factory=list)
    questions: list[EvidencedNote] = Field(default_factory=list)
    processes: list[EvidencedNote] = Field(default_factory=list)
    conceptual_model: list[EvidencedNote] = Field(default_factory=list)
    backlog: list[BacklogItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_references(self):
        codes = {r.code for r in self.requirements}
        if len(codes) != len(self.requirements):
            raise ValueError("Códigos de requisitos duplicados")
        stories = {s.code for s in self.stories}
        if len(stories) != len(self.stories) or len({c.code for c in self.criteria}) != len(self.criteria):
            raise ValueError("Identificadores duplicados")
        for item in [*self.stories, *self.criteria, *self.backlog]:
            if not set(item.requirements) <= codes:
                raise ValueError("Referencia a requisito inexistente")
        for item in [*self.criteria, *self.backlog]:
            if item.story_code not in stories:
                raise ValueError("Referencia a historia inexistente")
        for requirement in self.requirements:
            if not set(requirement.dependencies) <= codes:
                raise ValueError("Dependencia inexistente")
        backlog_codes = {item.code for item in self.backlog}
        if len(backlog_codes) != len(self.backlog):
            raise ValueError("Identificadores de backlog duplicados")
        for item in self.backlog:
            if not set(item.dependencies) <= backlog_codes:
                raise ValueError("Dependencia de backlog inexistente")
        return self


class AnalysisRequest(StrictModel):
    input_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    consent: bool = False


class RequirementPatch(StrictModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, min_length=1, max_length=10000)
    observations: str | None = Field(default=None, max_length=10000)
    priority: str | None = Field(default=None, pattern=r"^(high|medium|low|unspecified)$")
    status: ValidationStatus | None = None


class CriterionPatch(StrictModel):
    revision: int = Field(ge=0)
    given: str = Field(min_length=1, max_length=10000)
    when: str = Field(min_length=1, max_length=10000)
    then: str = Field(min_length=1, max_length=10000)
    observations: str = Field(default="", max_length=10000)


class CriterionValidation(StrictModel):
    revision: int = Field(ge=0)
    status: str = Field(pattern=r"^(validated|rejected)$")
    observations: str = Field(default="", max_length=10000)

    @model_validator(mode="after")
    def rejection_reason(self):
        if self.status == "rejected" and not self.observations.strip():
            raise ValueError("Indica el motivo del rechazo")
        return self


class SettingsPatch(StrictModel):
    profile: Profile = Profile.balanced
    provider: str = Field(default="chatgpt", pattern=r"^(chatgpt|mock)$")
    model: str | None = Field(default=None, max_length=200)
    language: str | None = Field(default="es", pattern=r"^[a-z]{2}$")


class CreditPolicy(StrictModel):
    confirmed_zero_credits: bool


class AccountChoice(StrictModel):
    account_id: str = Field(min_length=1, max_length=100)
