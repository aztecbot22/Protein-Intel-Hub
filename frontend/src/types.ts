export type CrossRef = {
  db: string;
  id: string;
  url?: string;
};

export type Domain = {
  name: string;
  start?: number;
  end?: number;
  source?: string;
};

export type Overview = {
  protein_name: string;
  gene: string;
  organism: string;
  length?: number;
  isoforms: string[];
  domains: Domain[];
  subcellular_locations: string[];
  function_summary: string;
  caveats: string[];
  key_annotations: string[];
  cross_refs: CrossRef[];
};

export type Variant = {
  variant_id: string;
  hgvs?: string;
  protein_change?: string;
  aa_position?: number;
  classification?: string;
  condition?: string;
  species?: string;
  review_status?: string;
  conflicts?: string[];
  pmids?: string[];
};

export type Structure = {
  pdb_ids: string[];
  alphafold_id?: string;
  alphafold_files?: { label: string; url: string }[];
  predicted_domains: Domain[];
  binding_sites: string[];
  binding_sites_detail?: { label: string; start?: number; end?: number }[];
  druggability_flags: string[];
};

export type Pathway = {
  name: string;
  source: string;
  role?: string;
};

export type InteractionNode = {
  id: string;
  label: string;
  type: string;
};

export type InteractionEdge = {
  source: string;
  target: string;
  evidence?: string;
  score?: number;
};

export type Interactions = {
  nodes: InteractionNode[];
  edges: InteractionEdge[];
};

export type LiteratureItem = {
  pmid: string;
  title: string;
  year?: number;
  journal?: string;
  citation_count?: number;
  ml_score?: number;
  disease_score?: number;
  l2r_score?: number;
  topic_label?: string;
  tags: string[];
};

export type VariantConditionCount = {
  condition: string;
  count: number;
};

export type VariantsOverview = {
  total: number;
  condition_counts: VariantConditionCount[];
};

export type LiteratureOverview = {
  total: number;
};

export type Dossier = {
  query: string;
  resolved_id: string;
  overview: Overview;
  variants: Variant[];
  variants_overview?: VariantsOverview;
  structure: Structure;
  pathways: Pathway[];
  interactions: Interactions;
  literature: LiteratureItem[];
  literature_overview?: LiteratureOverview;
  study_suggestions: string[];
  provenance: Record<string, string>;
};

export type Annotation = {
  id: number;
  protein_id: string;
  author_id: number;
  author_name: string;
  content: string;
  source: string;
  created_at: string;
};
