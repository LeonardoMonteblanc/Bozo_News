import type { Topic } from '../types';
import { useState, useEffect } from 'react';
import { api } from '../lib/api';

interface TopicGridProps {
  onTopicSelect: (id: number | null) => void;
  selectedTopicId: number | null;
}

export const TopicGrid = ({ onTopicSelect, selectedTopicId }: TopicGridProps) => {
  const [topicos, setTopicos] = useState<Topic[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchTopicos = async () => {
      setLoading(true);
      try {
        const data = await api.topicos();
        setTopicos(data);
      } catch (err) {
        setError('Failed to load topics');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchTopicos();
  }, []);

  if (loading && topicos.length === 0) {
    return (
      <div className="col-span-3 text-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
        <p className="mt-2 text-stone-500 dark:text-slate-400">Carregando tópicos...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="col-span-3 text-center py-6">
        <p className="text-red-500">{error}</p>
      </div>
    );
  }

  if (topicos.length === 0) {
    return (
      <div className="col-span-3 text-center py-6">
        <p className="text-stone-500 dark:text-slate-400">Nenhum tópico encontrado</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
      {topicos.map(topic => (
        <div
          key={topic.id}
          className={`card-topico rounded-lg border p-4 bg-white dark:bg-slate-900 transition-all ${
            selectedTopicId === topic.id ? 'ring-2 ring-red-500' : ''
          }`}
          style={{
            borderColor: selectedTopicId === topic.id ? '#dc2626' : undefined,
          }}
          onClick={() => onTopicSelect(selectedTopicId === topic.id ? null : topic.id)}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              onTopicSelect(selectedTopicId === topic.id ? null : topic.id);
            }
          }}
        >
          <div className="flex items-baseline justify-between mb-2">
            <h3 className={`font-display text-base leading-tight ${selectedTopicId === topic.id ? 'text-red-600' : ''}`}>
              {topic.nome}
            </h3>
            <span className="text-xs text-stone-400 dark:text-slate-500 tabular-nums shrink-0 ml-2">
              {topic.total.toLocaleString('pt-BR')}
            </span>
          </div>
          <div className="flex flex-wrap gap-1">
            {(topic.palavras_top ?? []).slice(0, 8).map((palavraObj) => (
              <button
                key={palavraObj.palavra}
                className="chip-palavra"
                onClick={(e) => e.stopPropagation()}
              >
                {palavraObj.palavra}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};
