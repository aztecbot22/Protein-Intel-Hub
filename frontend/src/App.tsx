import { useEffect, useMemo, useRef, useState } from "react";
import { exportVariants, fetchDossier, type DossierOptions } from "./api";
import type { Dossier } from "./types";

const TABS = ["Overview", "Variants", "Structure", "Pathways", "Literature"] as const;

type Tab = (typeof TABS)[number];

const ORGANISMS = [
  { label: "Human (Homo sapiens)", taxonId: 9606 },
  { label: "Human (HeLa)", taxonId: 9606 },
  { label: "Mouse (Mus musculus)", taxonId: 10090 },
  { label: "Rat (Rattus norvegicus)", taxonId: 10116 },
  { label: "Zebrafish (Danio rerio)", taxonId: 7955 },
  { label: "Fruit fly (Drosophila melanogaster)", taxonId: 7227 },
  { label: "Yeast (Saccharomyces cerevisiae)", taxonId: 559292 },
  { label: "Arabidopsis thaliana", taxonId: 3702 },
  { label: "E. coli (K-12)", taxonId: 83333 },
];

const WHEEL_COLORS = ["#0f766e", "#c2410c", "#0ea5e9", "#a855f7", "#16a34a", "#eab308", "#ef4444", "#64748b"];

declare global {
  interface Window {
    $3Dmol?: {
      createViewer: (container: HTMLElement, options?: Record<string, unknown>) => {
        clear: () => void;
        addModel: (data: string, format: string) => void;
        setStyle: (selection: Record<string, unknown>, style: Record<string, unknown>) => void;
        setClickable: (
          selection: Record<string, unknown>,
          clickable: boolean,
          callback: (atom: { resi?: number; resn?: string; chain?: string; atom?: string } | null) => void,
        ) => void;
        zoomTo: () => void;
        render: () => void;
        spin: (axis: "x" | "y" | "z" | false, speed?: number) => void;
        setBackgroundColor?: (color: string) => void;
      };
    };
  }
}

export default function App() {
  const [query, setQuery] = useState("");
  const [organismTaxonId, setOrganismTaxonId] = useState<number>(9606);
  const [topic, setTopic] = useState("");
  const [activeTab, setActiveTab] = useState<Tab>("Overview");
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [loading, setLoading] = useState(false);
  const [fallback, setFallback] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  const [variantPage, setVariantPage] = useState(1);
  const [variantPageSize] = useState(10);
  const [variantSort, setVariantSort] = useState<"significance" | "date">("significance");

  const [literaturePage, setLiteraturePage] = useState(1);
  const [literaturePageSize] = useState(10);
  const [literatureYearFrom, setLiteratureYearFrom] = useState("");
  const [literatureYearTo, setLiteratureYearTo] = useState("");
  const [literatureSort, setLiteratureSort] = useState<"date" | "relevance" | "citation" | "ml">("date");
  const [structureSpin, setStructureSpin] = useState(true);

  const headline = useMemo(() => {
    if (!dossier) return "Protein Intelligence Hub";
    return `${dossier.overview.gene} dossier`; 
  }, [dossier]);

  const [studyOptions, setStudyOptions] = useState<string[]>([]);
  const studySuggestions = studyOptions;
  const suggestionValue = studySuggestions.includes(topic) ? topic : "";

  const parseYear = (value: string) => {
    const year = Number(value);
    return Number.isFinite(year) && year > 0 ? year : undefined;
  };

  const buildOptions = (overrides: Partial<DossierOptions> = {}) => ({
    organismTaxonId,
    topic: topic.trim() || undefined,
    variantPage,
    variantPageSize,
    variantSort,
    literaturePage,
    literaturePageSize,
    literatureYearFrom: parseYear(literatureYearFrom),
    literatureYearTo: parseYear(literatureYearTo),
    literatureSort,
    ...overrides,
  });

  const handleSearch = async (value: string, overrides: Partial<DossierOptions> = {}) => {
    const trimmed = value.trim();
    if (!trimmed) {
      setError("Enter a gene symbol or UniProt ID to build the dossier.");
      setDossier(null);
      return;
    }
    setLoading(true);
    setError(null);
    setNotFound(false);
    try {
      const result = await fetchDossier(trimmed, buildOptions(overrides));
      if (result.notFound || !result.dossier) {
        setDossier(null);
        setFallback(false);
        setNotFound(true);
        return;
      }
      setDossier(result.dossier);
      setStudyOptions(result.dossier.study_suggestions || []);
      setFallback(result.fallback);
    } catch (err) {
      setError("Unable to load dossier data.");
    } finally {
      setLoading(false);
    }
  };

  const handleNewSearch = () => {
    setVariantPage(1);
    setLiteraturePage(1);
    setTopic("");
    setStudyOptions([]);
    void handleSearch(query, { variantPage: 1, literaturePage: 1 });
  };

  const handleExport = async () => {
    if (!dossier) return;
    const blob = await exportVariants(dossier.query, dossier.variants);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${dossier.query}_variants.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleVariantPageChange = (nextPage: number) => {
    setVariantPage(nextPage);
    if (query.trim()) {
      void handleSearch(query, { variantPage: nextPage });
    }
  };

  const handleLiteraturePageChange = (nextPage: number) => {
    setLiteraturePage(nextPage);
    if (query.trim()) {
      void handleSearch(query, { literaturePage: nextPage });
    }
  };

  const handleApplyLiteratureFilters = () => {
    setLiteraturePage(1);
    if (query.trim()) {
      void handleSearch(query, { literaturePage: 1 });
    }
  };

  const variantTotal = dossier?.variants_overview?.total ?? 0;
  const variantTotalPages = variantTotal ? Math.ceil(variantTotal / variantPageSize) : 1;
  const literatureTotal = dossier?.literature_overview?.total ?? 0;
  const literatureTotalPages = literatureTotal ? Math.ceil(literatureTotal / literaturePageSize) : 1;
  const keyAnnotations = dossier?.overview.key_annotations ?? [];
  const showKeyAnnotationsInIsoforms =
    !!dossier && dossier.overview.isoforms.length === 0 && keyAnnotations.length > 0;
  const showKeyAnnotationsInCaveats =
    !!dossier && dossier.overview.caveats.length === 0 && keyAnnotations.length > 0 && !showKeyAnnotationsInIsoforms;

  return (
    <div className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">Protein Intelligence Hub</p>
          <h1>{headline}</h1>
          <p className="subtitle">
            A unified dossier that merges protein identity, clinical variants, structure intelligence,
            pathways, interactions, and the most relevant evidence in one place.
          </p>
        </div>
        <div className="search-card">
          <label htmlFor="protein-input">Protein, gene, or UniProt ID</label>
          <div className="search-row">
            <input
              id="protein-input"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  handleNewSearch();
                }
              }}
              placeholder="Try TP53, BRCA1, P04637"
            />
            <button onClick={handleNewSearch} disabled={loading}>
              {loading ? "Loading" : "Build dossier"}
            </button>
          </div>
          <div className="filter-grid">
            <div>
              <label htmlFor="organism-select">Organism</label>
              <select
                id="organism-select"
                value={organismTaxonId}
                onChange={(event) => {
                  setOrganismTaxonId(Number(event.target.value));
                  setVariantPage(1);
                  setLiteraturePage(1);
                }}
              >
                {ORGANISMS.map((organism) => (
                  <option key={organism.label} value={organism.taxonId}>
                    {organism.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <p className="hint">Tip: use gene symbols or canonical UniProt IDs.</p>
        </div>
      </header>

      {error && <div className="alert">{error}</div>}
      {notFound && <div className="alert">No matching protein found. Try a gene symbol or UniProt ID.</div>}
      {fallback && !notFound && (
        <div className="alert amber">Running in demo mode. Connect the API for live data.</div>
      )}

      {dossier && (
        <main className="layout">
          <aside className="summary">
            <div className="card">
              <div className="card-header">
                <h2>{dossier.overview.protein_name}</h2>
                <span className="badge">{dossier.resolved_id}</span>
              </div>
              <div className="meta">
                <div>
                  <span>Gene</span>
                  <strong>{dossier.overview.gene}</strong>
                </div>
                <div>
                  <span>Organism</span>
                  <strong>{dossier.overview.organism}</strong>
                </div>
                <div>
                  <span>Length</span>
                  <strong>{dossier.overview.length ?? "-"}</strong>
                </div>
              </div>
              <p className="summary-text">{dossier.overview.function_summary}</p>
              <div className="pill-row">
                {dossier.overview.subcellular_locations.map((loc) => (
                  <span className="pill" key={loc}>
                    {loc}
                  </span>
                ))}
              </div>
            </div>

            <div className="card">
              <h3>Cross references</h3>
              <ul className="list">
                {dossier.overview.cross_refs.map((ref) => (
                  <li key={`${ref.db}-${ref.id}`}>
                    <span>{ref.db}</span>
                    <strong>{ref.id}</strong>
                  </li>
                ))}
              </ul>
            </div>

            <div className="card">
              <h3>Evidence provenance</h3>
              <ul className="list">
                {Object.entries(dossier.provenance).map(([key, value]) => (
                  <li key={key}>
                    <span>{key}</span>
                    <strong>{value}</strong>
                  </li>
                ))}
              </ul>
            </div>
          </aside>

          <section className="panel">
            <div className="filter-bar">
              <div>
                <label htmlFor="topic-select">Suggested study focus</label>
                <select
                  id="topic-select"
                  value={suggestionValue}
                  onChange={(event) => {
                    const value = event.target.value;
                    setTopic(value);
                    setVariantPage(1);
                    setLiteraturePage(1);
                    void handleSearch(query, { topic: value || undefined, variantPage: 1, literaturePage: 1 });
                  }}
                >
                  <option value="">All studies</option>
                  {studySuggestions.map((suggestion) => (
                    <option key={suggestion} value={suggestion}>
                      {suggestion}
                    </option>
                  ))}
                </select>
                {dossier && studySuggestions.length === 0 && (
                  <p className="muted">No suggestions found yet. Showing all studies.</p>
                )}
              </div>
            </div>
            <nav className="tabs">
              {TABS.map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={tab === activeTab ? "active" : ""}
                >
                  {tab}
                </button>
              ))}
            </nav>

            <div className="panel-body">
              {activeTab === "Overview" && (
                <div className="grid">
                  <div className="card">
                    <h3>Domains</h3>
                    <ul className="list">
                      {dossier.overview.domains.length === 0 && <li>No domains reported.</li>}
                      {dossier.overview.domains.map((domain) => (
                        <li key={domain.name}>
                          <span>{domain.name}</span>
                          <strong>
                            {domain.start && domain.end ? `${domain.start}-${domain.end}` : "-"}
                          </strong>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="card">
                    <h3>{showKeyAnnotationsInIsoforms ? "Key annotations" : "Isoforms"}</h3>
                    <div className="pill-row">
                      {dossier.overview.isoforms.length === 0 && keyAnnotations.length === 0 && (
                        <span className="muted">No isoforms listed.</span>
                      )}
                      {dossier.overview.isoforms.map((isoform) => (
                        <span className="pill" key={isoform}>
                          {isoform}
                        </span>
                      ))}
                      {showKeyAnnotationsInIsoforms &&
                        keyAnnotations.map((annotation) => (
                          <span className="pill" key={annotation}>
                            {annotation}
                          </span>
                        ))}
                    </div>
                    <h3 className="spacer">{showKeyAnnotationsInCaveats ? "Key annotations" : "Caveats"}</h3>
                    <ul className="list">
                      {dossier.overview.caveats.length === 0 && keyAnnotations.length === 0 && (
                        <li>No caveats reported.</li>
                      )}
                      {dossier.overview.caveats.map((caveat) => (
                        <li key={caveat}>{caveat}</li>
                      ))}
                      {showKeyAnnotationsInCaveats &&
                        keyAnnotations.map((annotation) => (
                          <li key={annotation}>{annotation}</li>
                        ))}
                    </ul>
                  </div>
                </div>
              )}

              {activeTab === "Variants" && (
                <div className="card">
                  <div className="card-header">
                    <div>
                      <h3>Clinical variants</h3>
                      <p className="muted">
                        Showing page {variantPage} of {variantTotalPages} • {variantTotal} total records
                      </p>
                    </div>
                    <div className="actions">
                      <select
                        value={variantSort}
                        onChange={(event) => {
                          const nextSort = event.target.value as "significance" | "date";
                          setVariantSort(nextSort);
                          setVariantPage(1);
                          void handleSearch(query, { variantSort: nextSort, variantPage: 1 });
                        }}
                      >
                        <option value="significance">Sort: significance</option>
                        <option value="date">Sort: default</option>
                      </select>
                      <button className="secondary" onClick={handleExport}>
                        Export CSV
                      </button>
                    </div>
                  </div>
                  <div className="table">
                  <div className="row header">
                    <span>ID</span>
                    <span>HGVS</span>
                    <span>AA change</span>
                    <span>AA pos</span>
                    <span>Clinical significance</span>
                    <span>Species</span>
                    <span>Review</span>
                  </div>
                    {dossier.variants.length === 0 && (
                      <div className="row empty">
                        <span className="muted">No ClinVar variants found.</span>
                      </div>
                    )}
                    {dossier.variants.map((variant) => (
                      <div className="row" key={variant.variant_id}>
                        <span>{variant.variant_id}</span>
                        <span>{variant.hgvs}</span>
                        <span>{variant.protein_change ?? "-"}</span>
                        <span>{variant.aa_position ?? "-"}</span>
                        <span>{variant.classification ?? "-"}</span>
                        <span>{variant.species ?? "-"}</span>
                        <span>{variant.review_status ?? "-"}</span>
                      </div>
                    ))}
                  </div>
                  <div className="pagination">
                    <button
                      className="secondary"
                      onClick={() => handleVariantPageChange(Math.max(variantPage - 1, 1))}
                      disabled={variantPage <= 1}
                    >
                      Prev
                    </button>
                    <span className="muted">
                      Page {variantPage} of {variantTotalPages}
                    </span>
                    <button
                      className="secondary"
                      onClick={() => handleVariantPageChange(Math.min(variantPage + 1, variantTotalPages))}
                      disabled={variantPage >= variantTotalPages}
                    >
                      Next
                    </button>
                  </div>
                  {dossier.variants_overview?.condition_counts?.length ? (
                    <div className="wheel-block">
                      <div>
                        <h3>ClinVar condition wheel</h3>
                        <p className="muted">Most frequent conditions in the current result set.</p>
                      </div>
                      <ConditionWheel data={dossier.variants_overview.condition_counts.slice(0, 8)} />
                      <ul className="legend">
                        {dossier.variants_overview.condition_counts.slice(0, 8).map((item, index) => (
                          <li key={item.condition}>
                            <span className="legend-swatch" style={{ background: WHEEL_COLORS[index % WHEEL_COLORS.length] }} />
                            <span>{item.condition}</span>
                            <strong>{item.count}</strong>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              )}

              {activeTab === "Structure" && (
                <div className="structure-layout">
                  <div className="card compact-card structure-side">
                    <h3>Predicted domains</h3>
                    <ul className="list">
                      {dossier.structure.predicted_domains.length === 0 && <li>No predicted domains reported.</li>}
                      {dossier.structure.predicted_domains.map((domain) => (
                        <li key={domain.name}>
                          <span>{domain.name}</span>
                          <strong>
                            {domain.start && domain.end ? `${domain.start}-${domain.end}` : "-"}
                          </strong>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="card structure-card structure-main">
                    <h3>Structures</h3>
                    <div className="pill-row">
                      {dossier.structure.pdb_ids.length === 0 &&
                        !dossier.structure.alphafold_id && <span className="muted">No structures found.</span>}
                      {dossier.structure.pdb_ids.map((pdb) => (
                        <span className="pill" key={pdb}>
                          PDB {pdb}
                        </span>
                      ))}
                    </div>
                    {dossier.structure.alphafold_files && dossier.structure.alphafold_files.length > 0 && (
                      <div className="alphafold-options">
                        <div className="viewer-header spacer">
                          <h3>AlphaFold structure viewer</h3>
                          <button
                            className="secondary small"
                            onClick={() => setStructureSpin((prev) => !prev)}
                          >
                            {structureSpin ? "Stop rotation" : "Auto-rotate"}
                          </button>
                        </div>
                        <div className="viewer">
                          <AlphaFoldViewer
                            files={dossier.structure.alphafold_files}
                            bindingSites={dossier.structure.binding_sites_detail || []}
                            spin={structureSpin}
                          />
                        </div>
                        <div className="pill-row spacer">
                          {dossier.structure.alphafold_files.slice(0, 4).map((file) => (
                            <a
                              key={file.url}
                              className="pill link-pill"
                              href={file.url}
                              target="_blank"
                              rel="noreferrer"
                            >
                              {file.label}
                            </a>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                  <div className="card compact-card structure-side">
                    <h3>Druggability heuristics</h3>
                    <ul className="list">
                      {dossier.structure.druggability_flags.length === 0 && <li>No heuristic flags yet.</li>}
                      {dossier.structure.druggability_flags.map((flag) => (
                        <li key={flag}>{flag}</li>
                      ))}
                    </ul>
                    <h3 className="spacer">Binding sites</h3>
                    <div className="pill-row">
                      {dossier.structure.binding_sites.length === 0 && <span className="muted">No binding sites listed.</span>}
                      {dossier.structure.binding_sites.map((site) => (
                        <span className="pill" key={site}>
                          {site}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {activeTab === "Pathways" && (
                <div className="grid">
                  <div className="card">
                    <h3>Pathway membership</h3>
                    <ul className="list">
                      {dossier.pathways.length === 0 && <li>No pathways mapped.</li>}
                      {dossier.pathways.map((pathway) => (
                        <li key={pathway.name}>
                          <span>{pathway.name}</span>
                          <strong>{pathway.source}</strong>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="card">
                    <h3>Interaction network</h3>
                    <p className="muted">Filtered view of curated interactions.</p>
                    <ul className="list">
                      {dossier.interactions.edges.length === 0 && <li>No interactions returned.</li>}
                      {dossier.interactions.edges.map((edge, index) => (
                        <li key={`${edge.source}-${edge.target}-${index}`}>
                          <span>
                            {edge.source} → {edge.target}
                          </span>
                          <strong>{edge.evidence}</strong>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              {activeTab === "Literature" && (
                <div className="literature-panel">
                  <div className="card">
                    <div className="card-header">
                      <div>
                        <h3>Literature filters</h3>
                        <p className="muted">
                          {literatureTotal} total results • Page {literaturePage} of {literatureTotalPages}
                        </p>
                      </div>
                      <button className="secondary" onClick={handleApplyLiteratureFilters}>
                        Apply filters
                      </button>
                    </div>
                    <div className="filter-grid">
                      <div>
                        <label htmlFor="year-from">Year from</label>
                        <input
                          id="year-from"
                          value={literatureYearFrom}
                          onChange={(event) => setLiteratureYearFrom(event.target.value)}
                          placeholder="2010"
                        />
                      </div>
                      <div>
                        <label htmlFor="year-to">Year to</label>
                        <input
                          id="year-to"
                          value={literatureYearTo}
                          onChange={(event) => setLiteratureYearTo(event.target.value)}
                          placeholder="2026"
                        />
                      </div>
                      <div>
                        <label htmlFor="literature-sort">Sort by</label>
                        <select
                          id="literature-sort"
                          value={literatureSort}
                          onChange={(event) =>
                            setLiteratureSort(event.target.value as "date" | "relevance" | "citation" | "ml")
                          }
                        >
                          <option value="date">Most recent</option>
                          <option value="relevance">Relevance</option>
                          <option value="citation">Highest citations</option>
                          <option value="ml">ML relevance (L2R)</option>
                        </select>
                      </div>
                    </div>
                  </div>

                  <div className="grid">
                    {dossier.literature.length === 0 && (
                      <div className="card">
                        <p className="muted">No PubMed results returned for this query.</p>
                      </div>
                    )}
                    {dossier.literature.map((paper) => (
                      <a
                        className="card clickable"
                        key={paper.pmid}
                        href={`https://pubmed.ncbi.nlm.nih.gov/${paper.pmid}/`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        <h3>{paper.title}</h3>
                        <p className="muted">
                          {paper.journal} {paper.year ? `• ${paper.year}` : ""}
                        </p>
                        <div className="pill-row">
                          {paper.topic_label && (
                            <span className="pill topic-pill">Topic: {paper.topic_label}</span>
                          )}
                          {paper.tags.map((tag) => (
                            <span className="pill" key={tag}>
                              {tag}
                            </span>
                          ))}
                        </div>
                        <p className="muted">
                          PMID: {paper.pmid} • Citations: {paper.citation_count ?? 0}
                          {literatureSort === "ml" && paper.l2r_score != null
                            ? ` • L2R: ${paper.l2r_score}`
                            : ""}
                          {literatureSort === "ml" && paper.disease_score != null
                            ? ` • Disease: ${paper.disease_score}`
                            : ""}
                        </p>
                      </a>
                    ))}
                  </div>

                  <div className="pagination">
                    <button
                      className="secondary"
                      onClick={() => handleLiteraturePageChange(Math.max(literaturePage - 1, 1))}
                      disabled={literaturePage <= 1}
                    >
                      Prev
                    </button>
                    <span className="muted">
                      Page {literaturePage} of {literatureTotalPages}
                    </span>
                    <button
                      className="secondary"
                      onClick={() => handleLiteraturePageChange(Math.min(literaturePage + 1, literatureTotalPages))}
                      disabled={literaturePage >= literatureTotalPages}
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}

            </div>
          </section>
        </main>
      )}

      {!dossier && (
        <section className="home">
          <div className="card">
            <h2>Build a protein dossier</h2>
            <p className="muted">
              Search any gene or UniProt ID to assemble an integrated dossier with canonical info,
              clinical variants, structures, pathways, interactions, and literature.
            </p>
          </div>
          <div className="grid">
            <div className="card">
              <h3>Evidence-first modules</h3>
              <p className="muted">
                Each tab is driven by live biomedical databases and surfaced with provenance so you can
                trust every claim and follow the evidence trail.
              </p>
            </div>
            <div className="card">
              <h3>Clinical & experimental alignment</h3>
              <p className="muted">
                Rank variants by clinical significance, map conditions, and explore the most relevant
                studies for your organism and disease focus.
              </p>
            </div>
            <div className="card">
              <h3>Collaborative context</h3>
              <p className="muted">
                Capture annotations, hypotheses, and caveats alongside the data so your team keeps a
                shared, living record.
              </p>
            </div>
          </div>
        </section>
      )}

      <footer className="footer">
        <p>
          © 2026 Priyansh Pathak. Data sources:{" "}
          <a href="https://www.uniprot.org/" target="_blank" rel="noreferrer">UniProt</a>,{" "}
          <a href="https://www.ncbi.nlm.nih.gov/clinvar/" target="_blank" rel="noreferrer">ClinVar</a>,{" "}
          <a href="https://pubmed.ncbi.nlm.nih.gov/" target="_blank" rel="noreferrer">PubMed</a>,{" "}
          <a href="https://reactome.org/" target="_blank" rel="noreferrer">Reactome</a>,{" "}
          <a href="https://string-db.org/" target="_blank" rel="noreferrer">STRING</a>,{" "}
          <a href="https://www.rcsb.org/" target="_blank" rel="noreferrer">PDB</a>,{" "}
          <a href="https://alphafold.ebi.ac.uk/" target="_blank" rel="noreferrer">AlphaFold DB</a>,{" "}
          <a href="https://europepmc.org/" target="_blank" rel="noreferrer">Europe PMC</a>.
        </p>
        <p className="muted">
          This project is not affiliated with the above providers. Please follow their citation and usage guidelines.
        </p>
      </footer>
    </div>
  );
}

function ConditionWheel({ data }: { data: { condition: string; count: number }[] }) {
  const total = data.reduce((sum, item) => sum + item.count, 0);
  if (!total) return null;

  let offset = 0;
  const segments = data.map((item, index) => {
    const pct = (item.count / total) * 100;
    const start = offset;
    const end = offset + pct;
    offset = end;
    return `${WHEEL_COLORS[index % WHEEL_COLORS.length]} ${start}% ${end}%`;
  });

  return (
    <div
      className="wheel"
      style={{ background: `conic-gradient(${segments.join(", ")})` }}
      aria-label="ClinVar condition distribution"
      role="img"
    />
  );
}

function AlphaFoldViewer({
  files,
  bindingSites,
  spin,
}: {
  files: { label: string; url: string }[];
  bindingSites: { label: string; start?: number; end?: number }[];
  spin: boolean;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const viewerRef = useRef<ReturnType<NonNullable<Window["$3Dmol"]>["createViewer"]> | null>(null);
  const [ready, setReady] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selection, setSelection] = useState<{
    resi?: number;
    resn?: string;
    chain?: string;
    atom?: string;
    bindingLabel?: string | null;
  } | null>(null);

  const modelUrl = useMemo(() => pickAlphaFoldModel(files), [files]);
  const modelFormat = useMemo(() => (modelUrl?.toLowerCase().includes(".cif") ? "cif" : "pdb"), [modelUrl]);

  useEffect(() => {
    if (window.$3Dmol) {
      setReady(true);
      return;
    }

    const existing = document.querySelector<HTMLScriptElement>("script[data-3dmol]");
    if (!existing) {
      const script = document.createElement("script");
      script.src = "https://3Dmol.org/build/3Dmol-min.js";
      script.async = true;
      script.dataset["3dmol"] = "true";
      script.onload = () => setReady(true);
      script.onerror = () => setError("Unable to load 3D structure viewer.");
      document.body.appendChild(script);
    } else {
      const timeout = window.setInterval(() => {
        if (window.$3Dmol) {
          setReady(true);
          window.clearInterval(timeout);
        }
      }, 200);
      return () => window.clearInterval(timeout);
    }
  }, []);

  useEffect(() => {
    if (!ready || !modelUrl || !containerRef.current || !window.$3Dmol) return;
    setError(null);
    setLoading(true);

    const controller = new AbortController();
    const viewer = viewerRef.current ?? window.$3Dmol.createViewer(containerRef.current, { backgroundColor: "#ffffff" });
    viewerRef.current = viewer;
    viewer.clear();
    if (viewer.setBackgroundColor) {
      viewer.setBackgroundColor("#ffffff");
    }

    fetch(modelUrl, { signal: controller.signal })
      .then((response) => response.text())
      .then((data) => {
        viewer.addModel(data, modelFormat);
        const bindingResidues = collectBindingResidues(bindingSites, 240);
        const applyBaseStyle = () => {
          viewer.setStyle({}, { cartoon: { color: "spectrum" } });
          if (bindingResidues.length > 0) {
            viewer.setStyle({ resi: bindingResidues }, { sphere: { color: "#f97316", radius: 1.6 } });
          }
        };
        applyBaseStyle();
        viewer.zoomTo();
        viewer.render();
        viewer.setClickable({}, true, (atom) => {
          if (!atom) return;
          applyBaseStyle();
          viewer.setStyle(
            { resi: atom.resi, chain: atom.chain },
            { stick: { color: "#2563eb", radius: 0.25 } },
          );
          const bindingLabel = resolveBindingLabel(bindingSites, atom.resi);
          setSelection({
            resi: atom.resi,
            resn: atom.resn,
            chain: atom.chain,
            atom: atom.atom,
            bindingLabel,
          });
          viewer.render();
        });
        viewer.spin(spin ? "y" : false, 0.6);
      })
      .catch((err) => {
        if (err?.name === "AbortError") return;
        setError("Unable to load AlphaFold structure.");
      })
      .finally(() => setLoading(false));

    return () => controller.abort();
  }, [ready, modelUrl, modelFormat, spin, bindingSites]);

  if (!modelUrl) {
    return <div className="viewer-placeholder">No AlphaFold model available.</div>;
  }

  return (
    <div className="mol-viewer">
      {loading && <div className="viewer-overlay">Loading structure…</div>}
      {error && <div className="viewer-overlay">{error}</div>}
      <div ref={containerRef} className="viewer-canvas" />
      {selection && (
        <div className="viewer-info">
          Selected: {selection.resn ?? "Residue"} {selection.resi ?? ""}{" "}
          {selection.chain ? `• Chain ${selection.chain}` : ""}
          {selection.atom ? ` • Atom ${selection.atom}` : ""}
          {selection.bindingLabel ? ` • ${selection.bindingLabel}` : ""}
        </div>
      )}
    </div>
  );
}

function pickAlphaFoldModel(files: { label: string; url: string }[]): string | null {
  if (!files || files.length === 0) return null;
  const preferred =
    files.find((file) => file.label.toLowerCase().includes("mmcif")) ||
    files.find((file) => file.label.toLowerCase().includes("pdb")) ||
    files[0];
  return preferred?.url || null;
}

function collectBindingResidues(
  sites: { label: string; start?: number; end?: number }[],
  limit: number,
): number[] {
  const residues = new Set<number>();
  for (const site of sites) {
    const start = site.start ?? site.end;
    const end = site.end ?? site.start;
    if (!start || !end) continue;
    const min = Math.min(start, end);
    const max = Math.max(start, end);
    for (let pos = min; pos <= max; pos += 1) {
      residues.add(pos);
      if (residues.size >= limit) return Array.from(residues);
    }
  }
  return Array.from(residues);
}

function resolveBindingLabel(
  sites: { label: string; start?: number; end?: number }[],
  residue?: number,
): string | null {
  if (!residue) return null;
  for (const site of sites) {
    if (!site.start && !site.end) continue;
    const start = site.start ?? site.end ?? residue;
    const end = site.end ?? site.start ?? residue;
    const min = Math.min(start, end);
    const max = Math.max(start, end);
    if (residue >= min && residue <= max) {
      return `Binding site: ${site.label}`;
    }
  }
  return null;
}
