/** Fallback when API summary is unavailable (must match backend defaults). */
export const DEFAULT_CLIENT_BUDGET_MIN_EUR = 260_000;
export const DEFAULT_CLIENT_BUDGET_MAX_EUR = 340_000;

export function clientBudgetBoundsFromSummary(summary: unknown): { min: number; max: number } {
  const s = summary as Record<string, unknown> | null | undefined;
  const min = Number(s?.client_budget_min_eur);
  const max = Number(s?.client_budget_max_eur);
  if (Number.isFinite(min) && Number.isFinite(max) && min > 0 && max >= min) {
    return { min, max };
  }
  return { min: DEFAULT_CLIENT_BUDGET_MIN_EUR, max: DEFAULT_CLIENT_BUDGET_MAX_EUR };
}

/** Keep only cards whose numeric total is inside the client EUR budget (strict: null / NaN excluded). */
export function filterListingCardsByClientBudget<T extends { price?: unknown }>(
  items: T[],
  minEur: number,
  maxEur: number,
): T[] {
  return items.filter((i) => priceWithinClientBudget(i.price, minEur, maxEur));
}

export function priceWithinClientBudget(price: unknown, minEur: number, maxEur: number): boolean {
  if (price == null) return false;
  const n = typeof price === "number" ? price : Number(price);
  if (!Number.isFinite(n)) return false;
  return n >= minEur && n <= maxEur;
}
