// API client. Tries the FastAPI backend first; if it is unreachable, falls
// back to static JSON exported into /public/data by `python -m sherlock.build`
// so the demo still works (without natural-language questions / LLM text).
import type { Area, CaseCard, CaseFile, HomeSummary, InvestigateResult, MetroCase } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

let offline = false;
export const isOffline = () => offline;

async function fromApi<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { ...init, cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${path}`);
  return (await res.json()) as T;
}

async function fromStatic<T>(file: string): Promise<T> {
  const res = await fetch(`/data/${file}`, { cache: "force-cache" });
  if (!res.ok) throw new Error(`Static data missing: ${file}. Run \`python -m sherlock.build\`.`);
  return (await res.json()) as T;
}

let staticCases: Promise<CaseFile[]> | null = null;
let staticZipCases: Promise<CaseFile[]> | null = null;
const allStaticCases = () => (staticCases ??= fromStatic<CaseFile[]>("cases.json"));
const allStaticZipCases = () => (staticZipCases ??= fromStatic<CaseFile[]>("zip_cases.json").catch(() => [] as CaseFile[]));

export type Layer = "neighborhood" | "zip";

async function withFallback<T>(apiPath: string, fallback: () => Promise<T>): Promise<T> {
  if (!offline) {
    try {
      return await fromApi<T>(apiPath);
    } catch {
      offline = true;
    }
  }
  return fallback();
}

export const getSummary = () => withFallback<HomeSummary>("/summary", () => fromStatic("summary_home.json"));
export const getAreas = () => withFallback<Area[]>("/areas", () => fromStatic("areas.json"));
export const getGeo = (layer: Layer = "neighborhood") =>
  layer === "zip"
    ? withFallback<GeoJSON.FeatureCollection>("/geo/zips", () => fromStatic("zips.geojson"))
    : withFallback<GeoJSON.FeatureCollection>("/geo/neighborhoods", () => fromStatic("neighborhoods.geojson"));
export const getMetro = () => withFallback<MetroCase>("/metro", () => fromStatic("metro.json"));

export const getCases = (layer: Layer = "neighborhood") =>
  withFallback<CaseCard[]>(`/cases?geography=${layer}`, async () => {
    const all = await (layer === "zip" ? allStaticZipCases() : allStaticCases());
    return all
      .filter((c) => c.case_number)
      .map((c) => ({
        id: c.id, case_number: c.case_number, case_label: c.case_label, geography: c.geography, area_id: c.area_id, name: c.name, title: c.title, level: c.level,
        anomaly_score: c.anomaly_score, confidence: c.confidence.level, why_noticed: c.why_noticed.map((w) => w.headline).slice(0, 3),
      }));
  });

export const getCase = (id: string) =>
  withFallback<CaseFile>(`/cases/${encodeURIComponent(id)}`, async () => {
    const found = [...(await allStaticCases()), ...(await allStaticZipCases())].find((c) => c.id === id || c.area_id === id);
    if (!found) throw new Error(`Case ${id} not found`);
    return found;
  });

export async function explainCase(id: string): Promise<CaseFile["finding"] | null> {
  if (offline) return null;
  try {
    return await fromApi<CaseFile["finding"]>(`/cases/${encodeURIComponent(id)}/explain`);
  } catch {
    return null;
  }
}

export async function investigate(question: string): Promise<InvestigateResult> {
  if (offline) {
    return { question, results: [], message: "Questions need the Sherlock API. Start it with: uvicorn api.main:app --port 8000" };
  }
  return fromApi<InvestigateResult>("/investigate", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question }),
  });
}

// ---------------------------------------------------------------------------
// Dr. John chat
// ---------------------------------------------------------------------------
export interface ChatSource {
  tag: string;
  type: "data" | "web";
  title: string;
  url?: string | null;
  case_id?: string | null;
  excerpt: string;
}

export interface ChatReply {
  answer: string;
  provider: string;
  note?: string | null;
  web?: string;
  sources: ChatSource[];
  verification: { unmatched_numbers: string[]; causal_language: string[]; ok: boolean } | null;
  disclaimer?: string;
}

export async function askDrJohn(
  question: string,
  history: { role: "user" | "assistant"; content: string }[],
  caseId: string | null,
  mode: string,
  useWeb: boolean,
): Promise<ChatReply> {
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question, history, case_id: caseId, mode, use_web: useWeb }),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as ChatReply;
}
