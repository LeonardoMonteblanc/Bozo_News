import type { Article } from '../types';
import { useEffect, useState } from 'react';
import { api } from '../lib/api';

interface Filters {
  q: string;
  topico: number | undefined;
  entidade: string;
  categoria: string;
  dominio: string;
  sentimento: string;
  de: string;
  ate: string;
  ordenar: 'data_desc' | 'data_asc' | 'relevancia';
  limit: number;
  offset: number;
  ocultarLidas: boolean;
}

interface NewsListProps {
  filters: Filters;
  lidas: Set<number>;
  onToggleLida: (id: number) => void;
  onOpenModal: (id: number) => void;
}

export const NewsList = ({
  filters,
  lidas,
  onToggleLida,
  onOpenModal,
}: NewsListProps) => {
  const [noticias, setNoticias] = useState<Article[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchNoticias = async () => {
      setLoading(true);
      try {
        const data = await api.noticias(filters);
        setNoticias(data.itens);
        setTotal(data.total);
      } catch (err) {
        setError('Failed to load news');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchNoticias();
  }, [filters]);

  if (loading && noticias.length === 0) {
    return (
      <div className="col-span-12 text-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
        <p className="mt-2 text-stone-500 dark:text-slate-400">Carregando notícias...</p>
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

  if (noticias.length === 0 && total === 0) {
    return (
      <div className="col-span-12 text-center py-12">
        <div className="text-3xl mb-2">∅</div>
        <p className="text-sm text-stone-500 dark:text-slate-400">
          Nenhum resultado com esses filtros.
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="grid grid-cols-12 gap-2 text-xs uppercase tracking-wider text-stone-500 dark:text-slate-500 border-b border-stone-200 dark:border-slate-800 pb-2 mb-2 px-2">
        <div className="col-span-2">Data</div>
        <div className="col-span-7">Título</div>
        <div className="col-span-2">Veículo</div>
        <div className="col-span-1 text-right">Estado</div>
      </div>

      <div className="divide-y divide-stone-100 dark:divide-slate-800">
        {noticias.map(article => {
          const isLida = lidas.has(article.id);
          const per = (article.entidades_per ?? []).slice(0, 2);

          return (
            <article
              key={article.id}
              className={`grid grid-cols-12 gap-3 items-start py-3 hover:bg-stone-50 dark:hover:bg-slate-800/50 transition cursor-pointer -mx-2 px-2 rounded ${isLida ? 'noticia-lida' : ''}`}
              onClick={() => onOpenModal(article.id)}
            >
              <div className="col-span-2 text-xs text-stone-500 dark:text-slate-500 font-medium tabular-nums pt-0.5">
                {article.data || ''}
              </div>
              <div className="col-span-7 min-w-0">
                {article.topico_nome_v5 && (
                  <div className="mb-1">
                    <span className="text-xs font-medium text-red-600">
                      {article.topico_nome_v5}
                    </span>
                  </div>
                )}
                <h3 className="text-sm font-semibold leading-snug mb-1">
                  {article.titulo}
                </h3>
                {per.length > 0 && (
                  <div className="text-xs text-stone-500 dark:text-slate-500">
                    {per.join(' · ')}
                  </div>
                )}
              </div>
              <div className="col-span-2 text-xs text-stone-500 dark:text-slate-500 truncate pt-0.5">
                {article.sitename || ''}
              </div>
              <div className="col-span-1 flex justify-end">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onToggleLida(article.id);
                  }}
                  className="text-sm leading-none transition"
                  title={isLida ? 'Marcar como não lida' : 'Marcar como lida'}
                  style={{ color: isLida ? '#65a30d' : '#cbd5e1' }}
                >
                  {isLida ? '●' : '○'}
                </button>
              </div>
            </article>
          );
        })}
      </div>
    </>
  );
};
