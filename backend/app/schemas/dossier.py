from pydantic import BaseModel


class CrossRef(BaseModel):
    db: str
    id: str
    url: str | None = None


class Domain(BaseModel):
    name: str
    start: int | None = None
    end: int | None = None
    source: str | None = None


class Overview(BaseModel):
    protein_name: str
    gene: str
    organism: str
    length: int | None = None
    isoforms: list[str] = []
    domains: list[Domain] = []
    subcellular_locations: list[str] = []
    function_summary: str
    caveats: list[str] = []
    key_annotations: list[str] = []
    cross_refs: list[CrossRef] = []


class Variant(BaseModel):
    variant_id: str
    hgvs: str | None = None
    protein_change: str | None = None
    aa_position: int | None = None
    classification: str | None = None
    condition: str | None = None
    species: str | None = None
    review_status: str | None = None
    conflicts: list[str] = []
    pmids: list[str] = []


class AlphaFoldFile(BaseModel):
    label: str
    url: str


class BindingSite(BaseModel):
    label: str
    start: int | None = None
    end: int | None = None


class Structure(BaseModel):
    pdb_ids: list[str] = []
    alphafold_id: str | None = None
    alphafold_files: list[AlphaFoldFile] = []
    predicted_domains: list[Domain] = []
    binding_sites: list[str] = []
    binding_sites_detail: list[BindingSite] = []
    druggability_flags: list[str] = []


class Pathway(BaseModel):
    name: str
    source: str
    role: str | None = None


class InteractionNode(BaseModel):
    id: str
    label: str
    type: str


class InteractionEdge(BaseModel):
    source: str
    target: str
    evidence: str | None = None
    score: float | None = None


class Interactions(BaseModel):
    nodes: list[InteractionNode] = []
    edges: list[InteractionEdge] = []


class LiteratureItem(BaseModel):
    pmid: str
    title: str
    year: int | None = None
    journal: str | None = None
    citation_count: int | None = None
    ml_score: float | None = None
    disease_score: float | None = None
    l2r_score: float | None = None
    topic_label: str | None = None
    tags: list[str] = []


class VariantConditionCount(BaseModel):
    condition: str
    count: int


class VariantsOverview(BaseModel):
    total: int = 0
    condition_counts: list[VariantConditionCount] = []


class LiteratureOverview(BaseModel):
    total: int = 0


class Dossier(BaseModel):
    query: str
    resolved_id: str
    overview: Overview
    variants: list[Variant] = []
    variants_overview: VariantsOverview | None = None
    structure: Structure
    pathways: list[Pathway] = []
    interactions: Interactions
    literature: list[LiteratureItem] = []
    literature_overview: LiteratureOverview | None = None
    study_suggestions: list[str] = []
    provenance: dict[str, str] = {}
