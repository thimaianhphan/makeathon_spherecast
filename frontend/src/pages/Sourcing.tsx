import { useEffect, useMemo, useRef, useState } from "react";
import { AppLayout } from "@/components/AppLayout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Download, Upload, Sparkles, Leaf, Loader2 } from "lucide-react";
import { toast } from "sonner";

const BASE =
  (import.meta as { env?: { VITE_API_BASE_URL?: string } }).env
    ?.VITE_API_BASE_URL ?? "http://localhost:8000";

// ── Types ─────────────────────────────────────────────────────────────────────

interface BomEntry {
  sku: string;
  company: string;
}

interface ComponentRow {
  sku: string;
  cost_min: string;
  cost_max: string;
  purity_min: string;
  quality_min: string;
}

interface Assignment {
  sku: string;
  supplier: string;
  purity: number | null;
  quality_score: number | null;
  prices: { quantity: number; unit: string; price: number; currency: string }[];
}

interface BatchResult {
  suppliers: string[];
  assignments: Assignment[];
  uncovered: string[];
}

// ── CSV helpers ───────────────────────────────────────────────────────────────

const HEADERS = ["sku", "cost_min", "cost_max", "purity_min", "quality_min"] as const;

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

// ── Small UI pieces ───────────────────────────────────────────────────────────

const Th = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
  <th className={`px-3 py-2.5 font-medium ${className}`}>{children}</th>
);

const CellInput = ({
  value, placeholder, onChange, max,
}: {
  value: string; placeholder: string; onChange: (v: string) => void; max?: number;
}) => (
  <td className="px-1 py-1 text-right">
    <input
      inputMode="decimal"
      value={value}
      placeholder={placeholder}
      onChange={e => {
        const v = e.target.value;
        if (max !== undefined && v && Number(v) > max) return;
        onChange(v);
      }}
      className="h-8 w-full rounded-md bg-transparent px-2 text-right text-sm font-mono outline-none transition-colors placeholder:text-muted-foreground/60 hover:bg-muted focus:bg-background focus:ring-2 focus:ring-ring/40"
    />
  </td>
);

const palette = [
  "bg-blue-100 text-blue-800", "bg-purple-100 text-purple-800",
  "bg-teal-100 text-teal-800", "bg-orange-100 text-orange-800",
  "bg-pink-100 text-pink-800", "bg-indigo-100 text-indigo-800",
];

// ── Page ──────────────────────────────────────────────────────────────────────

export default function Sourcing() {
  const [boms, setBoms] = useState<BomEntry[]>([]);
  const [selectedSku, setSelectedSku] = useState("");
  const [rows, setRows] = useState<ComponentRow[]>([]);
  const [loadingBom, setLoadingBom] = useState(false);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<BatchResult | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetch(`${BASE}/api/sourcing/boms`)
      .then(r => r.json())
      .then(setBoms)
      .catch(() => setBoms([]));
  }, []);

  const selectedBom = boms.find(b => b.sku === selectedSku);

  async function handleSelect(sku: string) {
    setSelectedSku(sku);
    setResult(null);
    setRows([]);
    setLoadingBom(true);
    try {
      const components: { sku: string }[] = await fetch(
        `${BASE}/api/sourcing/bom/${encodeURIComponent(sku)}`
      ).then(r => r.json());
      setRows(components.map(c => ({
        sku: c.sku,
        cost_min: "", cost_max: "", purity_min: "", quality_min: "",
      })));
    } catch {
      toast.error("Couldn't load BOM components.");
    } finally {
      setLoadingBom(false);
    }
  }

  const updateCell = (idx: number, key: keyof ComponentRow, value: string) =>
    setRows(prev => prev.map((r, i) => i === idx ? { ...r, [key]: value } : r));

  // derive global constraints as most-permissive union across all rows
  const globalConstraints = useMemo(() => {
    if (!rows.length) return {};
    const nums = (key: keyof ComponentRow) =>
      rows.map(r => parseFloat(r[key] as string)).filter(n => !isNaN(n));
    const priceMin = nums("cost_min");
    const priceMax = nums("cost_max");
    const purityMin = nums("purity_min");
    const qualMin = nums("quality_min");
    return {
      price_min: priceMin.length ? Math.min(...priceMin) : undefined,
      price_max: priceMax.length ? Math.max(...priceMax) : undefined,
      purity_min: purityMin.length ? Math.min(...purityMin) : undefined,
      quality_min: qualMin.length ? Math.min(...qualMin) : undefined,
    };
  }, [rows]);

  async function handleOptimize() {
    if (!rows.length) { toast("Load a product first."); return; }
    setRunning(true);
    setResult(null);
    try {
      const body = { sku: selectedSku, ...globalConstraints };
      const res = await fetch(`${BASE}/api/sourcing/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? res.statusText);
      setResult(data);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  }

  function handleExport() {
    if (!rows.length) { toast("Pick a product first."); return; }
    const lines = [HEADERS.join(",")];
    for (const r of rows)
      lines.push([r.sku, r.cost_min, r.cost_max, r.purity_min, r.quality_min].map(escapeCsv).join(","));
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
    const a = Object.assign(document.createElement("a"), {
      href: URL.createObjectURL(blob),
      download: `${selectedSku || "bom"}-constraints.csv`,
    });
    a.click();
    URL.revokeObjectURL(a.href);
    toast("Exported. Edit in Sheets and re-upload when ready.");
  }

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
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
      })));
      toast(`Loaded ${body.length} ingredients.`);
    } catch (err) {
      toast.error(`Couldn't read CSV — ${err instanceof Error ? err.message : "unknown error"}`);
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  const supplierColors: Record<string, string> = {};
  (result?.suppliers ?? []).forEach((s, i) => { supplierColors[s] = palette[i % palette.length]; });

  const assignmentBySku = Object.fromEntries(
    (result?.assignments ?? []).map(a => [a.sku, a])
  );

  return (
    <AppLayout>
      <div className="mx-auto w-full max-w-5xl px-4 py-10 sm:px-6 sm:py-14 space-y-6">

        {/* Header */}
        <header>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Supplier Batching</h1>
          <p className="mt-1.5 text-sm text-muted-foreground sm:text-base">
            Lock in your bill of materials, set the guardrails, then let us find the best suppliers to fill the order.
          </p>
        </header>

        {/* Product selector */}
        <section className="rounded-2xl border bg-card p-5 shadow-sm sm:p-6">
          <label className="mb-2 flex items-center gap-2 text-sm font-medium text-foreground">
            <Leaf className="h-4 w-4 text-primary" />
            Finished Product
          </label>
          <p className="mb-3 text-sm text-muted-foreground">
            Pick a SKU and we'll pull its bill of materials below.
          </p>
          <Select value={selectedSku} onValueChange={handleSelect}>
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
                Tweak a row inline, or export → edit in Sheets → re-upload for bulk changes. Blank means no constraint.
              </p>
            </div>
            <div className="flex gap-2">
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
              <table className="w-full text-sm font-mono">
                <thead>
                  <tr className="border-b bg-muted/60 text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <Th className="min-w-[260px]">Ingredient SKU</Th>
                    <Th className="text-right">Cost floor $/kg</Th>
                    <Th className="text-right">Cost ceiling $/kg</Th>
                    <Th className="text-right">Min purity (0–1)</Th>
                    <Th className="text-right">Min quality (0–1)</Th>
                    {result && <Th>Supplier</Th>}
                    {result && <Th className="text-right">Score</Th>}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => {
                    const a = assignmentBySku[r.sku];
                    const uncovered = result?.uncovered.includes(r.sku);
                    return (
                      <tr key={r.sku} className="border-b last:border-b-0 transition-colors hover:bg-muted/20">
                        <td className="px-3 py-2 text-xs text-foreground">{r.sku}</td>
                        <CellInput value={r.cost_min} placeholder="—" onChange={v => updateCell(i, "cost_min", v)} />
                        <CellInput value={r.cost_max} placeholder="—" onChange={v => updateCell(i, "cost_max", v)} />
                        <CellInput value={r.purity_min} placeholder="—" onChange={v => updateCell(i, "purity_min", v)} max={1} />
                        <CellInput value={r.quality_min} placeholder="—" onChange={v => updateCell(i, "quality_min", v)} max={1} />
                        {result && (
                          <td className="px-3 py-2">
                            {uncovered
                              ? <Badge className="bg-destructive/10 text-destructive text-xs">uncovered</Badge>
                              : a ? <Badge className={`text-xs ${supplierColors[a.supplier] ?? ""}`}>{a.supplier}</Badge>
                              : null}
                          </td>
                        )}
                        {result && (
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

          <Button
            onClick={handleOptimize}
            disabled={!rows.length || running}
            className="mt-6 h-12 w-full rounded-xl text-base font-medium shadow-sm"
          >
            {running
              ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Finding suppliers…</>
              : <><Sparkles className="mr-2 h-4 w-4" />Find Optimal Suppliers</>}
          </Button>
        </section>

        {/* Summary */}
        {result && (
          <section className="rounded-2xl border bg-card p-5 shadow-sm sm:p-6">
            <div className="flex flex-wrap items-center gap-4">
              <div className="text-sm">
                <span className="text-muted-foreground">Covered: </span>
                <span className="font-semibold">{result.assignments.length}</span>
              </div>
              {result.uncovered.length > 0 && (
                <div className="text-sm text-destructive font-medium">
                  {result.uncovered.length} uncovered
                </div>
              )}
              <div className="flex flex-wrap gap-1 ml-auto">
                {result.suppliers.map(s => (
                  <Badge key={s} className={`text-xs ${supplierColors[s]}`}>{s}</Badge>
                ))}
              </div>
            </div>
          </section>
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
    <p className="text-sm font-medium text-foreground">No product picked yet.</p>
    <p className="mt-1 max-w-sm text-sm text-muted-foreground">
      Choose a finished SKU above and we'll lay out its ingredients here, ready for you to set cost, purity, and quality guardrails.
    </p>
  </div>
);
