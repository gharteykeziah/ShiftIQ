import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge Tailwind classes safely — later classes win over earlier conflicting
 * ones (e.g. cn("p-2", condition && "p-4") resolves to just "p-4").
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
