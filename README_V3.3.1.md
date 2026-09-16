# Family Finance V3.3.1

Correções visuais:
- remove a barra preta superior do Streamlit;
- aumenta e clarifica a marca na sidebar;
- reduz os valores demasiado grandes nos KPI;
- evita truncagem do estado;
- cria cards próprios para o Family Financial Score;
- cria cards compactos para os Componentes do score;
- troca o gráfico escuro `st.bar_chart()` por Altair em fundo claro;
- mantém toda a lógica financeira e base de dados.

## Instalar

Copiar o conteúdo deste pacote para:

`/opt/family-finance/app`

Depois:

```bash
cd /opt/family-finance/app
python apply_v3_3_1.py
sudo systemctl restart family-finance
```

O script cria `app_v3.3_backup.py` antes de alterar o `app.py`.

Se o serviço tiver outro nome, usa o nome real do serviço.
