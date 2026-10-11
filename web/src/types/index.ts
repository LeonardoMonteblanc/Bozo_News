export interface Article {
  id: number;
  data: string;
  titulo: string;
  resumo?: string;
  url: string;
  sitename?: string;
  categoria?: string;
  sentimento_label?: string;
  topico_id?: number | null;
  topico_id_v5?: number | null;
  topico_nome_v5?: string | null;
  entidades_per?: string[];
  entidades_org?: string[];
  bolsonaro_score?: number;
}

export interface Topic {
  id: number;
  nome: string;
  total: number;
  keywords_bertopic?: string[];
  palavras_top?: { palavra: string; total: number }[];
}

export interface Entity {
  nome: string;
  total: number;
}

export interface TimelineEntry {
  mes: string;
  total: number;
}

export interface CategoriasResponse {
  categoria: string;
  total: number;
}

export interface Dominio {
  domain: string;
  total: number;
}

export interface NoticiasResponse {
  total: number;
  limit: number;
  offset: number;
  itens: Article[];
}

export interface RedeResponse {
  nos: { id: string; total: number }[];
  arestas: { source: string; target: string; peso: number }[];
}

export interface SugestoesResponse {
  entidades: Entity[];
  topicos: Topic[];
  categorias: CategoriasResponse[];
  total_noticias: number;
}

export interface HealthResponse {
  status: string;
  artigos_no_banco: number;
}

export type Ordenar = 'data_desc' | 'data_asc' | 'relevancia';
export type Panela = 'noticias' | 'timeline' | 'entidades' | 'rede' | 'filtros';
