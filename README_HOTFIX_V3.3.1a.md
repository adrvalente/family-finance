# Family Finance V3.3.1a — Hotfix

Corrige o erro:

`NameError: name 'render_brand_header' is not defined`

## O que foi corrigido
- `ui/theme.py`: volta a incluir `render_brand_header()`
- `ui/__init__.py`: exporta `render_brand_header`
- `apply_v3_3_1.py`: import corrigido
- `apply_hotfix_v3_3_1a.py`: corrige diretamente o `app.py` já atualizado

## Aplicar
Copiar estes ficheiros para `/opt/family-finance/app` e executar:

```bash
cd /opt/family-finance/app
python apply_hotfix_v3_3_1a.py
sudo systemctl restart family-finance
```

Depois fazer `Ctrl + F5`.

O hotfix cria `app_v3.3.1_before_hotfix.py` antes de alterar o `app.py`.
