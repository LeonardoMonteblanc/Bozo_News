import { Header } from './components/Header';
import { StatsCards } from './components/StatsCards';
import { TopicGrid } from './components/TopicGrid';
import { NewsList } from './components/NewsList';
import { Entities } from './components/Entities';
import { Timeline } from './components/Timeline';
import { useState } from 'react';
import { useFilters } from './hooks/useFilters';
import { useLocalStorage } from './hooks/useLocalStorage';

function App() {
  const [lidas, setLidas] = useLocalStorage<number[]>('lidas', []);
  const lidasSet = new Set(lidas);
  const { state: filters, update: updateFilters, reset: resetFilters } = useFilters();
  const [selectedTopicId, setSelectedTopicId] = useState<number | null>(null);
  const [openModalId, setOpenModalId] = useState<number | null>(null);

  const handleToggleLida = (id: number) => {
    setLidas((prev: number[]) => {
      const newSet = new Set(prev);
      if (newSet.has(id)) {
        newSet.delete(id);
      } else {
        newSet.add(id);
      }
      return Array.from(newSet);
    });
  };

  const handleOpenModal = (id: number) => {
    setOpenModalId(id);
  };

  const handleCloseModal = () => {
    setOpenModalId(null);
  };

  const activeFilters = filters.q || filters.topico !== null || filters.categoria || filters.dominio || filters.sentimento || filters.entidade || filters.de || filters.ate;

  return (
    <div className="min-h-screen bg-stone-50 dark:bg-slate-950 text-stone-900 dark:text-slate-100 transition-colors">
      <Header />
      <main id="conteudo" className="max-w-7xl mx-auto px-4 py-6">
        <StatsCards />
        <div className="mb-6 flex gap-2 flex-wrap items-center min-h-[2rem]">
          <span id="chips-vazio" className={`text-xs text-stone-400 dark:text-slate-500 ${activeFilters ? 'hidden' : ''}`}>
            Nenhum filtro ativo. Clique em um tópico ou palavra para começar.
          </span>
          <div id="chips-container" className="flex gap-2 flex-wrap"></div>
          <button
            id="btn-limpar"
            onClick={resetFilters}
            className={`hidden text-xs text-red-700 dark:text-red-400 hover:underline ml-2 ${activeFilters ? '' : 'hidden'}`}
          >
            limpar tudo
          </button>
        </div>

        <div className="flex items-baseline justify-between mb-3">
          <h2 className="font-display text-xl">Tópicos</h2>
          <span className="text-xs text-stone-500 dark:text-slate-500">12 temas · clique para explorar</span>
        </div>
        <TopicGrid
          onTopicSelect={(id) => {
            setSelectedTopicId(id);
            updateFilters({ topico: id ?? undefined, offset: 0 });
          }}
          selectedTopicId={selectedTopicId}
        />

        <section id="resultados" className="bg-white dark:bg-slate-900 rounded-lg border border-stone-200 dark:border-slate-800">
          <div className="border-b border-stone-200 dark:border-slate-800 flex overflow-x-auto">
            <button
              data-painel="noticias"
              className={filters.painel === 'noticias' ? 'panel-tab active' : 'panel-tab'}
              onClick={() => updateFilters({ painel: 'noticias' })}
            >
              Notícias
            </button>
            <button
              data-painel="timeline"
              className={filters.painel === 'timeline' ? 'panel-tab active' : 'panel-tab'}
              onClick={() => updateFilters({ painel: 'timeline' })}
            >
              Timeline
            </button>
            <button
              data-painel="entidades"
              className={filters.painel === 'entidades' ? 'panel-tab active' : 'panel-tab'}
              onClick={() => updateFilters({ painel: 'entidades' })}
            >
              Entidades
            </button>
            <button
              data-painel="rede"
              className={filters.painel === 'rede' ? 'panel-tab active' : 'panel-tab'}
              onClick={() => updateFilters({ painel: 'rede' })}
            >
              Rede
            </button>
            <button
              data-painel="filtros"
              className={filters.painel === 'filtros' ? 'panel-tab active' : 'panel-tab'}
              onClick={() => updateFilters({ painel: 'filtros' })}
            >
              Mais filtros
            </button>
          </div>

          {filters.painel === 'noticias' && (
            <NewsList
              filters={{
                q: filters.q,
                topico: filters.topico ?? undefined,
                entidade: filters.entidade,
                categoria: filters.categoria,
                dominio: filters.dominio,
                sentimento: filters.sentimento,
                de: filters.de,
                ate: filters.ate,
                ordenar: filters.ordenar,
                limit: filters.limit,
                offset: filters.offset,
                ocultarLidas: filters.ocultarLidas,
              }}
              lidas={lidasSet}
              onToggleLida={handleToggleLida}
              onOpenModal={handleOpenModal}
            />
          )}
          {filters.painel === 'timeline' && <Timeline />}
          {filters.painel === 'entidades' && <Entities onEntitySelect={nome => {
            updateFilters({ entidade: nome, offset: 0 });
          }} />}
          {filters.painel === 'rede' && <div className="p-6">Rede visualization placeholder</div>}
          {filters.painel === 'filtros' && (
            <div className="p-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="text-xs font-medium text-stone-600 dark:text-slate-400">Categoria</label>
                  <select
                    className="w-full mt-1 px-3 py-2 border border-stone-200 dark:border-slate-700 rounded-md text-sm bg-white dark:bg-slate-800"
                    value={filters.categoria}
                    onChange={(e) => updateFilters({ categoria: e.target.value, offset: 0 })}
                  >
                    <option value="">todas</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-stone-600 dark:text-slate-400">Veículo</label>
                  <select
                    className="w-full mt-1 px-3 py-2 border border-stone-200 dark:border-slate-700 rounded-md text-sm bg-white dark:bg-slate-800"
                    value={filters.dominio}
                    onChange={(e) => updateFilters({ dominio: e.target.value, offset: 0 })}
                  >
                    <option value="">todos</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-stone-600 dark:text-slate-400">Sentimento</label>
                  <select
                    className="w-full mt-1 px-3 py-2 border border-stone-200 dark:border-slate-700 rounded-md text-sm bg-white dark:bg-slate-800"
                    value={filters.sentimento}
                    onChange={(e) => updateFilters({ sentimento: e.target.value, offset: 0 })}
                  >
                    <option value="">todos</option>
                    <option value="positivo">positivo</option>
                    <option value="negativo">negativo</option>
                    <option value="neutro">neutro</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-stone-600 dark:text-slate-400">De</label>
                  <input
                    type="date"
                    min="2019-01-01"
                    max="2022-12-31"
                    className="w-full mt-1 px-3 py-2 border border-stone-200 dark:border-slate-700 rounded-md text-sm bg-white dark:bg-slate-800"
                    value={filters.de}
                    onChange={(e) => updateFilters({ de: e.target.value, offset: 0 })}
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-stone-600 dark:text-slate-400">Até</label>
                  <input
                    type="date"
                    min="2019-01-01"
                    max="2022-12-31"
                    className="w-full mt-1 px-3 py-2 border border-stone-200 dark:border-slate-700 rounded-md text-sm bg-white dark:bg-slate-800"
                    value={filters.ate}
                    onChange={(e) => updateFilters({ ate: e.target.value, offset: 0 })}
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-stone-600 dark:text-slate-400">Entidade</label>
                  <input
                    type="text"
                    placeholder="ex: Bolsonaro"
                    className="w-full mt-1 px-3 py-2 border border-stone-200 dark:border-slate-700 rounded-md text-sm bg-white dark:bg-slate-800"
                    value={filters.entidade}
                    onChange={(e) => updateFilters({ entidade: e.target.value, offset: 0 })}
                  />
                </div>
              </div>
              <div className="mt-4 flex gap-2">
                <button
                  onClick={() => updateFilters({ offset: 0 })}
                  className="bg-red-700 hover:bg-red-800 text-white text-sm px-4 py-2 rounded-md font-medium"
                >
                  Aplicar
                </button>
                <button
                  onClick={resetFilters}
                  className="bg-stone-100 dark:bg-slate-800 hover:bg-stone-200 dark:hover:bg-slate-700 text-sm px-4 py-2 rounded-md"
                >
                  Limpar
                </button>
              </div>
            </div>
          )}
        </section>
      </main>

      {openModalId !== null && (
        <div
          className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4"
          onClick={(e) => {
            if (e.target === e.currentTarget) handleCloseModal();
          }}
        >
          <div className="bg-white dark:bg-slate-900 rounded-lg shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto fade-in" role="dialog" aria-modal="true">
            <div className="p-5 border-b border-stone-200 dark:border-slate-800 flex justify-between items-start sticky top-0 bg-white dark:bg-slate-900 z-10">
              <h3 className="font-display text-lg pr-4 leading-tight">ID: {openModalId}</h3>
              <button
                onClick={handleCloseModal}
                className="text-stone-400 hover:text-stone-700 dark:hover:text-slate-200 text-2xl leading-none w-8 h-8"
              >
                ×
              </button>
            </div>
            <div className="p-5 space-y-4">
              <p className="text-stone-500 dark:text-slate-400">Carregando detalhes da notícia...</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
