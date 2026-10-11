import { useEffect, useState } from 'react';
import { api } from '../lib/api';

export const StatsCards = () => {
  const [stats, setStats] = useState<{
    noticias: number;
    topicos: number;
    periodo: string;
    topTopic: string;
  }>({
    noticias: 0,
    topicos: 0,
    periodo: '4 anos',
    topTopic: '—',
  });

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const [noticiasResp, topicosResp] = await Promise.all([
          api.noticias({ limit: 1 }),
          api.topicos(),
        ]);

        const topTopicName = topicosResp.length > 0
          ? topicosResp[0].nome.split(' ').slice(0, 2).join(' ')
          : '—';

        setStats({
          noticias: noticiasResp.total,
          topicos: topicosResp.length,
          periodo: '4 anos',
          topTopic: topTopicName,
        });
      } catch (error) {
        console.error('Failed to fetch stats:', error);
      }
    };

    fetchStats();
  }, []);

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
      <div className="rounded-lg border border-stone-200 dark:border-slate-800 p-4">
        <div className="text-xs uppercase tracking-wider text-stone-500 dark:text-slate-500 mb-1">Notícias</div>
        <div className="font-display text-2xl">{stats.noticias.toLocaleString('pt-BR')}</div>
      </div>
      <div className="rounded-lg border border-stone-200 dark:border-slate-800 p-4">
        <div className="text-xs uppercase tracking-wider text-stone-500 dark:text-slate-500 mb-1">Tópicos</div>
        <div className="font-display text-2xl">{stats.topicos}</div>
      </div>
      <div className="rounded-lg border border-stone-200 dark:border-slate-800 p-4">
        <div className="text-xs uppercase tracking-wider text-stone-500 dark:text-slate-500 mb-1">Período</div>
        <div className="font-display text-2xl">{stats.periodo}</div>
      </div>
      <div className="rounded-lg border border-stone-200 dark:border-slate-800 p-4">
        <div className="text-xs uppercase tracking-wider text-stone-500 dark:text-slate-500 mb-1">Maior tópico</div>
        <div className="font-display text-2xl truncate">{stats.topTopic}</div>
      </div>
    </div>
  );
};
