# ============================================================================
# Deploy D1 — Corpus Bolsonaro
# Executa: ALTER TABLE + upload dos 42 SQLs + verificação
# ============================================================================
#
# Uso:
#   .\deploy_d1.ps1
#
# Requisitos:
#   - wrangler autenticado
#   - work_data/export_d1/ populado (rodar export_cloudflare.py antes)

$ErrorActionPreference = "Continue"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " DEPLOY D1 — Corpus Bolsonaro 2019-2022" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# [1] ALTER TABLE — adicionar colunas v5 (se ainda não existem)
# ============================================================================

Write-Host "[1/4] Adicionando colunas topico_id_v5 e topico_nome_v5..." -ForegroundColor Yellow

wrangler d1 execute bolsonaro-corpus --remote --command="ALTER TABLE articles ADD COLUMN topico_id_v5 INTEGER;"
if ($LASTEXITCODE -ne 0) {
    Write-Host "      (coluna já existe ou erro — continuando)" -ForegroundColor DarkGray
}

wrangler d1 execute bolsonaro-corpus --remote --command="ALTER TABLE articles ADD COLUMN topico_nome_v5 TEXT;"
if ($LASTEXITCODE -ne 0) {
    Write-Host "      (coluna já existe ou erro — continuando)" -ForegroundColor DarkGray
}

Write-Host ""

# ============================================================================
# [2] Re-upload dos 42 SQLs
# ============================================================================

Write-Host "[2/4] Upload dos lotes SQL..." -ForegroundColor Yellow

$arquivos = Get-ChildItem work_data\export_d1\data_*.sql | Sort-Object Name
$total = $arquivos.Count
$i = 0
$falhas = 0

foreach ($f in $arquivos) {
    $i++
    Write-Host "      [$i/$total] $($f.Name)..." -NoNewline

    $output = wrangler d1 execute bolsonaro-corpus --remote --file="$($f.FullName)" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host " OK" -ForegroundColor Green
    } else {
        Write-Host " FALHA" -ForegroundColor Red
        Write-Host "      $output" -ForegroundColor DarkGray
        $falhas++

        # Se for limite diário, para tudo
        if ($output -match "daily row write limit") {
            Write-Host ""
            Write-Host "      [X] Cota D1 esgotada. Aguarde até 21h Brasília." -ForegroundColor Red
            Write-Host "      Progresso: $i/$total" -ForegroundColor Yellow
            exit 1
        }
    }
}

Write-Host ""

# ============================================================================
# [3] Verificar contagem
# ============================================================================

Write-Host "[3/4] Verificando contagem..." -ForegroundColor Yellow

wrangler d1 execute bolsonaro-corpus --remote --command="SELECT COUNT(*) AS total FROM articles;"

wrangler d1 execute bolsonaro-corpus --remote --command="SELECT topico_id_v5, topico_nome_v5, COUNT(*) AS n FROM articles WHERE topico_id_v5 IS NOT NULL GROUP BY topico_id_v5 ORDER BY n DESC LIMIT 5;"

Write-Host ""

# ============================================================================
# [4] Resumo final
# ============================================================================

Write-Host "[4/4] Resumo" -ForegroundColor Yellow
Write-Host "      Uploads: $($total - $falhas)/$total com sucesso" -ForegroundColor $(if ($falhas -eq 0) { "Green" } else { "Yellow" })
Write-Host ""

if ($falhas -eq 0) {
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host " D1 pronto. Próximos passos:" -ForegroundColor Green
    Write-Host "   1. wrangler deploy                     (deploy do Worker)" -ForegroundColor Green
    Write-Host "   2. Copy-Item index.html .pages_deploy\" -ForegroundColor Green
    Write-Host "   3. wrangler pages deploy .pages_deploy --project-name=bitsmarxistas --branch=main" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
} else {
    Write-Host "============================================================" -ForegroundColor Yellow
    Write-Host " $falhas lote(s) falharam. Rode de novo para retomar." -ForegroundColor Yellow
    Write-Host "============================================================" -ForegroundColor Yellow
}