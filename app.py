"""Dashboard de Indicadores de Saúde Bucal — esqueleto Streamlit."""

import sqlite3
import unicodedata
from usuarios import hash_senha, senha_valida, verificar_senha
import pandas as pd
import plotly.express as px
import streamlit as st
from login.envia_email import enviar_email_redefinicao
from datetime import datetime, timedelta
import secrets
import io
from linhas_cuidado.base import (
    carregar_cadastro, carregar_dados, indicador_esb,
    indicador_mensal, normalizar_nome,
)
from linhas_cuidado.tabagismo.listagem import tela_listagem

from configuracao import tela_configuracao

DB = "indicadores.db"

# ----------------- LOGIN-----------------
if "usuario" not in st.session_state:
    aba_entrar, aba_cadastrar, aba_esqueci = st.tabs(
        ["🔐 Entrar", "🆕 Cadastrar", "❓ Esqueci a senha"]
    )

    # ---------- ENTRAR ----------
    with aba_entrar:
        with st.form("login"):
            st.title("Indicadores de Saúde Bucal")
            email = st.text_input("E-mail")
            senha = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar", type="primary"):
                with sqlite3.connect(DB) as con:
                    linha = con.execute(
                        """SELECT us.senha_hash, us.ativo, us.perfil,
                                  COALESCE(u.nome, '') AS unidade
                           FROM usuarios us
                           LEFT JOIN unidades u ON u.id = us.unidade_id
                           WHERE us.email = ?""",
                        (email.strip().lower(),),
                    ).fetchone()
                if not linha or not verificar_senha(senha, linha[0]):
                    st.error("E-mail ou senha inválidos.")
                elif not linha[1]:
                    st.info("Conta aguardando ativação pelo administrador.")
                else:
                    st.session_state.usuario = {"perfil": linha[2], "unidade": linha[3]}
                    st.session_state.usuario_login = email.strip().lower()
                    st.rerun()

    # ---------- CADASTRAR ----------
    with aba_cadastrar:
        with st.form("cadastro", clear_on_submit=True):
            st.subheader("Criar novo acesso")
            email_cad = st.text_input("E-mail", key="cad_email")
            senha_cad = st.text_input("Senha (mín. 8, letras e números)",
                                      type="password", key="cad_senha")
            confirma = st.text_input("Confirme a senha", type="password")
            with sqlite3.connect(DB) as con:
                unidades = pd.read_sql("SELECT nome FROM unidades ORDER BY nome", con)
            unidade = st.selectbox("Unidade", unidades["nome"])
            if st.form_submit_button("Enviar cadastro"):
                if "@" not in email_cad:
                    st.error("Informe um e-mail válido.")
                elif senha_cad != confirma:
                    st.error("As senhas não coincidem.")
                elif not (ok := senha_valida(senha_cad))[0]:
                    st.error(ok[1])
                else:
                    try:
                        with sqlite3.connect(DB) as con:
                            unid_id = con.execute(
                                "SELECT id FROM unidades WHERE nome = ?", (unidade,)
                            ).fetchone()[0]
                            con.execute(
                                "INSERT INTO usuarios (email, senha_hash, perfil, unidade_id, ativo) "
                                "VALUES (?, ?, 'unidade', ?, 0)",
                                (email_cad.strip().lower(), hash_senha(senha_cad), unid_id),
                            )
                        st.success("Cadastro enviado! Você receberá um e-mail quando o administrador ativar seu acesso.")
                    except sqlite3.IntegrityError:
                        st.error("Já existe um cadastro com este e-mail.")

    # ---------- ESQUECI A SENHA (2 etapas) ----------
    with aba_esqueci:
        st.subheader("Redefinir senha")

        if "etapa_esqueci" not in st.session_state:
            st.session_state.etapa_esqueci = 1

        if st.session_state.etapa_esqueci == 1:
            with st.form("pedir_codigo"):
                email_res = st.text_input("E-mail da conta")
                if st.form_submit_button("Receber código por e-mail"):
                    with sqlite3.connect(DB) as con:
                        existe = con.execute(
                            "SELECT 1 FROM usuarios WHERE email = ?",
                            (email_res.strip().lower(),),
                        ).fetchone()
                    if existe:
                        codigo = secrets.token_urlsafe(8)  # código curto, fácil de digitar
                        expira = (datetime.now() + timedelta(minutes=30)).isoformat()
                        with sqlite3.connect(DB) as con:
                            con.execute(
                                "INSERT INTO redefinicoes_senha (email, token, expira_em) VALUES (?, ?, ?)",
                                (email_res.strip().lower(), codigo, expira),
                            )
                        try:
                            enviar_email_redefinicao(email_res.strip().lower(), codigo)
                            st.info("Código enviado para o seu e-mail. Vale por 30 minutos.")
                        except Exception as e:
                            st.error(f"Falha ao enviar o e-mail: {e}")
                    # mensagem idêntica com ou sem conta: não revela quais e-mails existem
                    else:
                        st.info("Se este e-mail estiver cadastrado, você receberá o código.")
                    st.session_state.etapa_esqueci = 2
                    st.rerun()
        else:
            with st.form("usar_codigo"):
                codigo = st.text_input("Código recebido por e-mail")
                nova = st.text_input("Nova senha (mín. 8, letras e números)", type="password")
                nova_conf = st.text_input("Confirme a nova senha", type="password")
                if st.form_submit_button("Redefinir senha"):
                    if nova != nova_conf:
                        st.error("As senhas não coincidem.")
                    elif not (ok := senha_valida(nova))[0]:
                        st.error(ok[1])
                    else:
                        agora = datetime.now().isoformat()
                        with sqlite3.connect(DB) as con:
                            reg = con.execute(
                                """SELECT email, expira_em FROM redefinicoes_senha
                                   WHERE token = ? AND usado = 0 AND expira_em > ?
                                   ORDER BY id DESC LIMIT 1""",
                                (codigo.strip(), agora),
                            ).fetchone()
                        if not reg:
                            st.error("Código inválido, já usado ou expirado.")
                        else:
                            with sqlite3.connect(DB) as con:
                                con.execute(
                                    "UPDATE usuarios SET senha_hash = ? WHERE email = ?",
                                    (hash_senha(nova), reg[0]),
                                )
                                con.execute(
                                    "UPDATE redefinicoes_senha SET usado = 1 WHERE token = ?",
                                    (codigo.strip(),),
                                )
                            st.success("Senha redefinida! Use a aba Entrar.")
                            st.session_state.etapa_esqueci = 1
    st.stop()

# ----------------- DADOS -----------------
df = carregar_dados(1)  # indicador 1 = tabagismo
usuario = st.session_state.usuario

# escopo do usuário: área vê tudo; unidade vê só a dela
if usuario["perfil"] == "area":
    unidade = st.sidebar.selectbox(
        "Unidade",
        sorted(df[df["local_tipo"] == "unidade"]["local_nome"].unique()),
    )
else:
    unidade = usuario["unidade"]

meses = sorted(df["mes_ref"].unique())
mes_fim = st.sidebar.selectbox("Mês de referência", meses, index=len(meses) - 1)

# ----------------- A PARTIR DAQUI SÓ CHEGA QUEM LOGOU -----------------

st.sidebar.write(f"👤 {st.session_state.usuario_login} ({usuario['perfil']})")
if st.sidebar.button("Sair"):
    for chave in ("autenticado", "usuario", "usuario_login", "tela"):
        st.session_state.pop(chave, None)
    st.rerun()
if st.sidebar.button("🔑 Alterar senha"):
    st.session_state.tela = "senha"
    st.rerun()
if (usuario["perfil"] == "area"
        and st.session_state.get("tela") != "config"
        and st.sidebar.button("⚙️ Configuração")):
    st.session_state.tela = "config"
    st.rerun()

# ----------------- ROTEAMENTO: CONFIGURAÇÃO -----------------
tela = st.session_state.get("tela", "dashboard")
if st.session_state.get("tela") == "config":
    tela_configuracao()
    if st.button("← Voltar ao dashboard"):
        st.session_state.tela = "dashboard"
        st.rerun()
    st.stop()
if tela == "listagem":
    cadastro = carregar_cadastro()
    linhas_unid = cadastro[cadastro["unidade"].map(normalizar_nome)
                           == normalizar_nome(unidade)]
    tela_listagem(linhas_unid, mes_fim)
    if st.button("← Voltar ao dashboard"):
        st.session_state.tela = "dashboard"
        st.rerun()
    st.stop()
if st.session_state.get("tela") == "senha":
    st.title("🔑 Alterar minha senha")
    with st.form("troca_senha"):
        atual = st.text_input("Senha atual", type="password")
        nova = st.text_input("Nova senha (mín. 8, letras e números)", type="password")
        nova_conf = st.text_input("Confirme a nova senha", type="password")
        if st.form_submit_button("Salvar nova senha"):
            if nova != nova_conf:
                st.error("As senhas não coincidem.")
            elif not (ok := senha_valida(nova))[0]:
                st.error(ok[1])
            else:
                with sqlite3.connect(DB) as con:
                    hash_atual = con.execute(
                        "SELECT senha_hash FROM usuarios WHERE email = ?",
                        (st.session_state.usuario_login,),
                    ).fetchone()
                if not hash_atual or not verificar_senha(atual, hash_atual[0]):
                    st.error("Senha atual incorreta.")
                elif verificar_senha(nova, hash_atual[0]):
                    st.error("A nova senha não pode ser igual à atual.")
                else:
                    with sqlite3.connect(DB) as con:
                        con.execute(
                            "UPDATE usuarios SET senha_hash = ? WHERE email = ?",
                            (hash_senha(nova), st.session_state.usuario_login),
                        )
                    st.success("Senha alterada com sucesso!")
                if st.button("← Voltar"):
                    st.session_state.tela = "dashboard"
                    st.rerun()
    if st.button("← Voltar"):
        st.session_state.tela = "dashboard"
        st.rerun()
    st.stop()


# ----------------- DASHBOARD -----------------
st.title("📊 Acompanhamento de Pessoa Tabagista")


# KPIs do mês selecionado (com proteção para dados ausentes)
def kpi_do_mes(local_nome: str, tipo: str) -> dict | None:
    filtro = df[(df["local_nome"] == local_nome)
                & (df["local_tipo"] == tipo)
                & (df["mes_ref"] == mes_fim)]
    if filtro.empty:
        return None
    linha = filtro.iloc[0]
    return {
        "num": linha["numerador"],
        "den": linha["denominador"],
        "pct": linha["numerador"] / max(linha["denominador"], 1) * 100,
    }

area_nome = df[df["local_tipo"] == "area"]["local_nome"].iloc[0]

kpi_area = kpi_do_mes(area_nome, "area")
kpi_unid = kpi_do_mes(unidade, "unidade")

c1, c2 = st.columns(2)
if kpi_area:
    c1.metric("Área AP 2.2", f"{kpi_area['num']}/{kpi_area['den']}", f"{kpi_area['pct']:.1f}%")
else:
    c1.metric("Área AP 2.2", "sem dados", f"mês {mes_fim}")

if kpi_unid:
    c2.metric(unidade, f"{kpi_unid['num']}/{kpi_unid['den']}", f"{kpi_unid['pct']:.1f}%")
else:
    c2.metric(unidade, "sem dados", f"mês {mes_fim}")

# ESBs da unidade, via cadastro (tela ⚙️)
with sqlite3.connect(DB) as con:
    cadastro = carregar_cadastro()
    unid_norm = normalizar_nome(unidade)
    linhas_unid = cadastro[cadastro["unidade"].map(normalizar_nome) == unid_norm]
    esbs_da_unidade = sorted(linhas_unid["esb"].unique()) if not linhas_unid.empty else []

# resolve o nome EXATO da unidade no banco (casamento por contenção)
nomes_unid_banco = df[df["local_tipo"] == "unidade"]["local_nome"].unique()
unidade_db = next(
    (n for n in nomes_unid_banco
     if normalizar_nome(n) == unid_norm
     or unid_norm in normalizar_nome(n)
     or normalizar_nome(n) in unid_norm),
    None,
)
if unidade_db is None:
    st.warning(f"Unidade '{unidade}' não encontrada nos dados importados.")
    st.stop()
if linhas_unid.empty:
    st.warning(f"Unidade '{unidade}' sem ESBs cadastradas. Cadastre em ⚙️ Configuração.")
    esbs_da_unidade = []
else:
    esbs_da_unidade = sorted(linhas_unid["esb"].unique())
kpi_unid = kpi_do_mes(unidade_db, "unidade")

# Gráfico comparativo: unidade vs área vs ESBs da unidade
serie_unid = indicador_mensal(df, unidade_db).assign(local=unidade_db)
serie_area = indicador_mensal(df, area_nome).assign(local="AP 2.2 (área)")
serie_eq = [indicador_esb(df, esb).assign(local=esb) for esb in esbs_da_unidade]
comparativo = pd.concat([serie_unid, serie_area] + serie_eq)

fig = px.line(
    comparativo, x="mes_ref", y="percentual", color="local", markers=True,
    labels={"mes_ref": "Mês", "percentual": "% atendidos", "local": ""},
    title="Tabagismo — % atendidos pela SB (últimos 12 meses)",
)
if not esbs_da_unidade:
    st.warning(f"Nenhuma ESB encontrada para {unidade} em {mes_fim}.")
st.plotly_chart(fig, use_container_width=True)

# Tabela do mês por ESB
st.subheader(f"Indicador por ESB — {mes_fim}")
if esbs_da_unidade:
    linhas_tabela = []
    for esb in esbs_da_unidade:
        serie = indicador_esb(df, esb)
        mes = serie[serie["mes_ref"] == mes_fim]
        if not mes.empty:
            linhas_tabela.append({
                "ESB": esb,
                "Numerador": int(mes["numerador"].iloc[0]),
                "Denominador": int(mes["denominador"].iloc[0]),
                "%": float(mes["percentual"].iloc[0]),
            })
    if linhas_tabela:
        tabela_esb = pd.DataFrame(linhas_tabela)
        st.dataframe(tabela_esb, use_container_width=True, hide_index=True)
    else:
        st.warning(f"Sem dados de {unidade} em {mes_fim}.")
else:
    st.warning(f"Unidade '{unidade}' sem ESBs cadastradas. Cadastre em ⚙️ Configuração.")
# ----------------- LISTAGEM DE PACIENTES -----------------
st.divider()
if st.button("👥 Listagem de pacientes tabagistas", type="primary"):
    st.session_state.tela = "listagem"
    st.rerun()
