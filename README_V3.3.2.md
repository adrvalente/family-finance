# Family Finance V3.3.2 — Header Fix

Corrige a V3.3.1 que ocultava controlos nativos do Streamlit.

Restaurado:
- botão para expandir/recolher a sidebar;
- botão Deploy;
- menu nativo do Streamlit;
- header com fundo claro integrado na identidade Family Finance.

## Aplicar

Copia o conteúdo do pacote para `/opt/family-finance/app`.

Depois:

```bash
cd /opt/family-finance/app
python apply_header_fix_v3_3_2.py
sudo systemctl restart family-finance
```

Depois faz `Ctrl + F5`.

O script cria `ui/theme_v3.3.1_before_header_fix.py` antes da alteração.
