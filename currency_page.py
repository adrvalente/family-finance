"""Family Finance V3.6 — página Streamlit do conversor de moedas."""
from decimal import InvalidOperation
import streamlit as st
from currency_converter import CurrencyError, converter
from currency_repository import guardar_taxa, obter_ultima_taxa

MOEDAS = ('EUR', 'USD', 'GBP', 'CHF', 'BRL', 'CAD', 'AUD', 'JPY', 'SEK', 'NOK', 'DKK', 'PLN')


def page_currency_converter():
    st.title('💱 Conversor de Moedas')
    st.caption('Family Finance V3.6 · Frankfurter API · Histórico Aiven MySQL')
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        valor = st.number_input('Montante', min_value=0.0, value=100.0, step=10.0, format='%.2f', key='fx_amount')
    with col2:
        origem = st.selectbox('Moeda de origem', MOEDAS, key='fx_from')
    with col3:
        destino = st.selectbox('Moeda de destino', MOEDAS, index=1, key='fx_to')

    if st.button('Converter', type='primary', use_container_width=True):
        try:
            resultado = converter(str(valor), origem, destino)
            st.session_state['fx_result'] = resultado
            st.session_state['fx_pair'] = (origem, destino)
            if origem != destino and resultado.get('date'):
                try:
                    guardar_taxa(resultado)
                    st.session_state['fx_save_status'] = 'Cotação guardada no Aiven.'
                except Exception:
                    st.session_state['fx_save_status'] = 'Conversão concluída, mas não foi possível guardar a cotação no Aiven.'
            else:
                st.session_state['fx_save_status'] = 'Conversão entre moedas iguais; não é necessário guardar uma cotação.'
        except (CurrencyError, ValueError, InvalidOperation) as exc:
            st.session_state.pop('fx_result', None)
            st.error(f'Não foi possível converter: {exc}')

    result = st.session_state.get('fx_result')
    if result and st.session_state.get('fx_pair') == (origem, destino):
        st.metric('Valor convertido', f"{result['valor_convertido']:,.2f} {destino}")
        st.caption(f"Taxa: 1 {origem} = {result['rate']} {destino} · Data: {result.get('date') or 'não aplicável'}")
        st.info(st.session_state.get('fx_save_status', ''))

    st.divider()
    st.subheader('Última cotação guardada')
    if st.button('Consultar no Aiven', key='fx_lookup'):
        try:
            registo = obter_ultima_taxa(origem, destino)
            if registo:
                st.success(f"1 {origem} = {registo['taxa']} {destino} · {registo['data_cotacao']} · {registo['fonte']}")
            else:
                st.info('Ainda não existe uma cotação guardada para este par.')
        except Exception:
            st.warning('Não foi possível consultar o histórico no Aiven. Confirma a ligação à base de dados.')
