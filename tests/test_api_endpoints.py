"""
Testes unitários para a API do Corpus Bolsonaro.
Executar: python -m pytest tests/test_api_endpoints.py -v
"""
import pytest
import json
from fastapi.testclient import TestClient
from src.api import app
from src.api.routes.noticias import listar_noticias
from src.api.routes.topicos import listar_topicos, topicos_com_palavras
from src.api.routes.entidades import listar_entidades, rede
from src.api.routes.agregacoes import timeline, categorias, dominios, palavras_chave
from src.api.routes.sugestoes import sugestoes


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_status(self, client):
        """Testa se o health check retorna status ok."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "artigos_no_banco" in data


class TestNoticiasEndpoints:
    def test_listar_noticias_basic(self, client):
        """Testa listagem básica de notícias."""
        response = client.get("/api/noticias?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "itens" in data
        assert len(data["itens"]) <= 5

    def test_noticias_with_filters(self, client):
        """Testa filtros de notícias."""
        response = client.get("/api/noticias?limit=5&topico=100")
        assert response.status_code == 200
        data = response.json()
        assert "itens" in data

    def test_get_noticia(self, client):
        """Testa obtenção de uma notícia específica."""
        # Primeiro precisa ter alguma notícia
        noticias_resp = client.get("/api/noticias?limit=1")
        if noticias_resp.json()["itens"]:
            noticia_id = noticias_resp.json()["itens"][0]["id"]
            response = client.get(f"/api/noticia/{noticia_id}")
            assert response.status_code == 200


class TestTopicosEndpoints:
    def test_listar_topicos(self, client):
        """Testa listagem de tópicos."""
        response = client.get("/api/topicos")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if data:
            assert "topico_id" in data[0]
            assert "nome" in data[0]
            assert "total" in data[0]

    def test_topicos_com_palavras(self, client):
        """Testa tópicos com palavras-chave."""
        response = client.get("/api/topicos_com_palavras?limite=3&palavras_por_topico=5")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestEntidadesEndpoints:
    def test_listar_entidades(self, client):
        """Testa listagem de entidades."""
        response = client.get("/api/entidades?limite=10")
        assert response.status_code == 200
        data = response.json()
        assert "per" in data
        assert "org" in data

    def test_rede(self, client):
        """Testa endpoint de rede."""
        response = client.get("/api/rede?limite=5")
        assert response.status_code == 200
        data = response.json()
        assert "nos" in data
        assert "arestas" in data


class TestAgregacoesEndpoints:
    def test_timeline(self, client):
        """Testa endpoint de timeline."""
        response = client.get("/api/timeline")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_categorias(self, client):
        """Testa endpoint de categorias."""
        response = client.get("/api/categorias")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_dominios(self, client):
        """Testa endpoint de dominios."""
        response = client.get("/api/dominios?limite=5")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_palavras_chave(self, client):
        """Testa endpoint de palavras-chave."""
        response = client.get("/api/palavras_chave?limite=10")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestSugestoesEndpoints:
    def test_sugestoes_com_query(self, client):
        """Testa sugestões com query."""
        response = client.get("/api/sugestoes?q=bols")
        assert response.status_code == 200
        data = response.json()
        assert "entidades" in data
        assert "topicos" in data
        assert "categorias" in data
        assert "total_noticias" in data

    def test_sugestoes_query_curta(self, client):
        """Testa sugestões com query curta."""
        response = client.get("/api/sugestoes?q=a")
        assert response.status_code == 200
        data = response.json()
        # Deve retornar arrays vazios para queries curtas
        assert data["entidades"] == []
        assert data["topicos"] == []


class TestSQLInjectionProtection:
    def test_like_escape(self, client):
        """Testa se caracteres especiais são escapados em LIKE queries."""
        response = client.get('/api/noticias?entidade=%')
        assert response.status_code == 200
        data = response.json()
        assert "itens" in data
