import { useEffect, useState } from "react";
import { AppLayout } from "@/components/AppLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Loader2, PackageSearch, ChevronDown, ChevronUp } from "lucide-react";

const BASE = (import.meta as { env?: { VITE_API_BASE_URL?: string } }).env?.VITE_API_BASE_URL ?? "http://localhost:8000";

interface BomEntry { sku: string; company: string }

interface Assignment {
  sku: string;
  supplier: string;
  purity: number | null;
  quality_score: number | null;
  prices: { quantity: number; unit: string; price: number; currency: string }[];
}

interface BatchResult {
  sku: string;
  suppliers: string[];
  assignments: Assignment[];
  uncovered: string[];
}

function fmtScore(v: number | null) {
  if (v === null || v === undefined) return <span className="text-muted-foreground text-xs">—</span>;
  const pct = Math.round(v * 100);
  const color = pct >= 70 ? "text-green-600" : pct >= 40 ? "text-yellow-600" : "text-red-500";
  return <span className={`font-mono text-xs ${color}`}>{pct}%</span>;
}

function fmtPurity(v: number | null) {
  if (v === null || v === undefined) return <span className="text-muted-foreground text-xs">—</span>;
  return <span className="font-mono text-xs">{(v * 100).toFixed(1)}%</span>;
}

function PriceCell({ prices }: { prices: Assignment["prices"] }) {
  const [open, setOpen] = useState(false);
  if (!prices.length) return <span className="text-muted-foreground text-xs">—</span>;
  const first = prices[0];
  return (
    <div>
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1 text-xs font-mono hover:underline"
      >
        ${first.price.toFixed(2)}/{first.unit}
        {prices.length > 1 && (open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />)}
      </button>
      {open && prices.length > 1 && (
        <div className="mt-1 space-y-0.5">
          {prices.slice(1).map((p, i) => (
            <div key={i} className="text-xs text-muted-foreground font-mono">
              {p.quantity}{p.unit}: ${p.price.toFixed(2)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Sourcing() {
  const [boms, setBoms] = useState<BomEntry[]>([]);
  const [search, setSearch] = useState("");
  const [selectedSku, setSelectedSku] = useState("");
  const [showDropdown, setShowDropdown] = useState(false);

  const [priceMin, setPriceMin] = useState("");
  const [priceMax, setPriceMax] = useState("");
  const [purityMin, setPurityMin] = useState("");
  const [qualityMin, setQualityMin] = useState("");

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BatchResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${BASE}/api/sourcing/boms`)
      .then(r => r.json())
      .then(setBoms)
      .catch(() => setBoms([]));
  }, []);

  const filtered = boms.filter(b =>
    b.sku.toLowerCase().includes(search.toLowerCase()) ||
    b.company.toLowerCase().includes(search.toLowerCase())
  ).slice(0, 20);

  function selectSku(sku: string) {
    setSelectedSku(sku);
    setSearch(sku);
    setShowDropdown(false);
    setResult(null);
    setError(null);
  }

  async function runBatch() {
    if (!selectedSku) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const body: Record<string, string | number> = { sku: selectedSku };
      if (priceMin) body.price_min = parseFloat(priceMin);
      if (priceMax) body.price_max = parseFloat(priceMax);
      if (purityMin) body.purity_min = parseFloat(purityMin);
      if (qualityMin) body.quality_min = parseFloat(qualityMin);

      const res = await fetch(`${BASE}/api/sourcing/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? res.statusText);
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  const supplierColors: Record<string, string> = {};
  const palette = ["bg-blue-100 text-blue-800", "bg-purple-100 text-purple-800", "bg-teal-100 text-teal-800",
    "bg-orange-100 text-orange-800", "bg-pink-100 text-pink-800", "bg-indigo-100 text-indigo-800"];
  (result?.suppliers ?? []).forEach((s, i) => { supplierColors[s] = palette[i % palette.length]; });

  return (
    <AppLayout>
      <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">

        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Supplier Batching</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Assign BOM components to the fewest suppliers using greedy set-cover.
          </p>
        </div>

        {/* SKU picker */}
        <div className="bg-card border rounded-lg p-5 space-y-4">
          <h2 className="text-sm font-semibold">Finished-Good SKU</h2>
          <div className="relative">
            <Input
              placeholder="Search SKU or company…"
              value={search}
              onChange={e => { setSearch(e.target.value); setShowDropdown(true); setSelectedSku(""); }}
              onFocus={() => setShowDropdown(true)}
              onBlur={() => setTimeout(() => setShowDropdown(false), 150)}
            />
            {showDropdown && filtered.length > 0 && (
              <div className="absolute z-10 mt-1 w-full bg-popover border rounded-md shadow-md max-h-56 overflow-y-auto">
                {filtered.map(b => (
                  <button
                    key={b.sku}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-accent"
                    onMouseDown={() => selectSku(b.sku)}
                  >
                    <span className="font-mono text-xs">{b.sku}</span>
                    <span className="ml-2 text-muted-foreground">{b.company}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Filters */}
        <div className="bg-card border rounded-lg p-5 space-y-4">
          <h2 className="text-sm font-semibold">Filters <span className="text-muted-foreground font-normal">(optional — blank = no constraint)</span></h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <label className="space-y-1">
              <span className="text-xs text-muted-foreground">Price min ($/kg)</span>
              <Input placeholder="e.g. 5" value={priceMin} onChange={e => setPriceMin(e.target.value)} />
            </label>
            <label className="space-y-1">
              <span className="text-xs text-muted-foreground">Price max ($/kg)</span>
              <Input placeholder="e.g. 200" value={priceMax} onChange={e => setPriceMax(e.target.value)} />
            </label>
            <label className="space-y-1">
              <span className="text-xs text-muted-foreground">Purity min (0–1)</span>
              <Input placeholder="e.g. 0.95" value={purityMin} onChange={e => setPurityMin(e.target.value)} />
            </label>
            <label className="space-y-1">
              <span className="text-xs text-muted-foreground">Quality score min (0–1)</span>
              <Input placeholder="e.g. 0.7" value={qualityMin} onChange={e => setQualityMin(e.target.value)} />
            </label>
          </div>
          <Button onClick={runBatch} disabled={!selectedSku || loading} className="w-full sm:w-auto">
            {loading ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Running…</> : "Run Batch"}
          </Button>
        </div>

        {/* Error */}
        {error && (
          <div className="bg-destructive/10 text-destructive border border-destructive/30 rounded-md px-4 py-3 text-sm">
            {error}
          </div>
        )}

        {/* Results */}
        {result && (
          <div className="space-y-4">
            {/* Summary bar */}
            <div className="bg-card border rounded-lg p-4 flex flex-wrap gap-4 items-center">
              <div className="text-sm">
                <span className="text-muted-foreground">Components: </span>
                <span className="font-semibold">{result.assignments.length}</span>
              </div>
              <div className="text-sm">
                <span className="text-muted-foreground">Suppliers: </span>
                <span className="font-semibold">{result.suppliers.length}</span>
              </div>
              {result.uncovered.length > 0 && (
                <div className="text-sm text-destructive">
                  {result.uncovered.length} uncovered
                </div>
              )}
              <div className="flex flex-wrap gap-1 ml-auto">
                {result.suppliers.map(s => (
                  <Badge key={s} className={`text-xs ${supplierColors[s]}`}>{s}</Badge>
                ))}
              </div>
            </div>

            {/* Assignment table */}
            <div className="bg-card border rounded-lg overflow-hidden">
              <table className="w-full text-sm">
                <thead className="border-b bg-muted/40">
                  <tr>
                    <th className="text-left px-4 py-2 text-xs font-medium text-muted-foreground">Component SKU</th>
                    <th className="text-left px-4 py-2 text-xs font-medium text-muted-foreground">Supplier</th>
                    <th className="text-left px-4 py-2 text-xs font-medium text-muted-foreground">Quality</th>
                    <th className="text-left px-4 py-2 text-xs font-medium text-muted-foreground">Purity</th>
                    <th className="text-left px-4 py-2 text-xs font-medium text-muted-foreground">Price</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {result.assignments.map(a => (
                    <tr key={a.sku} className="hover:bg-muted/20">
                      <td className="px-4 py-2 font-mono text-xs text-foreground">{a.sku}</td>
                      <td className="px-4 py-2">
                        <Badge className={`text-xs ${supplierColors[a.supplier] ?? ""}`}>{a.supplier}</Badge>
                      </td>
                      <td className="px-4 py-2">{fmtScore(a.quality_score)}</td>
                      <td className="px-4 py-2">{fmtPurity(a.purity)}</td>
                      <td className="px-4 py-2"><PriceCell prices={a.prices} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Uncovered */}
            {result.uncovered.length > 0 && (
              <div className="bg-destructive/5 border border-destructive/20 rounded-lg p-4">
                <p className="text-sm font-medium text-destructive mb-2">Uncovered components</p>
                <div className="space-y-1">
                  {result.uncovered.map(sku => (
                    <p key={sku} className="font-mono text-xs text-muted-foreground">{sku}</p>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Empty state */}
        {!result && !loading && !error && (
          <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
            <PackageSearch className="w-10 h-10 mb-3 opacity-40" />
            <p className="text-sm">Select a SKU and run batch to see supplier assignments.</p>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
