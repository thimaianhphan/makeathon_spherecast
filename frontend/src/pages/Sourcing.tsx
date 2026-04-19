import { useEffect, useMemo, useRef, useState } from "react";
import { AppLayout } from "@/components/AppLayout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Download, Upload, Sparkles, Leaf, Loader2, TrendingDown, TrendingUp, Users,
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

// ── Palette ───────────────────────────────────────────────────────────────────

const palette = [
  "bg-blue-100 text-blue-800", "bg-purple-100 text-purple-800",
  "bg-teal-100 text-teal-800", "bg-orange-100 text-orange-800",
  "bg-pink-100 text-pink-800", "bg-indigo-100 text-indigo-800",
];

// ── Atoms ─────────────────────────────────────────────────────────────────────

const CompactInput = ({ value, placeholder, onChange, max }: {
  value: string; placeholder: string; onChange: (v: string) => void; max?: number;
}) => (
  <td className="px-1 py-0.5 text-right">
    <input
      inputMode="decimal" value={value} placeholder={placeholder}
      onChange={e => {
        const v = e.target.value;
        if (max !== undefined && v && Number(v) > max) return;
        onChange(v);
      }}
      className="h-7 w-full rounded bg-transparent px-2 text-right text-[11px] font-mono outline-none transition-colors placeholder:text-muted-foreground/35 hover:bg-muted focus:bg-background focus:ring-1 focus:ring-ring/40"
    />
  </td>
);

const Metric = ({ value, label }: { value: string; label: string }) => (
  <span className="inline-flex items-baseline rounded bg-muted px-2 py-0.5 text-[11px]">
    <span className="font-medium text-foreground">{value}</span>
    <span className="ml-1 text-muted-foreground">{label}</span>
  </span>
);

function QualityScore({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const cls = score >= 0.7 ? "text-green-600" : score >= 0.4 ? "text-amber-600" : "text-red-500";
  return <span className={`font-mono text-[11px] ${cls}`}>{pct}%</span>;
}

function DeltaChip({ label, value, lowerIsBetter, format }: {
  label: string; value: number | null; lowerIsBetter?: boolean; format: (v: number) => string;
}) {
  if (value === null || value === undefined) return null;
  const good = lowerIsBetter ? value < 0 : value > 0;
  const neutral = value === 0;
  return (
    <span className={`inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-medium
      ${neutral ? "bg-muted text-muted-foreground"
        : good ? "bg-green-50 text-green-700"
        : "bg-red-50 text-red-600"}`}>
      {!neutral && (lowerIsBetter
        ? (value < 0 ? <TrendingDown className="w-2.5 h-2.5" /> : <TrendingUp className="w-2.5 h-2.5" />)
        : (value > 0 ? <TrendingUp className="w-2.5 h-2.5" /> : <TrendingDown className="w-2.5 h-2.5" />))}
      <span>{label} {value > 0 ? "+" : ""}{format(value)}</span>
    </span>
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function SkeletonTable() {
  return (
    <div className="divide-y divide-border">
      {Array.from({ length: 9 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-4 py-2.5 animate-pulse">
          <div className="h-2 rounded bg-muted" style={{ width: `${100 + (i % 4) * 30}px` }} />
          <div className="ml-auto flex gap-4">
            {[52, 52, 40, 40].map((w, j) => (
              <div key={j} className="h-2 rounded bg-muted" style={{ width: w }} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Empty states ──────────────────────────────────────────────────────────────

function EmptyConstraints() {
  return (
    <div className="h-full flex flex-col items-center justify-center gap-3 text-center px-6">
      <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
        <Leaf className="h-5 w-5 text-primary" />
      </div>
      <div>
        <p className="text-xs font-medium text-foreground">No product selected</p>
        <p className="mt-1 text-[11px] text-muted-foreground max-w-xs">
          Pick a finished good from the selector above to load its ingredient list.
        </p>
      </div>
    </div>
  );
}

function EmptyAlternatives({ hasRows }: { hasRows: boolean }) {
  return (
    <div className="h-full flex flex-col items-center justify-center gap-3 text-center px-4">
      <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center">
        <Sparkles className="w-4 h-4 text-muted-foreground" />
      </div>
      <div>
        <p className="text-xs font-medium text-foreground">
          {hasRows ? "Ready to optimise" : "Select a product first"}
        </p>
        <p className="mt-1 text-[11px] text-muted-foreground max-w-[200px]">
          {hasRows
            ? "Set constraints then click Find Suppliers"
            : "Pick a finished good from the top bar"}
        </p>
      </div>
    </div>
  );
}

// ── Alternative card ──────────────────────────────────────────────────────────

function AlternativeCard({ alt, index, selected, onClick }: {
  alt: Alternative; index: number; selected: boolean; onClick: () => void;
}) {
  const colors: Record<string, string> = {};
  alt.suppliers.forEach((s, i) => { colors[s] = palette[i % palette.length]; });
  const { metrics, deltas } = alt;

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={e => (e.key === "Enter" || e.key === " ") && onClick()}
      aria-pressed={selected}
      className={`rounded-lg border cursor-pointer p-3 transition-all select-none
        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring
        ${selected
          ? "border-primary ring-1 ring-primary/30 bg-primary/5"
          : "border-border bg-card hover:border-primary/40 hover:bg-muted/20"}`}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] font-semibold text-foreground">Option {index + 1}</span>
          {index === 0 && (
            <span className="text-[10px] text-primary bg-primary/10 px-1.5 py-px rounded-full font-medium">
              recommended
            </span>
          )}
        </div>
        <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
          <Users className="w-3 h-3" />
          <span>{metrics.supplier_count} supplier{metrics.supplier_count !== 1 ? "s" : ""}</span>
        </div>
      </div>

      <div className="flex flex-wrap gap-1 mb-2">
        {alt.suppliers.map(s => (
          <Badge key={s} className={`text-[10px] px-1.5 py-px leading-tight ${colors[s]}`}>{s}</Badge>
        ))}
        {alt.uncovered.length > 0 && (
          <Badge className="text-[10px] px-1.5 py-px leading-tight bg-destructive/10 text-destructive">
            {alt.uncovered.length} uncovered
          </Badge>
        )}
      </div>

      <div className="flex flex-wrap gap-1 mb-2">
        <Metric value={`${metrics.coverage_pct}%`} label="covered" />
        {metrics.avg_quality !== null && (
          <Metric value={`${Math.round(metrics.avg_quality * 100)}%`} label="quality" />
        )}
        {metrics.total_min_cost !== null && (
          <Metric value={`$${metrics.total_min_cost.toFixed(0)}`} label="est." />
        )}
      </div>

      {index > 0 && (
        <div className="flex flex-wrap gap-1 pt-2 border-t border-border">
          <DeltaChip label="suppliers" value={deltas.supplier_count} lowerIsBetter format={v => `${v > 0 ? "+" : ""}${v}`} />
          <DeltaChip label="quality" value={deltas.avg_quality} format={v => `${Math.round(Math.abs(v) * 100)}pp`} />
          <DeltaChip label="cost" value={deltas.total_min_cost} lowerIsBetter format={v => `$${Math.abs(v).toFixed(0)}`} />
        </div>
      )}
    </div>
  );
}

// ── Constraint table ──────────────────────────────────────────────────────────

interface ConstraintTableProps {
  rows: ComponentRow[];
  currentAlt: Alternative | null;
  supplierColors: Record<string, string>;
  assignmentBySku: Record<string, Assignment>;
  updateCell: (idx: number, key: keyof ComponentRow, value: string) => void;
}

function ConstraintTable({ rows, currentAlt, supplierColors, assignmentBySku, updateCell }: ConstraintTableProps) {
  return (
    <table className="w-full text-xs border-collapse">
      <thead className="sticky top-0 z-10">
        <tr className="border-b bg-muted/80 backdrop-blur-sm text-left text-[11px] uppercase tracking-wide text-muted-foreground">
          <th className="px-4 py-2.5 font-medium min-w-[200px]">Ingredient SKU</th>
          <th className="px-3 py-2.5 font-medium text-right whitespace-nowrap">Cost floor $/kg</th>
          <th className="px-3 py-2.5 font-medium text-right whitespace-nowrap">Cost ceil $/kg</th>
          <th className="px-3 py-2.5 font-medium text-right whitespace-nowrap">Min purity</th>
          <th className="px-3 py-2.5 font-medium text-right whitespace-nowrap">Min quality</th>
          {currentAlt && <th className="px-3 py-2.5 font-medium">Supplier</th>}
          {currentAlt && <th className="px-3 py-2.5 font-medium text-right">Quality</th>}
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => {
          const a = assignmentBySku[r.sku];
          const uncovered = currentAlt?.uncovered.includes(r.sku);
          return (
            <tr
              key={r.sku}
              className="border-b last:border-b-0 transition-colors hover:bg-muted/20 motion-safe:animate-in motion-safe:fade-in motion-safe:duration-200"
              style={{ animationDelay: `${Math.min(i * 20, 300)}ms` }}
            >
              <td className="px-4 py-2 font-mono text-[11px] text-foreground">{r.sku}</td>
              <CompactInput value={r.cost_min} placeholder={r.stats.price.min != null ? String(r.stats.price.min) : "—"} onChange={v => updateCell(i, "cost_min", v)} />
              <CompactInput value={r.cost_max} placeholder={r.stats.price.max != null ? String(r.stats.price.max) : "—"} onChange={v => updateCell(i, "cost_max", v)} />
              <CompactInput value={r.purity_min} placeholder={r.stats.purity.min != null ? String(r.stats.purity.min) : "—"} onChange={v => updateCell(i, "purity_min", v)} max={1} />
              <CompactInput value={r.quality_min} placeholder={r.stats.quality.min != null ? String(r.stats.quality.min) : "—"} onChange={v => updateCell(i, "quality_min", v)} max={1} />
              {currentAlt && (
                <td className="px-3 py-2">
                  {uncovered
                    ? <Badge className="bg-destructive/10 text-destructive text-[10px] px-1.5 py-px">uncovered</Badge>
                    : a
                    ? <Badge className={`text-[10px] px-1.5 py-px ${supplierColors[a.supplier] ?? ""}`}>{a.supplier}</Badge>
                    : <span className="text-[11px] text-muted-foreground">—</span>}
                </td>
              )}
              {currentAlt && (
                <td className="px-3 py-2 text-right">
                  {a?.quality_score != null
                    ? <QualityScore score={a.quality_score} />
                    : <span className="font-mono text-[11px] text-muted-foreground">—</span>}
                </td>
              )}
            </tr>
          );
        })}
      </tbody>
    </table>
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

  const tableProps: ConstraintTableProps = { rows, currentAlt, supplierColors, assignmentBySku, updateCell };

  const tableContent = loadingBom
    ? <SkeletonTable />
    : rows.length === 0
    ? <EmptyConstraints />
    : <ConstraintTable {...tableProps} />;

  return (
    <AppLayout>
      <div className="flex flex-col h-screen">

        {/* ── Top bar ─────────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between gap-3 px-4 h-12 border-b border-border shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <span className="text-xs font-semibold text-foreground shrink-0">Supplier Batching</span>
            <span className="text-border shrink-0">|</span>
            <Select value={selectedSku} onValueChange={handleSelect} open={selectOpen} onOpenChange={setSelectOpen}>
              <SelectTrigger className="h-7 min-w-[160px] max-w-[240px] rounded-md border-border bg-background px-2 text-xs">
                <SelectValue placeholder="Choose a product…" />
              </SelectTrigger>
              <SelectContent>
                {boms.map(b => (
                  <SelectItem key={b.sku} value={b.sku}>
                    <span className="font-medium text-xs">{b.company}</span>
                    <span className="ml-2 text-[11px] text-muted-foreground font-mono">{b.sku}</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {rows.length > 0 && !loadingBom && (
              <span className="hidden sm:inline text-[11px] text-muted-foreground shrink-0">
                {rows.length} ingredient{rows.length !== 1 ? "s" : ""}
              </span>
            )}
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {currentAlt && (
              <>
                <span className="hidden lg:inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-[11px] font-medium text-green-700">
                  {currentAlt.metrics.covered} covered
                </span>
                {currentAlt.metrics.uncovered_count > 0 && (
                  <span className="hidden lg:inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-[11px] font-medium text-red-700">
                    {currentAlt.metrics.uncovered_count} uncovered
                  </span>
                )}
              </>
            )}
            <label className="hidden md:flex items-center gap-1.5 text-[11px] text-muted-foreground cursor-pointer select-none">
              <Switch checked={includeIncomplete} onCheckedChange={setIncludeIncomplete} />
              All results
            </label>
            <Button variant="outline" size="sm" onClick={handleExport}
              className="hidden sm:inline-flex h-7 px-2.5 text-[11px] gap-1.5">
              <Download className="w-3 h-3" /> Export
            </Button>
            <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()}
              className="hidden sm:inline-flex h-7 px-2.5 text-[11px] gap-1.5">
              <Upload className="w-3 h-3" /> Import
            </Button>
            <input ref={fileRef} type="file" accept=".csv,text/csv" className="hidden" onChange={handleFile} />
            <Button
              onClick={handleOptimize}
              disabled={!rows.length || running}
              className="h-7 px-3 text-[11px] gap-1.5"
            >
              {running
                ? <><Loader2 className="w-3 h-3 animate-spin" />Optimising…</>
                : <><Sparkles className="w-3 h-3" />Find Suppliers</>}
            </Button>
          </div>
        </div>

        {/* ── Desktop: two-panel ──────────────────────────────────────────── */}
        <div className="flex-1 hidden md:flex overflow-hidden">

          {/* Left: constraint editor */}
          <div className="flex-1 flex flex-col overflow-hidden border-r border-border">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-foreground">
                Ingredient Constraints
              </p>
              <p className="text-[11px] text-muted-foreground">Blank = no constraint</p>
            </div>
            <div className="flex-1 overflow-auto">
              {tableContent}
            </div>
          </div>

          {/* Right: alternatives */}
          <div className="w-[300px] shrink-0 flex flex-col overflow-hidden">
            <div className="px-4 py-3 border-b border-border shrink-0">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-foreground">
                {response
                  ? `${response.alternatives.length} alternative${response.alternatives.length !== 1 ? "s" : ""} found`
                  : "Alternatives"}
              </p>
            </div>

            <div className="flex-1 overflow-y-auto p-3 space-y-2">
              {!response && !running && <EmptyAlternatives hasRows={rows.length > 0} />}

              {running && (
                <div className="h-full flex flex-col items-center justify-center gap-3 text-muted-foreground">
                  <Loader2 className="w-5 h-5 animate-spin text-primary" />
                  <p className="text-[11px]">Finding optimal suppliers…</p>
                </div>
              )}

              {response?.alternatives.length === 0 && !running && (
                <div className="h-full flex flex-col items-center justify-center gap-2 text-center px-4">
                  <p className="text-xs font-medium text-foreground">No alternatives found</p>
                  <p className="text-[11px] text-muted-foreground">
                    Try enabling "All results" or relaxing constraints.
                  </p>
                </div>
              )}

              {response?.alternatives.map((alt, i) => (
                <div
                  key={i}
                  className="motion-safe:animate-in motion-safe:fade-in motion-safe:duration-300"
                  style={{ animationDelay: `${i * 70}ms` }}
                >
                  <AlternativeCard
                    alt={alt} index={i}
                    selected={activeAlt === i}
                    onClick={() => setActiveAlt(i)}
                  />
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── Mobile: tabbed ──────────────────────────────────────────────── */}
        <div className="flex-1 md:hidden overflow-hidden">
          <Tabs defaultValue="constraints" className="flex flex-col h-full">
            <TabsList className="grid w-full grid-cols-2 shrink-0 rounded-none border-b border-border">
              <TabsTrigger value="constraints" className="text-xs">Constraints</TabsTrigger>
              <TabsTrigger value="results" className="text-xs">
                Results{response ? ` (${response.alternatives.length})` : ""}
              </TabsTrigger>
            </TabsList>

            <TabsContent value="constraints" className="flex-1 overflow-hidden m-0 flex flex-col">
              <div className="flex gap-2 p-2 border-b border-border shrink-0">
                <Button variant="outline" size="sm" onClick={handleExport} className="h-7 flex-1 text-[11px] gap-1">
                  <Download className="w-3 h-3" /> Export
                </Button>
                <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()} className="h-7 flex-1 text-[11px] gap-1">
                  <Upload className="w-3 h-3" /> Import
                </Button>
                <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground cursor-pointer select-none px-1">
                  <Switch checked={includeIncomplete} onCheckedChange={setIncludeIncomplete} />
                  All
                </label>
              </div>
              <div className="flex-1 overflow-x-auto overflow-y-auto">
                {tableContent}
              </div>
              <div className="p-3 border-t border-border shrink-0">
                <Button onClick={handleOptimize} disabled={!rows.length || running} className="w-full h-8 text-xs gap-1.5">
                  {running
                    ? <><Loader2 className="w-3 h-3 animate-spin" />Optimising…</>
                    : <><Sparkles className="w-3 h-3" />Find Suppliers</>}
                </Button>
              </div>
            </TabsContent>

            <TabsContent value="results" className="flex-1 overflow-auto m-0 p-3 space-y-2">
              {!response && !running && <EmptyAlternatives hasRows={rows.length > 0} />}
              {running && (
                <div className="flex flex-col items-center justify-center h-full gap-3">
                  <Loader2 className="w-5 h-5 animate-spin text-primary" />
                  <p className="text-[11px] text-muted-foreground">Finding optimal suppliers…</p>
                </div>
              )}
              {response?.alternatives.map((alt, i) => (
                <div
                  key={i}
                  className="motion-safe:animate-in motion-safe:fade-in motion-safe:duration-200"
                  style={{ animationDelay: `${i * 60}ms` }}
                >
                  <AlternativeCard alt={alt} index={i} selected={activeAlt === i} onClick={() => setActiveAlt(i)} />
                </div>
              ))}
            </TabsContent>
          </Tabs>
        </div>

      </div>
    </AppLayout>
  );
}
