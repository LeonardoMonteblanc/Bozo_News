import type {
  Article, Topic, Entity, TimelineEntry,
  CategoriasResponse, Dominio, NoticiasResponse,
  RedeResponse, SugestoesResponse, HealthResponse,
} from '../types';

const isLocalhost =
  typeof window !== 'undefined' &&
  (window.location.hostname === 'localhost' ||
   window.location.hostname === '127.0.0.1');

const API_BASE = isLocalhost ? '' : 'https://bozo-news-api.bitsmarxistas.workers.dev';

async function request<T>(path: string): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

export const api = {
  health: () => request<HealthResponse>('/health'),

  noticias: (params: {
    q?: string;
    topico?: number;
    entidade?: string;
    categoria?: string;
    dominio?: string;
    sentimento?: string;
    de?: string;
    ate?: string;
    ordenar?: 'data_desc' | 'data_asc' | 'relevancia';
    limit?: number;
    offset?: number;
  }): Promise<NoticiasResponse> => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') {
        qs.set(k, String(v));
      }
    });
    return request<NoticiasResponse>(`/api/noticias?${qs}`);
  },

  noticia: (id: number) => request<Article>(`/api/noticia/${id}`),

  topicos: (): Promise<Topic[]> => request<Topic[]>('/api/topicos'),

  topicosComPalavras: (limite = 20, palavras = 10) =>
    request<Topic[]>(`/api/topicos_com_palavras?limite=${limite}&palavras_por_topico=${palavras}`),

  entidades: (limite = 40): Promise<{ per: Entity[]; org: Entity[] }> =>
    request(`/api/entidades?limite=${limite}`),

  rede: (limite = 30): Promise<RedeResponse> =>
    request(`/api/rede?limite=${limite}`),

  timeline: (de: string, ate: string): Promise<TimelineEntry[]> =>
    request<TimelineEntry[]>(`/api/timeline?de=${de}&ate=${ate}`),

  categorias: (): Promise<CategoriasResponse[]> =>
    request<CategoriasResponse[]>('/api/categorias'),

  dominios: (limite = 50): Promise<Dominio[]> =>
    request<Dominio[]>(`/api/dominios?limite=${limite}`),

  sugestoes: (q: string): Promise<SugestoesResponse> =>
    request<SugestoesResponse>(`/api/sugestoes?q=${encodeURIComponent(q)}`),

  palavrasChave: (limite = 50): Promise<{ palavra: string; total: number }[]> =>
    request(`/api/palavras_chave?limite=${limite}`),
};
