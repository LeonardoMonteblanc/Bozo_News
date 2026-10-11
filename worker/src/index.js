/**
 * ============================================================================
 * API Cloudflare Worker — Corpus Bolsonaro 2019-2022
 * ============================================================================
 *
 * Bindings:
 *   DB → D1 (metadados)
 *
 * Roteamento:
 *   GET /                          → índice de endpoints
 *   GET /health                    → status da API
 *   GET /api/noticias              → lista com filtros
 *   GET /api/noticia/:id           → detalhe
 *   GET /api/timeline              → série temporal por mês
 *   GET /api/categorias            → distribuição por categoria
 *   GET /api/dominios              → distribuição por domínio
 *   GET /api/topicos               → lista de tópicos v5
 *   GET /api/entidades             → top PER + ORG
 *   GET /api/rede                  → grafo de co-ocorrência
 *   GET /api/palavras_chave        → nuvem de palavras
 *   GET /api/sugestoes             → autocomplete
 *   GET /api/topicos_com_palavras  → tópicos + palavras (visualização)
 * ============================================================================
 */

// ============================================================================
// CONSTANTES
// ============================================================================

const FILTRO_BASE = "(mention_bolsonaro = 1 OR relevance_bolsonaro = 1)";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

// ============================================================================
// HELPERS
// ============================================================================

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...CORS,
    },
  });
}

function erro(msg, status = 400) {
  return json({ erro: msg }, status);
}

function parseJSONField(v) {
  if (!v) return [];
  try {
    return JSON.parse(v);
  } catch {
    return [];
  }
}

function rowBasico(r) {
  return {
    id: r.id,
    data: r.data,
    titulo: r.titulo,
    resumo: r.resumo,
    url: r.url,
    sitename: r.sitename,
    categoria: r.categoria,
    sentimento_label: r.sentimento_label,
    topico_id: r.topico_id,
    topico_id_v5: r.topico_id_v5,
    topico_nome_v5: r.topico_nome_v5,
    entidades_per: parseJSONField(r.entidades_per),
    entidades_org: parseJSONField(r.entidades_org),
    bolsonaro_score: r.bolsonaro_score,
  };
}

// ============================================================================
// HANDLERS
// ============================================================================

async function handleHealth(env) {
  const r = await env.DB.prepare("SELECT COUNT(*) AS n FROM articles").first();
  return json({
    status: "ok",
    artigos_no_banco: r.n,
    timestamp: new Date().toISOString(),
  });
}

async function handleNoticias(env, url) {
  const p = url.searchParams;
  const where = [FILTRO_BASE];
  const binds = [];

  const q          = p.get("q");
  const de         = p.get("de");
  const ate        = p.get("ate");
  const categoria  = p.get("categoria");
  const dominio    = p.get("dominio");
  const topico     = p.get("topico");
  const sentimento = p.get("sentimento");
  const entidade   = p.get("entidade");
  const soRelev    = p.get("so_relevantes") === "true";
  const ordenar    = p.get("ordenar") || "data_desc";
  const limit      = Math.min(200, Math.max(1, parseInt(p.get("limit")) || 30));
  const offset     = Math.max(0, parseInt(p.get("offset")) || 0);

  if (soRelev) where.push("relevance_bolsonaro = 1");
  if (de)  { where.push("data >= ?"); binds.push(de); }
  if (ate) { where.push("data <= ?"); binds.push(ate); }
  if (categoria) { where.push("categoria = ?"); binds.push(categoria); }
  if (dominio)   { where.push("domain = ?");    binds.push(dominio); }
  if (topico !== null && topico !== "") {
    where.push("topico_id_v5 = ?");
    binds.push(parseInt(topico));
  }
  if (sentimento) { where.push("sentimento_label = ?"); binds.push(sentimento); }
  if (entidade) {
    where.push("(entidades_per LIKE ? OR entidades_org LIKE ?)");
    binds.push(`%${entidade}%`);
    binds.push(`%${entidade}%`);
  }

  const whereSQL = where.join(" AND ");

  let sqlCount, sqlData, bindsCount, bindsData;

  if (q) {
    const order = ordenar === "data_asc" ? "ASC" : "DESC";
    sqlCount = `
      SELECT COUNT(*) AS n FROM articles a
      JOIN articles_fts f ON f.rowid = a.id
      WHERE articles_fts MATCH ? AND ${whereSQL}
    `;
    sqlData = `
      SELECT a.id, a.data, a.titulo, a.resumo, a.url, a.sitename,
             a.categoria, a.sentimento_label,
             a.topico_id, a.topico_id_v5, a.topico_nome_v5,
             a.entidades_per, a.entidades_org, a.bolsonaro_score
      FROM articles a
      JOIN articles_fts f ON f.rowid = a.id
      WHERE articles_fts MATCH ? AND ${whereSQL}
      ORDER BY a.data ${order}
      LIMIT ? OFFSET ?
    `;
    bindsCount = [q, ...binds];
    bindsData  = [q, ...binds, limit, offset];
  } else {
    const orderMap = {
      data_desc:  "data DESC",
      data_asc:   "data ASC",
      relevancia: "bolsonaro_score DESC, data DESC",
    };
    const order = orderMap[ordenar] || "data DESC";

    sqlCount = `SELECT COUNT(*) AS n FROM articles WHERE ${whereSQL}`;
    sqlData = `
      SELECT id, data, titulo, resumo, url, sitename,
             categoria, sentimento_label,
             topico_id, topico_id_v5, topico_nome_v5,
             entidades_per, entidades_org, bolsonaro_score
      FROM articles
      WHERE ${whereSQL}
      ORDER BY ${order}
      LIMIT ? OFFSET ?
    `;
    bindsCount = [...binds];
    bindsData  = [...binds, limit, offset];
  }

  const total = await env.DB.prepare(sqlCount).bind(...bindsCount).first();
  const { results } = await env.DB.prepare(sqlData).bind(...bindsData).all();

  return json({
    total: total.n,
    limit,
    offset,
    itens: results.map(rowBasico),
  });
}

async function handleNoticia(env, id) {
  const r = await env.DB.prepare(
    "SELECT * FROM articles WHERE id = ?"
  ).bind(id).first();

  if (!r) return erro("Notícia não encontrada", 404);

  return json({
    ...r,
    palavras_chave: parseJSONField(r.palavras_chave),
    entidades_per: parseJSONField(r.entidades_per),
    entidades_org: parseJSONField(r.entidades_org),
    entidades_loc: parseJSONField(r.entidades_loc),
    entidades_misc: parseJSONField(r.entidades_misc),
    topico_palavras: parseJSONField(r.topico_palavras),
    topico_palavras_v2: parseJSONField(r.topico_palavras_v2),
  });
}

async function handleTimeline(env, url) {
  const p = url.searchParams;
  const de  = p.get("de")  || "2019-01-01";
  const ate = p.get("ate") || "2022-12-31";
  const soRelev = p.get("so_relevantes") === "true";
  const filtro = soRelev ? " AND relevance_bolsonaro = 1" : "";

  const { results } = await env.DB.prepare(`
    SELECT substr(data,1,7) AS mes, COUNT(*) AS total
    FROM articles
    WHERE data BETWEEN ? AND ? ${filtro}
    GROUP BY mes
    ORDER BY mes
  `).bind(de, ate).all();

  return json(results);
}

async function handleCategorias(env) {
  const { results } = await env.DB.prepare(`
    SELECT COALESCE(categoria,'?') AS categoria, COUNT(*) AS total
    FROM articles
    WHERE ${FILTRO_BASE}
    GROUP BY categoria
    ORDER BY total DESC
  `).all();
  return json(results);
}

async function handleDominios(env, url) {
  const limite = Math.min(200, parseInt(url.searchParams.get("limite")) || 30);
  const { results } = await env.DB.prepare(`
    SELECT domain, COUNT(*) AS total
    FROM articles
    WHERE ${FILTRO_BASE} AND domain IS NOT NULL
    GROUP BY domain
    ORDER BY total DESC
    LIMIT ?
  `).bind(limite).all();
  return json(results);
}

async function handleTopicos(env) {
  const { results } = await env.DB.prepare(`
    SELECT topico_id_v5 AS topico_id,
           topico_nome_v5 AS nome,
           COUNT(*) AS total
    FROM articles
    WHERE ${FILTRO_BASE} AND topico_id_v5 IS NOT NULL
    GROUP BY topico_id_v5
    ORDER BY total DESC
  `).all();
  return json(results);
}

async function handleEntidades(env, url) {
  const limite = Math.min(100, parseInt(url.searchParams.get("limite")) || 40);

  const { results } = await env.DB.prepare(`
    SELECT entidades_per, entidades_org
    FROM articles
    WHERE ${FILTRO_BASE} AND entidades_per IS NOT NULL
  `).all();

  const per = new Map();
  const org = new Map();

  for (const r of results) {
    for (const p of parseJSONField(r.entidades_per)) {
      per.set(p, (per.get(p) || 0) + 1);
    }
    for (const o of parseJSONField(r.entidades_org)) {
      org.set(o, (org.get(o) || 0) + 1);
    }
  }

  const ordenar = (m) => Array.from(m.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, limite)
    .map(([nome, total]) => ({ nome, total }));

  return json({ per: ordenar(per), org: ordenar(org) });
}

async function handleRede(env, url) {
  const limite  = Math.min(100, parseInt(url.searchParams.get("limite")) || 30);
  const minCooc = parseInt(url.searchParams.get("min_cooc")) || 3;

  const { results } = await env.DB.prepare(`
    SELECT entidades_per FROM articles
    WHERE ${FILTRO_BASE} AND entidades_per IS NOT NULL
  `).all();

  const freq = new Map();
  const cooc = new Map();

  for (const r of results) {
    const per = Array.from(new Set(parseJSONField(r.entidades_per)))
      .filter(p => p.length >= 4);
    for (const p of per) {
      freq.set(p, (freq.get(p) || 0) + 1);
    }
    for (let i = 0; i < per.length; i++) {
      for (let j = i + 1; j < per.length; j++) {
        const par = [per[i], per[j]].sort().join("||");
        cooc.set(par, (cooc.get(par) || 0) + 1);
      }
    }
  }

  const topNos = Array.from(freq.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, limite);
  const topNosSet = new Set(topNos.map(([n]) => n));

  const arestas = [];
  for (const [par, c] of cooc.entries()) {
    if (c < minCooc) continue;
    const [a, b] = par.split("||");
    if (topNosSet.has(a) && topNosSet.has(b)) {
      arestas.push({ source: a, target: b, peso: c });
    }
  }
  arestas.sort((x, y) => y.peso - x.peso);

  return json({
    nos: topNos.map(([id, total]) => ({ id, total })),
    arestas: arestas.slice(0, limite * 5),
  });
}

async function handlePalavrasChave(env, url) {
  const limite  = Math.min(300, parseInt(url.searchParams.get("limite")) || 100);
  const minFreq = Math.max(1, parseInt(url.searchParams.get("min_freq")) || 3);

  const { results } = await env.DB.prepare(`
    SELECT palavras_chave FROM articles
    WHERE ${FILTRO_BASE}
      AND palavras_chave IS NOT NULL
      AND palavras_chave != '[]'
  `).all();

  const freq = new Map();
  for (const r of results) {
    const kws = parseJSONField(r.palavras_chave);
    for (const kw of kws) {
      const k = String(kw).trim().toLowerCase();
      if (k.length < 4 || k.length > 40) continue;
      freq.set(k, (freq.get(k) || 0) + 1);
    }
  }

  const lista = Array.from(freq.entries())
    .filter(([, n]) => n >= minFreq)
    .sort((a, b) => b[1] - a[1])
    .slice(0, limite)
    .map(([palavra, total]) => ({ palavra, total }));

  return json(lista);
}

async function handleSugestoes(env, url) {
  const q = (url.searchParams.get("q") || "").trim().toLowerCase();
  if (q.length < 2) {
    return json({ entidades: [], topicos: [], categorias: [], total_noticias: 0 });
  }

  const like = `%${q}%`;

  const countRes = await env.DB.prepare(`
    SELECT COUNT(*) AS n FROM articles
    WHERE ${FILTRO_BASE}
      AND (LOWER(titulo) LIKE ? OR LOWER(resumo) LIKE ?)
  `).bind(like, like).first();

  // Entidades
  const entRes = await env.DB.prepare(`
    SELECT entidades_per, entidades_org FROM articles
    WHERE ${FILTRO_BASE}
      AND (LOWER(entidades_per) LIKE ? OR LOWER(entidades_org) LIKE ?)
    LIMIT 200
  `).bind(like, like).all();

  const entMap = new Map();
  for (const r of entRes.results) {
    const todos = [
      ...parseJSONField(r.entidades_per),
      ...parseJSONField(r.entidades_org),
    ];
    for (const e of todos) {
      const key = String(e);
      if (!key.toLowerCase().includes(q)) continue;
      entMap.set(key, (entMap.get(key) || 0) + 1);
    }
  }
  const entidades = Array.from(entMap.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([nome, total]) => ({ nome, total }));

  // Tópicos (por nome v5)
  const topRes = await env.DB.prepare(`
    SELECT topico_id_v5 AS topico_id,
           topico_nome_v5 AS nome,
           COUNT(*) AS total
    FROM articles
    WHERE ${FILTRO_BASE} AND topico_id_v5 IS NOT NULL
    GROUP BY topico_id_v5
  `).all();

  const topicos = [];
  for (const t of topRes.results) {
    const nome = t.nome || "";
    if (nome.toLowerCase().includes(q)) {
      topicos.push({ id: t.topico_id, nome, total: t.total });
    }
  }

  // Categorias
  const catRes = await env.DB.prepare(`
    SELECT categoria, COUNT(*) AS total FROM articles
    WHERE ${FILTRO_BASE} AND LOWER(categoria) LIKE ?
    GROUP BY categoria
    ORDER BY total DESC
    LIMIT 3
  `).bind(like).all();

  return json({
    entidades,
    topicos: topicos.slice(0, 5),
    categorias: catRes.results.map(r => ({ nome: r.categoria, total: r.total })),
    total_noticias: countRes.n,
  });
}

async function handleTopicosComPalavras(env, url) {
  const limite = Math.min(20, parseInt(url.searchParams.get("limite")) || 20);
  const palavrasPorTopico = Math.min(15, parseInt(url.searchParams.get("palavras_por_topico")) || 15);

  const BLACKLIST = new Set([
    "jair bolsonaro", "bolsonaro", "jair", "presidente jair",
    "presidente", "folhapress", "agência brasil", "agencia brasil",
    "estadão conteúdo", "estadao conteudo", "reuters", "brasil",
    "paulo", "são paulo", "sao paulo", "reprodução", "reproducao",
    "foto", "imagem", "g1", "globo", "uol", "folha",
    "ministério", "ministerio", "governo", "federal", "nacional",
  ]);

  const { results: palavrasRes } = await env.DB.prepare(`
    SELECT a.topico_id_v5 AS topico_id, j.value AS palavra, COUNT(*) AS total
    FROM articles a, json_each(a.palavras_chave) j
    WHERE ${FILTRO_BASE}
      AND a.topico_id_v5 IS NOT NULL
      AND a.palavras_chave IS NOT NULL
      AND length(j.value) >= 5
    GROUP BY a.topico_id_v5, j.value
    ORDER BY a.topico_id_v5, total DESC
  `).all();

  const { results: metaRes } = await env.DB.prepare(`
    SELECT topico_id_v5 AS topico_id,
           topico_nome_v5 AS nome,
           COUNT(*) AS total,
           MAX(topico_palavras_v2) AS palavras
    FROM articles
    WHERE ${FILTRO_BASE} AND topico_id_v5 IS NOT NULL
    GROUP BY topico_id_v5
    ORDER BY total DESC
    LIMIT ?
  `).bind(limite).all();

  const porTopico = {};
  for (const r of palavrasRes) {
    const tid = r.topico_id;
    const pal = String(r.palavra).toLowerCase().trim();
    if (BLACKLIST.has(pal)) continue;
    if (pal.startsWith("bolsonaro ") || pal.endsWith(" bolsonaro")) continue;
    if (pal.startsWith("presidente ")) continue;
    if (!porTopico[tid]) porTopico[tid] = [];
    if (porTopico[tid].length < palavrasPorTopico) {
      porTopico[tid].push({ palavra: r.palavra, total: r.total });
    }
  }

  const resultado = metaRes.map(m => ({
    id: m.topico_id,
    nome: m.nome || `Tópico ${m.topico_id}`,
    total: m.total,
    keywords_bertopic: parseJSONField(m.palavras).slice(0, 8),
    palavras_top: porTopico[m.topico_id] || [],
  }));

  return json(resultado);
}

// ============================================================================
// ROTEADOR
// ============================================================================

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS });
    }
    if (request.method !== "GET") {
      return erro("Método não permitido", 405);
    }

    try {
      if (path === "/health")                    return await handleHealth(env);
      if (path === "/api/noticias")              return await handleNoticias(env, url);
      if (path === "/api/timeline")              return await handleTimeline(env, url);
      if (path === "/api/categorias")            return await handleCategorias(env);
      if (path === "/api/dominios")              return await handleDominios(env, url);
      if (path === "/api/topicos")               return await handleTopicos(env);
      if (path === "/api/entidades")             return await handleEntidades(env, url);
      if (path === "/api/rede")                  return await handleRede(env, url);
      if (path === "/api/palavras_chave")        return await handlePalavrasChave(env, url);
      if (path === "/api/sugestoes")             return await handleSugestoes(env, url);
      if (path === "/api/topicos_com_palavras")  return await handleTopicosComPalavras(env, url);

      const m = path.match(/^\/api\/noticia\/(\d+)$/);
      if (m) return await handleNoticia(env, parseInt(m[1]));

      if (path === "/") {
        return json({
          nome: "Corpus Bolsonaro 2019-2022 API",
          versao: "1.0",
          endpoints: [
            "/health", "/api/noticias", "/api/noticia/:id",
            "/api/timeline", "/api/categorias", "/api/dominios",
            "/api/topicos", "/api/entidades", "/api/rede",
            "/api/palavras_chave", "/api/sugestoes",
            "/api/topicos_com_palavras",
          ],
        });
      }

      return erro("Rota não encontrada: " + path, 404);
    } catch (e) {
      return json({ erro: e.message, stack: e.stack }, 500);
    }
  },
};