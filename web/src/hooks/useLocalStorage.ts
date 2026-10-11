import { useState, useCallback, useEffect } from 'react';

export function useLocalStorage<T>(key: string, initial: T): [T, (val: T | ((prev: T) => T)) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const stored = localStorage.getItem(key);
      return stored ? JSON.parse(stored) : initial;
    } catch {
      return initial;
    }
  });

  // Sync to localStorage on value change
  useEffect(() => {
    localStorage.setItem(key, JSON.stringify(value));
  }, [key, value]);

  const update = useCallback((next: T | ((prev: T) => T)) => {
    setValue(prev => typeof next === 'function' ? (next as (prev: T) => T)(prev) : next);
  }, [key]);

  return [value, update];
}