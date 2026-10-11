import type { Entity } from '../types';
import { useEffect, useState } from 'react';
import { api } from '../lib/api';

interface EntitiesProps {
  onEntitySelect: (nome: string) => void;
}

export const Entities = ({ onEntitySelect }: EntitiesProps) => {
  const [per, setPer] = useState<Entity[]>([]);
  const [org, setOrg] = useState<Entity[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchEntities = async () => {
      setLoading(true);
      try {
        const data = await api.entidades(50);
        setPer(data.per);
        setOrg(data.org);
      } catch (err) {
        setError('Failed to load entities');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchEntities();
  }, []);

  if (loading && per.length === 0 && org.length === 0) {
    return (
      <div className="col-span-12 text-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
        <p className="mt-2 text-stone-500 dark:text-slate-400">Carregando entidades...</p>
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

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
      <div>
        <h3 className="font-display text-lg mb-3">Pessoas</h3>
        <div id="lista-per" className="space-y-1 text-sm">
          {per.map((p, idx) => (
            <div
              key={idx}
              className="flex justify-between items-center py-1.5 border-b border-stone-100 dark:border-slate-800 cursor-pointer hover:bg-stone-50 dark:hover:bg-slate-800/50 rounded px-1 -mx-1"
              onClick={() => onEntitySelect(p.nome)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  onEntitySelect(p.nome);
                }
              }}
            >
              <span className="truncate text-sm">
                <span className="text-xs text-stone-400 w-6 inline-block tabular-nums">
                  {idx + 1}
                </span>
                {p.nome}
              </span>
              <span className="text-xs font-medium tabular-nums" style={{ color: '#dc2626' }}>
                {p.total}
              </span>
            </div>
          ))}
        </div>
      </div>
      <div>
        <h3 className="font-display text-lg mb-3">Organizações</h3>
        <div id="lista-org" className="space-y-1 text-sm">
          {org.map((o, idx) => (
            <div
              key={idx}
              className="flex justify-between items-center py-1.5 border-b border-stone-100 dark:border-slate-800 cursor-pointer hover:bg-stone-50 dark:hover:bg-slate-800/50 rounded px-1 -mx-1"
              onClick={() => onEntitySelect(o.nome)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  onEntitySelect(o.nome);
                }
              }}
            >
              <span className="truncate text-sm">
                <span className="text-xs text-stone-400 w-6 inline-block tabular-nums">
                  {idx + 1}
                </span>
                {o.nome}
              </span>
              <span className="text-xs font-medium tabular-nums" style={{ color: '#2563eb' }}>
                {o.total}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
