import { useDarkMode } from '../hooks/useDarkMode';

export const Header = () => {
  const { dark, toggle } = useDarkMode();

  return (
    <header className="bg-white/95 dark:bg-slate-900/95 backdrop-blur border-b border-stone-200 dark:border-slate-800 sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 py-3 flex items-center gap-3">
        <div className="flex items-center gap-2 shrink-0">
          <span className="w-2.5 h-2.5 rounded-full bg-red-700" />
          <span className="font-display text-base">Corpus Bolsonaro</span>
          <span className="hidden sm:inline text-xs text-stone-400 dark:text-slate-500">2019–2022</span>
        </div>

        <div className="flex-1 max-w-lg mx-auto relative">
          <input
            id="busca-global"
            type="search"
            placeholder="Buscar tópico, palavra, entidade... (Ctrl+K)"
            className="w-full px-3 py-2 border border-stone-200 dark:border-slate-700 rounded-md text-sm bg-stone-50 dark:bg-slate-800 focus:bg-white dark:focus:bg-slate-800 focus:outline-none focus:border-stone-400 dark:focus:border-slate-500 transition-colors"
            autoComplete="off"
            aria-label="Busca global"
          />
        </div>

        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={toggle}
            className="text-base leading-none w-9 h-9 rounded-md hover:bg-stone-100 dark:hover:bg-slate-800"
            aria-label="Alternar tema"
          >
            {dark ? '☀️' : '🌙'}
          </button>
        </div>
      </div>
    </header>
  );
};
