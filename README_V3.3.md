# Family Finance V3.3 — Design System

Esta versão introduz a identidade visual oficial do **Family Finance**, sem alterar a lógica financeira ou a base de dados.

## Paleta oficial

| Token | Cor | Utilização |
|---|---|---|
| Primary | `#0B4F9C` | navegação, ações principais, identidade |
| Success | `#159A78` | poupança, receitas, sucesso |
| Warning | `#E6A23C` | atenção, contratos, desvios |
| Danger | `#D9534F` | erros, risco, situações críticas |
| Info | `#2798C7` | informação, insights |
| Background | `#F5F8FB` | fundo global |
| Surface | `#FFFFFF` | cards, tabelas, formulários |
| Text | `#17324D` | texto principal |
| Muted | `#6B7C8F` | legendas e informação secundária |

## Componentes normalizados

- KPI / `st.metric`
- alertas `success`, `warning`, `error`, `info`
- cards / containers
- insights
- tabelas / dataframes
- botões
- tabs
- inputs
- barras de progresso
- gráficos Streamlit
- sidebar
- login / cabeçalho de marca

## Instalação

Copiar para a pasta da aplicação:

- `ui/`
- `assets/`
- `.streamlit/config.toml`
- `apply_v3_3.py`

Depois:

```bash
cd /opt/family-finance/app
python apply_v3_3.py
```

Reiniciar o serviço:

```bash
sudo systemctl restart family-finance
```

Se o teu serviço tiver outro nome, usa o nome atualmente configurado.

## Segurança da atualização

`apply_v3_3.py` cria automaticamente:

`app_v3.2_backup.py`

antes de alterar o `app.py`.

A V3.3 é intencionalmente uma atualização visual: não altera `db.py`, tabelas SQL, autenticação, cálculos, OCR, inteligência de mercado ou lógica dos dashboards.
