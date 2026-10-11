import type { TimelineEntry } from '../types';
import { useEffect, useState } from 'react';
import { api } from '../lib/api';

export const Timeline = () => {
  const [data, setData] = useState<TimelineEntry[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<{ de: string; ate: string }>({
    de: '2019-01-01',
    ate: '2022-12-31',
  });

  useEffect(() => {
    const fetchTimeline = async () => {
      setLoading(true);
      try {
        const result = await api.timeline(filters.de, filters.ate);
        setData(result);
      } catch (err) {
        setError('Failed to load timeline');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchTimeline();
  }, [filters.de, filters.ate]);

  if (loading && data.length === 0) {
    return (
      <div className="col-span-12 text-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
        <p className="mt-2 text-stone-500 dark:text-slate-400">Carregando timeline...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="col-span-12 text-center py-6">
        <p className="text-red-500">{error}</p>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="col-span-12 text-center py-12">
        <p className="text-stone-500 dark:text-slate-400">Nenhum dado disponível para o período selecionado</p>
      </div>
    );
  }

  return (
    <div className="col-span-12">
      <h3 className="font-display text-lg mb-4">Evolução mensal</h3>
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-stone-200 dark:border-slate-800 p-4">
        <div className="flex mb-4">
          <label className="mr-2">De: </label>
          <input
            type="date"
            value={filters.de}
            onChange={(e) => setFilters(prev => ({ ...prev, de: e.target.value }))}
            min="2019-01-01"
            max="2022-12-31"
            className="border border-stone-200 dark:border-slate-700 rounded-md px-2 py-1 bg-white dark:bg-slate-800 text-sm"
          />
          <span className="mx-4">até</span>
          <label className="mr-2"> </label>
          <input
            type="date"
            value={filters.ate}
            onChange={(e) => setFilters(prev => ({ ...prev, ate: e.target.value }))}
            min="2019-01-01"
            max="2022-12-31"
            className="border border-stone-200 dark:border-slate-700 rounded-md px-2 py-1 bg-white dark:bg-slate-800 text-sm"
          />
        </div>
        {/* In a real app, we'd render a chart here using Chart.js or similar */}
        <div className="h-40 bg-gradient-to-b from-gray-50 to-white dark:from-slate-900 dark:to-slate-800 rounded-lg">
          <div className="flex h-full items-center justify-center text-stone-500 dark:text-slate-400">
            Timeline chart would be rendered here
            <br />
            <span className="text-xs">({data.length} months of data)</span>
          </div>
        </div>
      </div>
    </div>
  );
};
