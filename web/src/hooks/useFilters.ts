import { useState, useCallback } from 'react';
import type { Ordenar, Panela } from '../types';

export interface FiltersState {
  q: string;
  topico: number | null;
  entidade: string;
  categoria: string;
  dominio: string;
  sentimento: string;
  de: string;
  ate: string;
  ordenar: Ordenar;
  limit: number;
  offset: number;
  ocultarLidas: boolean;
  painel: Panela;
}

export function useFilters() {
  const [state, setState] = useState<FiltersState>({
    q: '',
    topico: null,
    entidade: '',
    categoria: '',
    dominio: '',
    sentimento: '',
    de: '',
    ate: '',
    ordenar: 'data_desc',
    limit: 20,
    offset: 0,
    ocultarLidas: false,
    painel: 'noticias',
  });

  const update = useCallback((partial: Partial<FiltersState>) => {
    setState(prev => ({ ...prev, ...partial }));
  }, []);

  const reset = useCallback(() => {
    setState({
      q: '',
      topico: null,
      entidade: '',
      categoria: '',
      dominio: '',
      sentimento: '',
      de: '',
      ate: '',
      ordenar: 'data_desc',
      limit: 20,
      offset: 0,
      ocultarLidas: false,
      painel: 'noticias',
    });
  }, []);

  const nextPage = useCallback(() => {
    update({ offset: state.offset + state.limit });
  }, [state.offset, state.limit, update]);

  const prevPage = useCallback(() => {
    update({ offset: Math.max(0, state.offset - state.limit) });
  }, [state.offset, state.limit, update]);

  const toggleTopico = useCallback((id: number) => {
    setState(prev => ({
      ...prev,
      topico: prev.topico === id ? null : id,
      offset: 0,
    }));
  }, []);

  return { state, update, reset, nextPage, prevPage, toggleTopico };
}
