"""Configuração de unidades, ESBs e ESFs — apenas para o admin."""

import sqlite3
from login.envia_email import enviar_email_ativacao
import pandas as pd
import streamlit as st

DB = "indicadores.db"

def _con():
    return sqlite3.connect(DB)

# Modal de confirmação
@st.dialog("🗑️ Confirmar exclusão")
def confirmar_exclusao(tipo: str, nome: str, id_registro: int, apagar_esfs: bool = False):
    """Modal de confirmação de exclusão (tipo: 'ESB' ou 'ESF')."""
    st.write(f"Excluir {tipo} **{nome}**?")
    if apagar_esfs:
        st.warning("As ESFs vinculadas a esta ESB também serão excluídas.")

    confirmou = st.text_input(f"Digite '{nome}' para confirmar")
    if st.button("🗑️ Confirmar", type="primary"):
        if confirmou.strip().upper() == nome.strip().upper():
            with _con() as con:
                if tipo == "ESB":
                    if apagar_esfs:
                        con.execute("DELETE FROM esf WHERE esb_id = ?", (id_registro,))
                    con.execute("DELETE FROM esb WHERE id = ?", (id_registro,))
                else:
                    con.execute("DELETE FROM esf WHERE id = ?", (id_registro,))
            st.rerun(scope="app")   # fecha o modal e atualiza a página toda
        else:
            st.error("A confirmação não confere com o nome.")

def tela_configuracao():
    if st.session_state.usuario.get("perfil") != "area":
        st.error("Acesso restrito ao administrador.")
        st.stop()

    aba_u, aba_e, aba_g, aba_us = st.tabs(["Unidades", "ESBs", "ESFs", "Usuários"])

    # ---------- UNIDADES ----------
    with aba_u:
        with _con() as con:
            unidades = pd.read_sql("SELECT * FROM unidades ORDER BY nome", con)
        st.dataframe(unidades, use_container_width=True, hide_index=True)

        with st.form("nova_unidade", clear_on_submit=True):
            nome = st.text_input("Nova unidade")
            if st.form_submit_button("Adicionar") and nome.strip():
                with _con() as con:
                    con.execute("INSERT OR IGNORE INTO unidades (nome) VALUES (?)",
                                (nome.strip().upper(),))
                st.rerun()

        # excluir
        with st.form("excluir_unidade"):
            alvo = st.selectbox("Excluir unidade", unidades["nome"] if not unidades.empty else [])
            if st.form_submit_button("🗑️ Excluir") and alvo:
                with _con() as con:
                    con.execute("DELETE FROM esf WHERE esb_id IN "
                                "(SELECT id FROM esb WHERE unidade_id = "
                                "(SELECT id FROM unidades WHERE nome = ?))", (alvo,))
                    con.execute("DELETE FROM esb WHERE unidade_id = "
                                "(SELECT id FROM unidades WHERE nome = ?)", (alvo,))
                    con.execute("DELETE FROM unidades WHERE nome = ?", (alvo,))
                st.rerun()

    # ---------- ESBs ----------
    with aba_e:
        st.subheader("Equipes de Saúde Bucal")
        with _con() as con:
            esbs = pd.read_sql(
                """SELECT e.id, e.nome AS esb, u.nome AS unidade
                   FROM esb e
                            JOIN unidades u ON u.id = e.unidade_id
                   ORDER BY u.nome, e.nome""", con)
            unidades = pd.read_sql("SELECT id, nome FROM unidades ORDER BY nome", con)
        st.dataframe(esbs[["esb", "unidade"]], use_container_width=True, hide_index=True)

        # ----- NOVA ESB -----
        with st.form("nova_esb", clear_on_submit=True):
            nome = st.text_input("Nova ESB")
            unid = st.selectbox("Unidade", unidades["nome"], key="esb_unid_nova")
            if st.form_submit_button("Adicionar") and nome.strip():
                unid_id = int(unidades.loc[unidades["nome"] == unid, "id"].iloc[0])
                with _con() as con:
                    con.execute("INSERT OR IGNORE INTO esb (nome, unidade_id) VALUES (?, ?)",
                                (nome.strip().upper(), unid_id))
                st.rerun()

        # ----- ALTERAR (nome e/ou unidade) -----
        if not esbs.empty:
            with st.form("alterar_esb"):
                st.write("**Alterar ESB**")
                esb_alvo = st.selectbox("ESB a alterar", esbs["esb"], key="esb_alterar")
                novo_nome = st.text_input("Novo nome (deixe vazio para manter)")
                nova_unid = st.selectbox("Nova unidade",
                                         ["(manter)"] + unidades["nome"].tolist())
                if st.form_submit_button("✏️ Salvar alterações"):
                    id_alvo = int(esbs.loc[esbs["esb"] == esb_alvo, "id"].iloc[0])
                    novo = novo_nome.strip().upper() if novo_nome.strip() else esb_alvo
                    novo_unid_id = (
                        int(unidades.loc[unidades["nome"] == nova_unid, "id"].iloc[0])
                        if nova_unid != "(manter)"
                        else int(esbs.loc[esbs["esb"] == esb_alvo, "unidade_id"].iloc[0])
                    )
                    try:
                        with _con() as con:
                            con.execute(
                                "UPDATE esb SET nome = ?, unidade_id = ? WHERE id = ?",
                                (novo, novo_unid_id, id_alvo))
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Já existe uma ESB com este nome.")

            # ----- EXCLUIR ESB -----
            esb_del = st.selectbox("ESB a excluir", esbs["esb"].tolist(),
                                   key="esb_excluir")
            id_esb = int(esbs.loc[esbs["esb"] == esb_del, "id"].iloc[0])
            with _con() as con:
                tem_esf = con.execute(
                    "SELECT 1 FROM esf WHERE esb_id = ?", (id_esb,)).fetchone()
            if st.button("🗑️ Excluir ESB"):
                confirmar_exclusao("ESB", esb_del, id_esb, apagar_esfs=bool(tem_esf))

    # ---------- ESFs ----------
    with aba_g:
        st.subheader("ESFs (composição das ESBs)")
        with _con() as con:
            esf_list = pd.read_sql(
                """SELECT g.id,
                          g.esb_id,
                          g.nome AS esf,
                          e.nome AS esb,
                          u.nome AS unidade
                   FROM esf g
                            JOIN esb e ON e.id = g.esb_id
                            JOIN unidades u ON u.id = e.unidade_id
                   ORDER BY u.nome, e.nome, g.nome""", con)
            esbs = pd.read_sql("SELECT id, nome FROM esb ORDER BY nome", con)
        st.dataframe(esf_list[["esf", "esb", "unidade"]],
                     use_container_width=True, hide_index=True)

        # ----- NOVA ESF -----
        with st.form("nova_esf", clear_on_submit=True):
            nome = st.text_input("Nova ESF (nome EXATO como aparece na planilha)")
            esb = st.selectbox("Pertence à ESB", esbs["nome"], key="esf_esb_nova")
            if st.form_submit_button("Adicionar") and nome.strip():
                esb_id = int(esbs.loc[esbs["nome"] == esb, "id"].iloc[0])
                with _con() as con:
                    con.execute("INSERT OR IGNORE INTO esf (nome, esb_id) VALUES (?, ?)",
                                (nome.strip().upper(), esb_id))
                st.rerun()

        # ----- ALTERAR (mover de ESB / renomear) — a mudança de composição -----
        if not esf_list.empty:
            with st.form("alterar_esf"):
                st.write("**Alterar composição**")
                esf_alvo = st.selectbox("ESF a alterar", esf_list["esf"], key="esf_alterar")
                nova_esb = st.selectbox("Mover para a ESB",
                                        ["(manter)"] + esbs["nome"].tolist())
                novo_nome = st.text_input("Novo nome (deixe vazio para manter)")
                if st.form_submit_button("✏️ Salvar"):
                    id_alvo = int(esf_list.loc[esf_list["esf"] == esf_alvo, "id"].iloc[0])
                    esb_atual = esf_list.loc[esf_list["esf"] == esf_alvo, "esb"].iloc[0]
                    novo_esb_id = (
                        int(esbs.loc[esbs["nome"] == nova_esb, "id"].iloc[0])
                        if nova_esb != "(manter)"
                        else int(esf_list.loc[esf_list["esf"] == esf_alvo, "esb_id"].iloc[0])
                    )
                    novo = novo_nome.strip().upper() if novo_nome.strip() else esf_alvo
                    try:
                        with _con() as con:
                            con.execute("UPDATE esf SET nome = ?, esb_id = ? WHERE id = ?",
                                        (novo, novo_esb_id, id_alvo))
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Já existe uma ESF com este nome.")

            # ----- EXCLUIR ESF -----
            esf_del = st.selectbox("ESF a excluir", esf_list["esf"].tolist(),
                                   key="esf_excluir")
            if st.button("🗑️ Excluir ESF"):
                id_del = int(esf_list.loc[esf_list["esf"] == esf_del, "id"].iloc[0])
                confirmar_exclusao("ESF", esf_del, id_del)
    with aba_us:
        st.subheader("Aguardando ativação")
        with _con() as con:
            pendentes = pd.read_sql(
                """SELECT us.email, COALESCE(u.nome, '—') AS unidade
                   FROM usuarios us LEFT JOIN unidades u ON u.id = us.unidade_id
                   WHERE us.ativo = 0 ORDER BY us.id""", con)
            ativos = pd.read_sql(
                """SELECT us.email, COALESCE(u.nome, '—') AS unidade, us.perfil
                   FROM usuarios us LEFT JOIN unidades u ON u.id = us.unidade_id
                   WHERE us.ativo = 1 ORDER BY us.email""", con)

        if pendentes.empty:
            st.write("Nenhum cadastro pendente.")
        else:
            st.dataframe(pendentes, use_container_width=True, hide_index=True)
            with st.form("ativar_usuario"):
                alvo = st.selectbox("Ativar e-mail", pendentes["email"])
                if st.form_submit_button("✅ Ativar e enviar e-mail"):
                    with _con() as con:
                        con.execute("UPDATE usuarios SET ativo = 1 WHERE email = ?", (alvo,))
                    try:
                        enviar_email_ativacao(alvo)
                        st.success(f"{alvo} ativado. E-mail de aviso enviado.")
                    except Exception as e:
                        st.warning(f"{alvo} ativado, mas o envio do e-mail falhou: {e}")

        st.subheader("Usuários ativos")
        st.dataframe(ativos, use_container_width=True, hide_index=True)