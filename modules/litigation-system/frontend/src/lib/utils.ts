import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** 合并 className（shadcn 惯例）：tailwind-merge 去冲突 + clsx 条件类。 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}