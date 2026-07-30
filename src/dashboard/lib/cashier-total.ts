export type CashierTotalMode = "thuoc" | "dich_vu";

export interface PricedServiceLine {
  price: number | null;
}

export interface PricedDrugLine extends PricedServiceLine {
  quantity: string | null;
}

export interface CashierTotal {
  sum: number;
  missing: boolean;
}

function validUnitPrice(price: number | null): price is number {
  return price !== null && Number.isFinite(price) && price > 0;
}

export function parsePositiveQuantity(raw: string | null): number | null {
  if (raw === null) return null;

  const normalized = raw.trim().replace(",", ".");
  if (!/^\d+(?:\.\d+)?$/.test(normalized)) return null;

  const quantity = Number(normalized);
  return Number.isFinite(quantity) && quantity > 0 ? quantity : null;
}

export function calculateCashierTotal(
  mode: CashierTotalMode,
  services: readonly PricedServiceLine[],
  drugs: readonly PricedDrugLine[],
): CashierTotal {
  const lines = mode === "thuoc" ? drugs : services;

  return lines.reduce<CashierTotal>(
    (total, line) => {
      if (!validUnitPrice(line.price)) {
        return { ...total, missing: true };
      }

      if (mode === "thuoc") {
        const quantity = parsePositiveQuantity((line as PricedDrugLine).quantity);
        if (quantity === null) {
          return { ...total, missing: true };
        }
        return {
          ...total,
          sum: total.sum + Math.round(line.price * quantity),
        };
      }

      return { ...total, sum: total.sum + line.price };
    },
    { sum: 0, missing: false },
  );
}
