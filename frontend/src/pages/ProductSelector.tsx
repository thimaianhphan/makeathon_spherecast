import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Search, ArrowRight, Package, ShieldCheck } from "lucide-react";
import { AppLayout } from "@/components/AppLayout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ComplianceDialog } from "@/components/ComplianceDialog";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { getBom, getFinishedGoods } from "@/api/client";
import type { CatalogueProduct, BomData } from "@/data/types";

const LAST_ANALYSIS_KEY = "agnes:last_analysis_id";

export default function ProductSelector() {
  const [products, setProducts] = useState<CatalogueProduct[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<CatalogueProduct | null>(null);
  const [bom, setBom] = useState<BomData | null>(null);
  const [loading, setLoading] = useState(true);
  const [complianceOpen, setComplianceOpen] = useState(false);
  const navigate = useNavigate();

  const lastId = localStorage.getItem(LAST_ANALYSIS_KEY);

  useEffect(() => {
    getFinishedGoods()
      .then(setProducts)
      .catch(() => setProducts([]))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedProduct) { setBom(null); return; }
    getBom(Number.parseInt(selectedProduct.product_id, 10))
      .then(setBom)
      .catch(() => setBom(null));
  }, [selectedProduct]);

  function handleSelect(product: CatalogueProduct) {
    setSelectedProduct(product);
  }

  function handleAnalyze() {
    if (!selectedProduct) return;
    localStorage.setItem(LAST_ANALYSIS_KEY, selectedProduct.product_id);
    navigate(`/analyze/${selectedProduct.product_id}`);
  }

  const ingredientCount = bom?.components.length ?? 0;

  function skuFor(product: CatalogueProduct): string {
    const enriched = product as CatalogueProduct & { sku?: string; finished_good_sku?: string };
    return enriched.sku ?? enriched.finished_good_sku ?? product.name;
  }

  function productNameFor(product: CatalogueProduct): string {
    const enriched = product as CatalogueProduct & { product_name?: string; finished_good_name?: string };
    return enriched.product_name ?? enriched.finished_good_name ?? product.name;
  }

  function companyFor(product: CatalogueProduct): string {
    const enriched = product as CatalogueProduct & { company_name?: string };
    return enriched.company_name ?? product.description ?? "Unknown company";
  }

  return (
    <AppLayout>
      <div className="max-w-2xl mx-auto px-6 py-12">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-foreground mb-2">Agnes ingredient variant explorer</h1>
          <p className="text-sm text-muted-foreground">
            Find cheaper, compliant ingredient alternatives for any product in your portfolio.
          </p>
        </div>

        {/* Searchable product combobox */}
        <div className="rounded-lg border border-border shadow-sm mb-4">
          <Command>
            <div className="flex items-center gap-2 px-3 border-b border-border">
              <Search className="w-4 h-4 text-muted-foreground shrink-0" />
              <CommandInput
                placeholder="Search by SKU, product name, or company..."
                className="border-0 shadow-none focus-visible:ring-0 text-sm"
              />
            </div>
            <CommandList className="max-h-64">
              {loading && (
                <CommandEmpty>Loading products…</CommandEmpty>
              )}
              {!loading && products.length === 0 && (
                <CommandEmpty>No products found.</CommandEmpty>
              )}
              {!loading && products.length > 0 && (
                <CommandGroup heading="Finished goods">
                  {products.map((p) => (
                    <CommandItem
                      key={p.product_id}
                      value={`${skuFor(p)} ${productNameFor(p)} ${companyFor(p)}`}
                      onSelect={() => handleSelect(p)}
                      className="flex items-center justify-between gap-4 cursor-pointer"
                    >
                      <div className="flex flex-col min-w-0">
                        <span className="text-sm truncate">
                          <span className="font-mono">{skuFor(p)}</span>
                          <span className="text-muted-foreground"> - </span>
                          <span className="font-medium">{productNameFor(p)}</span>
                        </span>
                        <span className="text-xs text-muted-foreground">{companyFor(p)}</span>
                      </div>
                      {selectedProduct?.product_id === p.product_id && (
                        <span className="text-primary text-xs font-medium shrink-0">Selected</span>
                      )}
                    </CommandItem>
                  ))}
                </CommandGroup>
              )}
            </CommandList>
          </Command>
        </div>

        {!selectedProduct && !loading && (
          <div className="rounded-lg border border-dashed border-border bg-muted/30 p-4 mb-6">
            <p className="text-xs text-muted-foreground">
              Select a finished good to preview its BOM and analysis scope before running recommendations.
            </p>
          </div>
        )}

        {/* Preview card */}
        {selectedProduct && (
          <div className="rounded-lg border border-border bg-card p-4 mb-6 animate-in fade-in duration-200">
            <div className="flex items-start justify-between gap-3 mb-3">
              <div className="flex items-center gap-2">
                <Package className="w-4 h-4 text-muted-foreground" />
                <div>
                  <p className="text-xs text-muted-foreground font-mono">{skuFor(selectedProduct)}</p>
                  <p className="text-sm font-semibold text-foreground">{productNameFor(selectedProduct)}</p>
                  <p className="text-xs text-muted-foreground">{companyFor(selectedProduct)}</p>
                </div>
              </div>
              {bom && (
                <Badge variant="secondary" className="shrink-0 text-xs">
                  {ingredientCount} raw material{ingredientCount !== 1 ? "s" : ""}
                </Badge>
              )}
            </div>

            {/* Ingredient pills */}
            {bom && bom.components.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {bom.components.map((c) => (
                  <span
                    key={c.product_id}
                    className="px-2 py-0.5 rounded-full bg-muted text-[11px] text-muted-foreground"
                  >
                    {c.Name}
                  </span>
                ))}
              </div>
            )}

            {bom && (
              <div className="mt-3 grid grid-cols-2 gap-2">
                <div className="rounded-md border border-border bg-muted/40 px-2 py-1.5">
                  <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Scope</p>
                  <p className="text-xs font-medium text-foreground">{ingredientCount} ingredient{ingredientCount === 1 ? "" : "s"}</p>
                </div>
                <div className="rounded-md border border-border bg-muted/40 px-2 py-1.5">
                  <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Variant slots</p>
                  <p className="text-xs font-medium text-foreground">Up to {ingredientCount * 3}</p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* CTA */}
        <div className="flex flex-col sm:flex-row gap-2">
          <Button
            className="flex-1 gap-2"
            disabled={!selectedProduct}
            onClick={handleAnalyze}
          >
            Analyze variants
            <ArrowRight className="w-4 h-4" />
          </Button>
          <Button
            variant="outline"
            className="sm:w-auto gap-2"
            disabled={!selectedProduct}
            onClick={() => setComplianceOpen(true)}
          >
            <ShieldCheck className="w-4 h-4" />
            Compliance check
          </Button>
        </div>

        {/* Continue last analysis */}
        {lastId && lastId !== selectedProduct?.product_id && (
          <p className="mt-4 text-center text-xs text-muted-foreground">
            <Link
              to={`/analyze/${lastId}`}
              className="text-primary hover:underline"
            >
              Continue last analysis
            </Link>
          </p>
        )}
      </div>

      {selectedProduct && (
        <ComplianceDialog
          open={complianceOpen}
          onOpenChange={setComplianceOpen}
          productId={Number.parseInt(selectedProduct.product_id, 10)}
          productSku={skuFor(selectedProduct)}
          productName={productNameFor(selectedProduct)}
          companyName={companyFor(selectedProduct)}
        />
      )}
    </AppLayout>
  );
}
