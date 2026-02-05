import { sampleDossier } from "./sampleDossier";
import type { Annotation, Dossier, Variant } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api";
const ENABLE_DEMO_FALLBACK = import.meta.env.VITE_ENABLE_DEMO_FALLBACK === "true";

export type DossierResult = {
  dossier: Dossier | null;
  fallback: boolean;
  notFound?: boolean;
};

export type DossierOptions = {
  organismTaxonId?: number;
  topic?: string;
  variantPage?: number;
  variantPageSize?: number;
  variantSort?: "significance" | "date";
  literaturePage?: number;
  literaturePageSize?: number;
  literatureYearFrom?: number;
  literatureYearTo?: number;
  literatureSort?: "date" | "relevance" | "citation" | "ml";
};

export async function fetchDossier(query: string, options: DossierOptions = {}): Promise<DossierResult> {
  try {
    const params = new URLSearchParams();
    if (options.organismTaxonId) params.set("organism_taxon_id", String(options.organismTaxonId));
    if (options.topic) params.set("topic", options.topic);
    if (options.variantPage) params.set("variant_page", String(options.variantPage));
    if (options.variantPageSize) params.set("variant_page_size", String(options.variantPageSize));
    if (options.variantSort) params.set("variant_sort", options.variantSort);
    if (options.literaturePage) params.set("literature_page", String(options.literaturePage));
    if (options.literaturePageSize) params.set("literature_page_size", String(options.literaturePageSize));
    if (options.literatureYearFrom) params.set("literature_year_from", String(options.literatureYearFrom));
    if (options.literatureYearTo) params.set("literature_year_to", String(options.literatureYearTo));
    if (options.literatureSort) params.set("literature_sort", options.literatureSort);

    const res = await fetch(
      `${API_BASE}/proteins/${encodeURIComponent(query)}/dossier?${params.toString()}`,
    );
    if (res.status === 404) {
      return { dossier: null, fallback: false, notFound: true };
    }
    if (!res.ok) {
      throw new Error("Failed to fetch dossier");
    }
    const dossier = (await res.json()) as Dossier;
    return { dossier, fallback: false };
  } catch {
    if (ENABLE_DEMO_FALLBACK) {
      return { dossier: { ...sampleDossier, query }, fallback: true };
    }
    return { dossier: null, fallback: false, notFound: true };
  }
}

export async function fetchNotes(query: string): Promise<Annotation[]> {
  try {
    const res = await fetch(`${API_BASE}/proteins/${encodeURIComponent(query)}/notes`);
    if (!res.ok) {
      return [];
    }
    return (await res.json()) as Annotation[];
  } catch {
    return [];
  }
}

export async function addNote(query: string, content: string, token: string): Promise<Annotation> {
  const res = await fetch(`${API_BASE}/proteins/${encodeURIComponent(query)}/notes`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ content }),
  });
  if (!res.ok) {
    throw new Error("Failed to save note");
  }
  return (await res.json()) as Annotation;
}

export async function login(email: string, password: string): Promise<string> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    throw new Error("Login failed");
  }
  const data = (await res.json()) as { access_token: string };
  return data.access_token;
}

export async function register(email: string, password: string, fullName?: string): Promise<void> {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, full_name: fullName, role: "member" }),
  });
  if (!res.ok) {
    throw new Error("Registration failed");
  }
}

export async function exportVariants(query: string, variants: Variant[]): Promise<Blob> {
  try {
    const res = await fetch(`${API_BASE}/export/variants?query=${encodeURIComponent(query)}`);
    if (res.ok) {
      return await res.blob();
    }
  } catch {
    // fallback below
  }

  const header = [
    "variant_id",
    "hgvs",
    "protein_change",
    "aa_position",
    "classification",
    "condition",
    "species",
    "review_status",
    "conflicts",
    "pmids",
  ];
  const rows = variants.map((variant) => [
    variant.variant_id,
    variant.hgvs || "",
    variant.protein_change || "",
    variant.aa_position || "",
    variant.classification || "",
    variant.condition || "",
    variant.species || "",
    variant.review_status || "",
    (variant.conflicts || []).join("; "),
    (variant.pmids || []).join("; "),
  ]);

  const csv = [header, ...rows]
    .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(","))
    .join("\n");

  return new Blob([csv], { type: "text/csv" });
}
