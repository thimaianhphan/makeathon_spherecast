import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Info, Loader2, ShieldCheck } from "lucide-react";
import { AppLayout } from "@/components/AppLayout";
import { IngredientList } from "@/components/IngredientList";
import { VariantCard, KeepCurrentCard } from "@/components/VariantCard";
import { EvidencePanel } from "@/components/EvidencePanel";
import { ComplianceDialog } from "@/components/ComplianceDialog";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  SCORE_WEIGHTS,
  getAnalysis,
  getFinishedGoods,
  startAnalysis,
  streamAnalysis,
} from "@/api/client";
import type {
  FinishedGoodAnalysis,
  IngredientAnalysis,
  LiveMessage,
  SourcingEvidenceItem,
  VariantCard as VariantCardType,
} from "@/data/types";

const CACHE_PREFIX = "agnes:analysis:";
const HISTORY_KEY = "agnes:history";
const LAST_ANALYSIS_KEY = "agnes:last_analysis_id";
const SELECTION_PREFIX = "agnes:selection:";

function cacheKey(id: number): string {
  return `${CACHE_PREFIX}${id}`;
}

function selectionKey(id: number): string {
  return `${SELECTION_PREFIX}${id}`;
}

function mergeCompanyName(analysis: FinishedGoodAnalysis, companyName: string): FinishedGoodAnalysis {
  if (analysis.company_name || !companyName) return analysis;
  return { ...analysis, company_name: companyName };
}

interface DecisionSummary {
  accept: number;
  needsReview: number;
  reject: number;
}

function summarizeDecisions(analysis: FinishedGoodAnalysis | null): DecisionSummary {
  if (!analysis) {
    return { accept: 0, needsReview: 0, reject: 0 };
  }

  return analysis.ingredients.reduce(
    (acc, ingredient) => {
      const decision = ingredient.top_variants[0]?.judge_decision;
      if (decision === "accept") {
        acc.accept += 1;
      } else if (decision === "needs_review") {
        acc.needsReview += 1;
      } else {
        acc.reject += 1;
      }
      return acc;
    },
    { accept: 0, needsReview: 0, reject: 0 } as DecisionSummary,
  );
}

interface HistoryEntry {
  id: number;
  sku: string;
  name: string;
  company_name: string;
  analyzed_at: string;
  accepted_count: number;
}

function saveToHistory(analysis: FinishedGoodAnalysis) {
  const raw = localStorage.getItem(HISTORY_KEY);
  const history: HistoryEntry[] = raw ? JSON.parse(raw) : [];
  const entry: HistoryEntry = {
    id: analysis.finished_good_id,
    sku: analysis.finished_good_sku,
    name: analysis.finished_good_name,
    company_name: analysis.company_name,
    analyzed_at: analysis.analyzed_at,
    accepted_count: analysis.ingredients.filter((ingredient) =>
      ingredient.top_variants.some((variant) => variant.judge_decision === "accept"),
    ).length,
  };
  const deduped = [entry, ...history.filter((item) => item.id !== entry.id)].slice(0, 20);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(deduped));
}

function HowScoresWorkPopover() {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          aria-label="How scores work"
        >
          <Info className="w-3.5 h-3.5" />
          How scores work
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-80 text-xs space-y-2">
        <p className="font-semibold">Scoring formula</p>
        <p className="text-muted-foreground">
          Composite score = {SCORE_WEIGHTS.compliance} x Compliance + {SCORE_WEIGHTS.quality} x Quality + {SCORE_WEIGHTS.price} x Price
        </p>
        <p className="text-muted-foreground">
          Compliance (0-100): 4 EU checks, pass=100, uncertain=50, fail=0. LLM-only inference is capped at 60.
        </p>
        <p className="text-muted-foreground">
          Quality (0-100): functional equivalence x 100. Functional-category match is the floor.
        </p>
        <p className="text-muted-foreground">
          Price (0-100): 100 means at least 20% cheaper, 50 means parity, 0 means at least 20% more expensive.
          If price is unknown, score stays neutral at 50.
        </p>
      </PopoverContent>
    </Popover>
  );
}

function LoadingView({
  sku,
  progressLines,
}: {
  sku?: string;
  progressLines: string[];
}) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 px-6">
      <Loader2 className="w-8 h-8 text-primary animate-spin" />
      <div className="text-center max-w-lg">
        <p className="text-sm font-medium text-foreground mb-1">Running ingredient variant analysis</p>
        <p className="text-xs text-muted-foreground mb-2">
          {sku ? `Analyzing ${sku}` : "Analyzing selected finished good"}. This can take 30-60 seconds.
        </p>
      </div>
      {progressLines.length > 0 && (
        <div className="w-full max-w-xl rounded-md border border-border bg-card p-3">
          <p className="text-[11px] font-medium text-muted-foreground mb-2">Live updates</p>
          <ul className="space-y-1">
            {progressLines.map((line, index) => (
              <li key={`${line}-${index}`} className="text-xs text-foreground">
                {line}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function ErrorView({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 text-center px-6">
      <p className="text-sm text-red-600 font-medium">Analysis failed</p>
      <p className="text-xs text-muted-foreground max-w-sm">{message}</p>
      <Button variant="outline" size="sm" onClick={onRetry}>Retry analysis</Button>
    </div>
  );
}

interface CenterPanelProps {
  ingredient: IngredientAnalysis | null;
  selectedVariantIdx: number | null;
  hoveredVariantIdx: number | null;
  activeEvidenceKey: string | null;
  onVariantSelect: (idx: number | null) => void;
  onVariantHover: (idx: number | null) => void;
  onEvidenceClick: (item: SourcingEvidenceItem, key: string) => void;
}

function CenterPanel({
  ingredient,
  selectedVariantIdx,
  hoveredVariantIdx,
  activeEvidenceKey,
  onVariantSelect,
  onVariantHover,
  onEvidenceClick,
}: CenterPanelProps) {
  if (!ingredient) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
        Select a raw material to review its top variants.
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-muted-foreground">Selected raw material</p>
          <h2 className="text-base font-semibold text-foreground">{ingredient.raw_material_name}</h2>
        </div>
        <span className="text-xs text-muted-foreground">
          {ingredient.top_variants.length} variant{ingredient.top_variants.length === 1 ? "" : "s"}
        </span>
      </div>

      {ingredient.top_variants.length === 0 && (
        <p className="text-sm text-muted-foreground py-4 text-center">
          No viable alternatives found for this ingredient.
        </p>
      )}

      {ingredient.top_variants.map((variant, idx) => (
        <div
          key={`${variant.substitute_product_id}-${variant.rank}`}
          className={ingredient.status === "done" ? "motion-safe:animate-in motion-safe:fade-in motion-safe:duration-200" : ""}
        >
          <VariantCard
            variant={variant}
            isSelected={selectedVariantIdx === idx}
            isHovered={hoveredVariantIdx === idx}
            activeEvidenceKey={activeEvidenceKey}
            onMouseEnter={() => onVariantHover(idx)}
            onMouseLeave={() => onVariantHover(null)}
            onSelect={() => onVariantSelect(selectedVariantIdx === idx ? null : idx)}
            onEvidenceClick={onEvidenceClick}
          />
        </div>
      ))}

      <KeepCurrentCard
        ingredientName={ingredient.raw_material_name}
        currentSupplierName={ingredient.current_supplier_name}
        reason={ingredient.keep_current_reason}
      />
    </div>
  );
}

export default function AnalysisView() {
  const { finishedGoodId } = useParams<{ finishedGoodId: string }>();
  const navigate = useNavigate();
  const id = Number.parseInt(finishedGoodId ?? "0", 10);

  const [analysis, setAnalysis] = useState<FinishedGoodAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [companyName, setCompanyName] = useState("");
  const [selectedIngredientId, setSelectedIngredientId] = useState<number | null>(null);
  const [selectedByIngredient, setSelectedByIngredient] = useState<Record<string, number | null>>({});
  const [hoveredVariantIdx, setHoveredVariantIdx] = useState<number | null>(null);
  const [activeEvidenceKey, setActiveEvidenceKey] = useState<string | null>(null);
  const [progressLines, setProgressLines] = useState<string[]>([]);
  const [complianceOpen, setComplianceOpen] = useState(false);

  const companyNameRef = useRef("");

  useEffect(() => {
    companyNameRef.current = companyName;
  }, [companyName]);

  useEffect(() => {
    if (!id) return;
    getFinishedGoods()
      .then((products) => {
        const match = products.find((product) => product.product_id === String(id));
        const companyField = match && "company_name" in match
          ? (match as { company_name?: string }).company_name
          : undefined;
        setCompanyName(companyField ?? match?.description ?? "");
      })
      .catch(() => {
        setCompanyName("");
      });
  }, [id]);

  const selectedIngredient = useMemo(() => {
    if (!analysis) return null;
    return analysis.ingredients.find((item) => item.raw_material_id === selectedIngredientId) ?? null;
  }, [analysis, selectedIngredientId]);

  const selectedVariantIdx = selectedIngredient
    ? selectedByIngredient[String(selectedIngredient.raw_material_id)] ?? null
    : null;

  const activeVariant: VariantCardType | null = useMemo(() => {
    if (!selectedIngredient) return null;
    const index = hoveredVariantIdx ?? selectedVariantIdx;
    if (index == null || index < 0) return null;
    return selectedIngredient.top_variants[index] ?? null;
  }, [hoveredVariantIdx, selectedIngredient, selectedVariantIdx]);

  const decisionSummary = useMemo(() => summarizeDecisions(analysis), [analysis]);

  const runAnalysis = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    setProgressLines(["Starting analysis pipeline..."]);

    const eventSource = streamAnalysis(id);
    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as LiveMessage;
        if (payload.type === "heartbeat") return;
        const line = payload.summary || payload.detail;
        if (!line) return;
        setProgressLines((prev) => [...prev.slice(-6), line]);
      } catch {
        // Ignore malformed stream events from fallback stream.
      }
    };
    eventSource.onerror = () => {
      eventSource.close();
    };

    try {
      await startAnalysis(id);
      const fetched = await getAnalysis(id);
      const merged = mergeCompanyName(fetched, companyNameRef.current);

      setAnalysis(merged);
      setSelectedIngredientId(merged.ingredients[0]?.raw_material_id ?? null);
      setHoveredVariantIdx(null);
      setActiveEvidenceKey(null);

      localStorage.setItem(cacheKey(id), JSON.stringify(merged));
      localStorage.setItem(LAST_ANALYSIS_KEY, String(id));
      saveToHistory(merged);
    } catch (analysisError) {
      setError(analysisError instanceof Error ? analysisError.message : String(analysisError));
    } finally {
      eventSource.close();
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (!id) return;

    const cachedAnalysis = localStorage.getItem(cacheKey(id));
    const savedSelections = localStorage.getItem(selectionKey(id));
    if (savedSelections) {
      try {
        setSelectedByIngredient(JSON.parse(savedSelections) as Record<string, number | null>);
      } catch {
        setSelectedByIngredient({});
      }
    } else {
      setSelectedByIngredient({});
    }

    if (cachedAnalysis) {
      try {
        const parsed = JSON.parse(cachedAnalysis) as FinishedGoodAnalysis;
        setAnalysis(parsed);
        setSelectedIngredientId(parsed.ingredients[0]?.raw_material_id ?? null);
        setError(null);
        return;
      } catch {
        localStorage.removeItem(cacheKey(id));
      }
    }

    void runAnalysis();
  }, [id, runAnalysis]);

  useEffect(() => {
    if (!analysis) return;
    if (analysis.company_name || !companyName) return;
    const merged = { ...analysis, company_name: companyName };
    setAnalysis(merged);
    localStorage.setItem(cacheKey(id), JSON.stringify(merged));
  }, [analysis, companyName, id]);

  useEffect(() => {
    if (!id) return;
    localStorage.setItem(selectionKey(id), JSON.stringify(selectedByIngredient));
  }, [id, selectedByIngredient]);

  const handleVariantSelect = (idx: number | null) => {
    if (!selectedIngredient) return;
    const ingredientKey = String(selectedIngredient.raw_material_id);
    setSelectedByIngredient((prev) => ({ ...prev, [ingredientKey]: idx }));
  };

  const handleVariantHover = (idx: number | null) => {
    setHoveredVariantIdx(idx);
    if (idx === null) {
      setActiveEvidenceKey(null);
    }
  };

  const handleEvidenceClick = (_item: SourcingEvidenceItem, key: string) => {
    setActiveEvidenceKey(key);
  };

  const handleSelectIngredient = (ingredientId: number) => {
    setSelectedIngredientId(ingredientId);
    setHoveredVariantIdx(null);
    setActiveEvidenceKey(null);
  };

  const handleRerun = () => {
    localStorage.removeItem(cacheKey(id));
    localStorage.removeItem(selectionKey(id));
    setSelectedByIngredient({});
    setHoveredVariantIdx(null);
    setActiveEvidenceKey(null);
    void runAnalysis();
  };

  return (
    <AppLayout>
      <div className="flex flex-col h-screen">
        <div className="flex items-center justify-between gap-3 px-4 h-12 border-b border-border shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <Button
              variant="ghost"
              size="sm"
              className="gap-1.5 text-xs text-muted-foreground"
              onClick={() => navigate("/")}
            >
              <ArrowLeft className="w-3 h-3" />
              Back
            </Button>

            {analysis && (
              <>
                <span className="text-border">|</span>
                <span className="text-xs font-mono text-muted-foreground truncate">{analysis.finished_good_sku}</span>
                <span className="text-xs text-foreground font-medium truncate">{analysis.finished_good_name}</span>
                {analysis.company_name && (
                  <span className="text-xs text-muted-foreground truncate">- {analysis.company_name}</span>
                )}
              </>
            )}
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {analysis && (
              <>
                <span className="hidden lg:inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-[11px] font-medium text-green-700">
                  Accept {decisionSummary.accept}
                </span>
                <span className="hidden lg:inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-700">
                  Review {decisionSummary.needsReview}
                </span>
                <span className="hidden lg:inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-[11px] font-medium text-red-700">
                  Reject {decisionSummary.reject}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  className="hidden sm:inline-flex h-7 px-2.5 text-[11px] gap-1.5"
                  onClick={() => setComplianceOpen(true)}
                >
                  <ShieldCheck className="w-3 h-3" />
                  Compliance check
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="hidden sm:inline-flex h-7 px-2.5 text-[11px]"
                  onClick={handleRerun}
                >
                  Run fresh
                </Button>
              </>
            )}
            <HowScoresWorkPopover />
          </div>
        </div>

        <div className="px-4 py-2 border-b border-border bg-amber-50/60">
          <p className="text-[11px] text-amber-800">
            Compatibility mode: this backend currently returns completed analysis in a single response. Ingredient-level progress percentages are unavailable.
          </p>
        </div>

        {loading && (
          <div className="flex-1">
            <LoadingView sku={analysis?.finished_good_sku} progressLines={progressLines} />
          </div>
        )}

        {!loading && error && (
          <div className="flex-1">
            <ErrorView message={error} onRetry={handleRerun} />
          </div>
        )}

        {!loading && !error && analysis && (
          <>
            <div className="flex-1 hidden md:flex overflow-hidden">
              <div className="w-[260px] shrink-0 border-r border-border overflow-hidden flex flex-col">
                <IngredientList
                  finishedGoodName={analysis.finished_good_name}
                  finishedGoodSku={analysis.finished_good_sku}
                  companyName={analysis.company_name}
                  ingredients={analysis.ingredients}
                  selectedId={selectedIngredientId}
                  onSelect={handleSelectIngredient}
                  onRerun={handleRerun}
                />
              </div>

              <div className="flex-1 overflow-hidden">
                <CenterPanel
                  ingredient={selectedIngredient}
                  selectedVariantIdx={selectedVariantIdx}
                  hoveredVariantIdx={hoveredVariantIdx}
                  activeEvidenceKey={activeEvidenceKey}
                  onVariantSelect={handleVariantSelect}
                  onVariantHover={handleVariantHover}
                  onEvidenceClick={handleEvidenceClick}
                />
              </div>

              <div className="w-[320px] shrink-0 border-l border-border overflow-hidden flex flex-col">
                <div className="px-4 py-3 border-b border-border">
                  <p className="text-xs font-semibold text-foreground uppercase tracking-wider">Evidence panel</p>
                </div>
                <div className="flex-1 overflow-y-auto">
                  <EvidencePanel variant={activeVariant} activeEvidenceKey={activeEvidenceKey} />
                </div>
              </div>
            </div>

            <div className="flex-1 md:hidden overflow-hidden">
              <Tabs defaultValue="ingredients" className="flex flex-col h-full">
                <TabsList className="grid w-full grid-cols-3 shrink-0 rounded-none border-b border-border">
                  <TabsTrigger value="ingredients" className="text-xs">Ingredients</TabsTrigger>
                  <TabsTrigger value="variants" className="text-xs">Variants</TabsTrigger>
                  <TabsTrigger value="evidence" className="text-xs">Evidence</TabsTrigger>
                </TabsList>

                <TabsContent value="ingredients" className="flex-1 overflow-hidden m-0">
                  <IngredientList
                    finishedGoodName={analysis.finished_good_name}
                    finishedGoodSku={analysis.finished_good_sku}
                    companyName={analysis.company_name}
                    ingredients={analysis.ingredients}
                    selectedId={selectedIngredientId}
                    onSelect={handleSelectIngredient}
                    onRerun={handleRerun}
                  />
                </TabsContent>

                <TabsContent value="variants" className="flex-1 overflow-auto m-0">
                  <CenterPanel
                    ingredient={selectedIngredient}
                    selectedVariantIdx={selectedVariantIdx}
                    hoveredVariantIdx={hoveredVariantIdx}
                    activeEvidenceKey={activeEvidenceKey}
                    onVariantSelect={handleVariantSelect}
                    onVariantHover={handleVariantHover}
                    onEvidenceClick={handleEvidenceClick}
                  />
                </TabsContent>

                <TabsContent value="evidence" className="flex-1 overflow-auto m-0">
                  <EvidencePanel variant={activeVariant} activeEvidenceKey={activeEvidenceKey} />
                </TabsContent>
              </Tabs>
            </div>
          </>
        )}
      </div>

      {id > 0 && (
        <ComplianceDialog
          open={complianceOpen}
          onOpenChange={setComplianceOpen}
          productId={id}
          productSku={analysis?.finished_good_sku}
          productName={analysis?.finished_good_name}
          companyName={analysis?.company_name}
        />
      )}
    </AppLayout>
  );
}
