import { useEffect, useMemo, useRef, useState } from "react";
import { AppLayout } from "@/components/AppLayout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Download, Upload, Sparkles, Leaf, Loader2,
  TrendingDown, TrendingUp, Users,
} from "lucide-react";
import { toast } from "sonner";

const BASE =
  (import.meta as { env?: { VITE_API_BASE_URL?: string } }).env
    ?.VITE_API_BASE_URL ?? "http://localhost:8000";

// ── Types ─────────────────────────────────────────────────────────────────────

interface BomEntry { sku: string; company: string }

interface Stats {
  price: { min: number | null; max: number | null };
  purity: { min: number | null; max: number | null };
  quality: { min: number | null; max: number | null };
}

interface ComponentRow {
  sku: string;
  cost_min: string; cost_max: string;
  purity_min: string; quality_min: string;
  stats: Stats;
}

interface Assignment {
  sku: string; supplier: string;
  purity: number | null; quality_score: number | null;
  prices: { quantity: number; unit: string; price: number; currency: string }[];
}

interface Metrics {
  supplier_count: number; covered: number; uncovered_count: number;
  coverage_pct: number; avg_quality: number | null; total_min_cost: number | null;
}

interface Deltas {
  supplier_count: number; avg_quality: number | null; total_min_cost: number | null;
}

interface Alternative {
  suppliers: string[]; assignments: Assignment[];
  uncovered: string[]; metrics: Metrics; deltas: Deltas;
}

interface BatchResponse { sku: string; alternatives: Alternative[] }

// ── CSV ───────────────────────────────────────────────────────────────────────

const CSV_HEADERS = ["sku", "cost_min", "cost_max", "purity_min", "quality_min"] as const;

const escapeCsv = (v: string) =>
  /[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v;

const parseCsv = (text: string): string[][] => {
  const rows: string[][] = [];
  let cur = "", row: string[] = [], inQ = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQ) {
      if (c === '"' && text[i + 1] === '"') { cur += '"'; i++; }
      else if (c === '"') inQ = false;
      else cur += c;
    } else {
      if (c === '"') inQ = true;
      else if (c === ',') { row.push(cur); cur = ''; }
      else if (c === '\n' || c === '\r') {
        if (c === '\r' && text[i + 1] === '\n') i++;
        row.push(cur); rows.push(row); row = []; cur = '';
      } else cur += c;
    }
  }
  if (cur.length || row.length) { row.push(cur); rows.push(row); }
  return rows.filter(r => r.some(cell => cell.trim()));
};

// ── UI atoms ──────────────────────────────────────────────────────────────────

const palette = [
  "bg-blue-100 text-blue-800", "bg-purple-100 text-purple-800",
  "bg-teal-100 text-teal-800", "bg-orange-100 text-orange-800",
  "bg-pink-100 text-pink-800", "bg-indigo-100 text-indigo-800",
];

const Th = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
  <th className={`px-3 py-2.5 font-medium ${className}`}>{children}</th>
);

const CellInput = ({ value, placeholder, onChange, max }: {
  value: string; placeholder: string; onChange: (v: string) => void; max?: number;
}) => (
  <td className="px-1 py-1 text-right">
    <input
      inputMode="decimal" value={value} placeholder={placeholder}
      onChange={e => {
        const v = e.target.value;
        if (max !== undefined && v && Number(v) > max) return;
        onChange(v);
      }}
      className="h-8 w-full rounded-md bg-transparent px-2 text-right text-sm font-mono outline-none transition-colors placeholder:text-muted-foreground/60 hover:bg-muted focus:bg-background focus:ring-2 focus:ring-ring/40"
    />
  </td>
);

function DeltaChip({ label, value, lowerIsBetter, format }: {
  label: string; value: number | null; lowerIsBetter?: boolean;
  format: (v: number) => string;
}) {
  if (value === null || value === undefined) return null;
  const good = lowerIsBetter ? value < 0 : value > 0;
  const neutral = value === 0;
  return (
    <div className={`flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-medium
      ${neutral ? "bg-muted text-muted-foreground"
        : good ? "bg-green-50 text-green-700"
        : "bg-red-50 text-red-600"}`}>
      {!neutral && (lowerIsBetter
        ? (value < 0 ? <TrendingDown className="w-3 h-3" /> : <TrendingUp className="w-3 h-3" />)
        : (value > 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />))}
      <span>{label}: {value > 0 ? "+" : ""}{format(value)}</span>
    </div>
  );
}

function AlternativeCard({ alt, index, selected, onClick }: {
  alt: Alternative; index: number; selected: boolean; onClick: () => void;
}) {
  const colors: Record<string, string> = {};
  alt.suppliers.forEach((s, i) => { colors[s] = palette[i % palette.length]; });
  const { metrics, deltas } = alt;

  return (
    <button
      onClick={onClick}
      className={`w-full text-left rounded-2xl border p-4 shadow-sm transition-all
        ${selected
          ? "border-primary ring-2 ring-primary/20 bg-primary/5"
          : "bg-card hover:border-primary/40 hover:bg-muted/30"}`}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-semibold">
          Option {index + 1}
          {index === 0 && <span className="ml-2 text-xs text-primary font-normal">recommended</span>}
        </span>
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <Users className="w-3 h-3" />
          {metrics.supplier_count} supplier{metrics.supplier_count !== 1 ? "s" : ""}
        </div>
      </div>

      <div className="flex flex-wrap gap-1 mb-3">
        {alt.suppliers.map(s => (
          <Badge key={s} className={`text-xs ${colors[s]}`}>{s}</Badge>
        ))}
        {alt.uncovered.length > 0 && (
          <Badge className="text-xs bg-destructive/10 text-destructive">
            {alt.uncovered.length} uncovered
          </Badge>
        )}
      </div>

      <div className="flex flex-wrap gap-1.5 mb-3">
        <div className="text-xs text-muted-foreground bg-muted rounded-lg px-2.5 py-1">
          {metrics.coverage_pct}% covered
        </div>
        {metrics.avg_quality !== null && (
          <div className="text-xs text-muted-foreground bg-muted rounded-lg px-2.5 py-1">
            quality {Math.round(metrics.avg_quality * 100)}%
          </div>
        )}
        {metrics.total_min_cost !== null && (
          <div className="text-xs text-muted-foreground bg-muted rounded-lg px-2.5 py-1">
            est. ${metrics.total_min_cost.toFixed(0)}
          </div>
        )}
      </div>

      {index > 0 && (
        <div className="flex flex-wrap gap-1.5">
          <DeltaChip
            label="suppliers" value={deltas.supplier_count}
            lowerIsBetter format={v => String(v)}
          />
          <DeltaChip
            label="quality" value={deltas.avg_quality}
            format={v => `${Math.round(Math.abs(v) * 100)}pp`}
          />
          <DeltaChip
            label="cost" value={deltas.total_min_cost}
            lowerIsBetter format={v => `$${Math.abs(v).toFixed(0)}`}
          />
        </div>
      )}
    </button>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function Sourcing() {
  const [boms, setBoms] = useState<BomEntry[]>([]);
  const [selectedSku, setSelectedSku] = useState("");
  const [rows, setRows] = useState<ComponentRow[]>([]);
  const [loadingBom, setLoadingBom] = useState(false);
  const [selectOpen, setSelectOpen] = useState(false);
  const [running, setRunning] = useState(false);
  const [response, setResponse] = useState<BatchResponse | null>(null);
  const [activeAlt, setActiveAlt] = useState(0);
  const [includeIncomplete, setIncludeIncomplete] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetch(`${BASE}/api/sourcing/boms`)
      .then(r => r.json())
      .then((data: BomEntry[]) => { setBoms(data); setSelectOpen(true); })
      .catch(() => setBoms([]));
  }, []);

  const emptyStats = (): Stats => ({
    price: { min: null, max: null },
    purity: { min: null, max: null },
    quality: { min: null, max: null },
  });

  async function handleSelect(sku: string) {
    setSelectedSku(sku); setResponse(null); setRows([]); setActiveAlt(0);
    setLoadingBom(true);
    try {
      const components: { sku: string; stats: Stats }[] = await fetch(
        `${BASE}/api/sourcing/bom/${encodeURIComponent(sku)}`
      ).then(r => r.json());
      setRows(components.map(c => ({
        sku: c.sku, cost_min: "", cost_max: "", purity_min: "", quality_min: "",
        stats: c.stats ?? emptyStats(),
      })));
    } catch { toast.error("Couldn't load BOM components."); }
    finally { setLoadingBom(false); }
  }

  const updateCell = (idx: number, key: keyof ComponentRow, value: string) =>
    setRows(prev => prev.map((r, i) => i === idx ? { ...r, [key]: value } : r));

  const globalConstraints = useMemo(() => {
    if (!rows.length) return {};
    const nums = (key: keyof ComponentRow) =>
      rows.map(r => parseFloat(r[key] as string)).filter(n => !isNaN(n));
    const priceMin = nums("cost_min"), priceMax = nums("cost_max");
    const purityMin = nums("purity_min"), qualMin = nums("quality_min");
    return {
      price_min: priceMin.length ? Math.min(...priceMin) : undefined,
      price_max: priceMax.length ? Math.max(...priceMax) : undefined,
      purity_min: purityMin.length ? Math.min(...purityMin) : undefined,
      quality_min: qualMin.length ? Math.min(...qualMin) : undefined,
    };
  }, [rows]);

  async function handleOptimize() {
    if (!rows.length) { toast("Load a product first."); return; }
    setRunning(true); setResponse(null); setActiveAlt(0);
    try {
      const body = { sku: selectedSku, ...globalConstraints, include_incomplete: includeIncomplete };
      const res = await fetch(`${BASE}/api/sourcing/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? res.statusText);
      setResponse(data);
    } catch (e) { toast.error(e instanceof Error ? e.message : String(e)); }
    finally { setRunning(false); }
  }

  function handleExport() {
    if (!rows.length) { toast("Pick a product first."); return; }
    const lines = [CSV_HEADERS.join(",")];
    for (const r of rows)
      lines.push([r.sku, r.cost_min, r.cost_max, r.purity_min, r.quality_min].map(escapeCsv).join(","));
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
    const a = Object.assign(document.createElement("a"), {
      href: URL.createObjectURL(blob), download: `${selectedSku || "bom"}-constraints.csv`,
    });
    a.click(); URL.revokeObjectURL(a.href);
    toast("Exported.");
  }

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; if (!file) return;
    try {
      const parsed = parseCsv(await file.text());
      if (!parsed.length) throw new Error("Empty file");
      const [header, ...body] = parsed;
      const idx = Object.fromEntries(header.map((h, i) => [h.trim().toLowerCase(), i]));
      if (!("sku" in idx)) throw new Error("Missing 'sku' column");
      setRows(body.map(cells => ({
        sku: cells[idx.sku]?.trim() ?? "",
        cost_min: cells[idx.cost_min]?.trim() ?? "",
        cost_max: cells[idx.cost_max]?.trim() ?? "",
        purity_min: cells[idx.purity_min]?.trim() ?? "",
        quality_min: cells[idx.quality_min]?.trim() ?? "",
        stats: emptyStats(),
      })));
      toast(`Loaded ${body.length} ingredients.`);
    } catch (err) {
      toast.error(`Couldn't read CSV — ${err instanceof Error ? err.message : "unknown error"}`);
    } finally { if (fileRef.current) fileRef.current.value = ""; }
  }

  const currentAlt = response?.alternatives[activeAlt] ?? null;
  const supplierColors: Record<string, string> = {};
  currentAlt?.suppliers.forEach((s, i) => { supplierColors[s] = palette[i % palette.length]; });
  const assignmentBySku = Object.fromEntries((currentAlt?.assignments ?? []).map(a => [a.sku, a]));

  return (
    <AppLayout>
      <div className="mx-auto w-full max-w-5xl px-4 py-10 sm:px-6 sm:py-14 space-y-6">

        <header>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Supplier Batching</h1>
          <p className="mt-1.5 text-sm text-muted-foreground sm:text-base">
            Lock in your bill of materials, set the guardrails, then let us find the best suppliers to fill the order.
          </p>
        </header>

        {/* Product selector */}
        <section className="rounded-2xl border bg-card p-5 shadow-sm sm:p-6">
          <label className="mb-2 flex items-center gap-2 text-sm font-medium">
            <Leaf className="h-4 w-4 text-primary" /> Finished Product
          </label>
          <p className="mb-3 text-sm text-muted-foreground">
            Pick a SKU and we'll pull its bill of materials below.
          </p>
          <Select value={selectedSku} onValueChange={handleSelect} open={selectOpen} onOpenChange={setSelectOpen}>
            <SelectTrigger className="h-11 rounded-xl bg-background">
              <SelectValue placeholder="Choose a finished product…" />
            </SelectTrigger>
            <SelectContent>
              {boms.map(b => (
                <SelectItem key={b.sku} value={b.sku}>
                  <span className="font-medium">{b.company}</span>
                  <span className="ml-2 text-xs text-muted-foreground font-mono">{b.sku}</span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </section>

        {/* Constraint editor */}
        <section className="rounded-2xl border bg-card p-5 shadow-sm sm:p-6">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-base font-semibold">Ingredient constraints</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Tweak inline, or export → edit in Sheets → re-upload. Blank = no constraint.
              </p>
            </div>
            <div className="flex gap-2 flex-wrap">
              <Button variant="outline" size="sm" onClick={handleExport} className="rounded-xl">
                <Download className="mr-1.5 h-4 w-4" /> Export CSV
              </Button>
              <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()} className="rounded-xl">
                <Upload className="mr-1.5 h-4 w-4" /> Upload CSV
              </Button>
              <input ref={fileRef} type="file" accept=".csv,text/csv" className="hidden" onChange={handleFile} />
            </div>
          </div>

          {loadingBom ? (
            <div className="flex items-center justify-center py-14 text-muted-foreground">
              <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading components…
            </div>
          ) : rows.length === 0 ? (
            <EmptyState />
          ) : (
            <div className="overflow-x-auto rounded-xl border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/60 text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <Th className="min-w-[240px]">Ingredient SKU</Th>
                    <Th className="text-right">Cost floor $/kg</Th>
                    <Th className="text-right">Cost ceil $/kg</Th>
                    <Th className="text-right">Min purity</Th>
                    <Th className="text-right">Min quality</Th>
                    {currentAlt && <Th>Supplier</Th>}
                    {currentAlt && <Th className="text-right">Quality</Th>}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => {
                    const a = assignmentBySku[r.sku];
                    const uncovered = currentAlt?.uncovered.includes(r.sku);
                    return (
                      <tr key={r.sku} className="border-b last:border-b-0 hover:bg-muted/20">
                        <td className="px-3 py-2 font-mono text-xs">{r.sku}</td>
                        <CellInput value={r.cost_min} placeholder={r.stats.price.min != null ? String(r.stats.price.min) : "—"} onChange={v => updateCell(i, "cost_min", v)} />
                        <CellInput value={r.cost_max} placeholder={r.stats.price.max != null ? String(r.stats.price.max) : "—"} onChange={v => updateCell(i, "cost_max", v)} />
                        <CellInput value={r.purity_min} placeholder={r.stats.purity.min != null ? String(r.stats.purity.min) : "—"} onChange={v => updateCell(i, "purity_min", v)} max={1} />
                        <CellInput value={r.quality_min} placeholder={r.stats.quality.min != null ? String(r.stats.quality.min) : "—"} onChange={v => updateCell(i, "quality_min", v)} max={1} />
                        {currentAlt && (
                          <td className="px-3 py-2">
                            {uncovered
                              ? <Badge className="bg-destructive/10 text-destructive text-xs">uncovered</Badge>
                              : a ? <Badge className={`text-xs ${supplierColors[a.supplier] ?? ""}`}>{a.supplier}</Badge>
                              : null}
                          </td>
                        )}
                        {currentAlt && (
                          <td className="px-3 py-2 text-right font-mono text-xs">
                            {a?.quality_score != null
                              ? <span className={a.quality_score >= 0.7 ? "text-green-600" : a.quality_score >= 0.4 ? "text-yellow-600" : "text-red-500"}>
                                  {Math.round(a.quality_score * 100)}%
                                </span>
                              : <span className="text-muted-foreground">—</span>}
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer select-none">
              <Switch checked={includeIncomplete} onCheckedChange={setIncludeIncomplete} />
              Include incomplete alternatives
            </label>
            <Button
              onClick={handleOptimize}
              disabled={!rows.length || running}
              className="h-12 w-full sm:w-auto px-8 rounded-xl text-base font-medium shadow-sm"
            >
              {running
                ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Finding suppliers…</>
                : <><Sparkles className="mr-2 h-4 w-4" />Find Optimal Suppliers</>}
            </Button>
          </div>
        </section>

        {/* Alternatives */}
        {response && response.alternatives.length > 0 && (
          <section className="space-y-3">
            <h2 className="text-sm font-semibold px-1">
              {response.alternatives.length} alternative{response.alternatives.length !== 1 ? "s" : ""} found
              <span className="ml-2 font-normal text-muted-foreground">— click to view in table above</span>
            </h2>
            <div className="grid gap-3 sm:grid-cols-3">
              {response.alternatives.map((alt, i) => (
                <AlternativeCard
                  key={i} alt={alt} index={i}
                  selected={activeAlt === i}
                  onClick={() => setActiveAlt(i)}
                />
              ))}
            </div>
          </section>
        )}

        {response && response.alternatives.length === 0 && (
          <div className="rounded-2xl border bg-card p-8 text-center text-sm text-muted-foreground">
            No valid alternatives found. Try enabling "include incomplete" or relaxing constraints.
          </div>
        )}
      </div>
    </AppLayout>
  );
}

const EmptyState = () => (
  <div className="flex flex-col items-center justify-center rounded-xl border border-dashed bg-muted/40 px-6 py-14 text-center">
    <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
      <Leaf className="h-5 w-5 text-primary" />
    </div>
    <p className="text-sm font-medium">No product picked yet.</p>
    <p className="mt-1 max-w-sm text-sm text-muted-foreground">
      Choose a finished SKU above and we'll lay out its ingredients, ready for you to set cost, purity, and quality guardrails.
    </p>
  </div>
);
