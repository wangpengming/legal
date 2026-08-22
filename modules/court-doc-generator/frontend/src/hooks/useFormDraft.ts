/** F2 表单草稿自动保存：1s 防抖写入 localStorage，卸载时落盘。 */
import { useEffect, useRef } from "react";

export function draftKey(workspaceId: string, formName: string): string {
  return `courtdoc:draft:${workspaceId}:${formName}`;
}

export function saveDraft(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // QuotaExceeded / 隐私模式：静默忽略
  }
}

export function loadDraft<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

export function clearDraft(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch {
    // 忽略
  }
}

/** 表单值变化后 1s 无输入即保存；组件卸载时立即保存最后一次输入。 */
export function useFormDraft(key: string, value: unknown, enabled = true): void {
  const valueRef = useRef(value);
  valueRef.current = value;

  useEffect(() => {
    if (!enabled || !key) return;
    const timer = window.setTimeout(() => saveDraft(key, valueRef.current), 1000);
    return () => {
      window.clearTimeout(timer);
      saveDraft(key, valueRef.current);
    };
  }, [key, enabled]);
}