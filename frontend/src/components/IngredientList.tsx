import { useRef, type KeyboardEvent } from "react";
import { RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { IngredientAnalysis } from "@/data/types";

function topDecision(ingredient: IngredientAnalysis): "accept" | "needs_review" | "reject" | null {
  if (ingredient.status !== "done") return null;
  return ingredient.top_variants[0]?.judge_decision ?? "reject";
}

function StatusDot({ ingredient }: { ingredient: IngredientAnalysis }) {
  const { status } = ingredient;
  if (status === "analyzing") {
    return <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse shrink-0" aria-label="Analyzing" />;
  }
  if (status === "error") {
    return <span className="w-2 h-2 rounded-full bg-red-400 shrink-0" aria-label="Error" />;
  }
  if (status === "pending") {
    return <span className="w-2 h-2 rounded-full bg-muted-foreground/40 shrink-0" aria-label="Pending" />;
  }

  const decision = topDecision(ingredient);
  if (decision === "accept") {
    return <span className="w-2 h-2 rounded-full bg-green-500 shrink-0" aria-label="Accept" />;
  }
  if (decision === "needs_review") {
    return <span className="w-2 h-2 rounded-full bg-amber-400 shrink-0" aria-label="Needs review" />;
  }
  return <span className="w-2 h-2 rounded-full bg-red-400 shrink-0" aria-label="Reject" />;
}

function statusHint(ingredient: IngredientAnalysis): string {
  if (ingredient.status === "analyzing") return "Analyzing...";
  if (ingredient.status === "error") return "Error";
  if (ingredient.status === "pending") return "Pending";
  const n = ingredient.top_variants.length;
  if (n === 0) return "No alternatives found";
  return `${n} alternative${n !== 1 ? "s" : ""} found`;
}

interface IngredientListProps {
  finishedGoodName: string;
  finishedGoodSku: string;
  companyName: string;
  ingredients: IngredientAnalysis[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  onRerun: () => void;
}

export function IngredientList({
  finishedGoodName,
  finishedGoodSku,
  companyName,
  ingredients,
  selectedId,
  onSelect,
  onRerun,
}: IngredientListProps) {
  const buttonRefs = useRef<Array<HTMLButtonElement | null>>([]);

  function focusAndSelect(index: number) {
    const normalized = Math.max(0, Math.min(ingredients.length - 1, index));
    const ingredient = ingredients[normalized];
    if (!ingredient) return;
    onSelect(ingredient.raw_material_id);
    buttonRefs.current[normalized]?.focus();
  }

  function handleArrowNavigation(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      focusAndSelect(index + 1);
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      focusAndSelect(index - 1);
      return;
    }
    if (event.key === "Home") {
      event.preventDefault();
      focusAndSelect(0);
      return;
    }
    if (event.key === "End") {
      event.preventDefault();
      focusAndSelect(ingredients.length - 1);
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border">
        <p className="text-xs text-muted-foreground font-mono">{finishedGoodSku}</p>
        <h2 className="text-sm font-semibold text-foreground leading-snug">{finishedGoodName}</h2>
        {companyName && (
          <p className="text-xs text-muted-foreground">{companyName}</p>
        )}
      </div>

      {/* Ingredient list */}
      <ul
        className="flex-1 overflow-y-auto py-2"
        role="listbox"
        aria-label="Raw materials"
      >
        {ingredients.map((ing, index) => {
          const isSelected = ing.raw_material_id === selectedId;
          const completionAnimation = ing.status === "done" ? "ingredient-complete" : "";
          return (
            <li key={ing.raw_material_id} role="option" aria-selected={isSelected}>
              <button
                ref={(node) => {
                  buttonRefs.current[index] = node;
                }}
                type="button"
                onClick={() => onSelect(ing.raw_material_id)}
                onKeyDown={(event) => handleArrowNavigation(event, index)}
                tabIndex={isSelected || (selectedId == null && index === 0) ? 0 : -1}
                aria-label={`${ing.raw_material_name}, ${statusHint(ing)}`}
                className={`w-full flex items-center gap-2.5 px-4 py-2.5 text-left transition-colors ${completionAnimation} ${
                  isSelected
                    ? "bg-primary/10 text-primary"
                    : "text-foreground hover:bg-muted"
                }`}
              >
                <StatusDot ingredient={ing} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{ing.raw_material_name}</p>
                  <p className="text-[11px] text-muted-foreground">{statusHint(ing)}</p>
                </div>
              </button>
            </li>
          );
        })}
      </ul>

      {/* Re-run button */}
      <div className="px-4 py-3 border-t border-border">
        <Button
          variant="outline"
          size="sm"
          className="w-full gap-2 text-xs"
          onClick={onRerun}
        >
          <RotateCw className="w-3 h-3" />
          Re-run analysis
        </Button>
      </div>
    </div>
  );
}
