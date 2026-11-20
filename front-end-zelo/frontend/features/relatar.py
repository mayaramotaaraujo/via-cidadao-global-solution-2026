"""Tela principal do cidadão: relatar -> IA analisa -> cidadão confirma/corrige -> protocolo.

Fluxo em 3 etapas controlado por state/sessao.py:
  FORMULARIO  -> entrada validada antes do envio
  REVISAO     -> human-in-the-loop: a IA sugere, o cidadão decide
  CONCLUIDO   -> protocolo + orientações + avaliação
"""

import html
import time

import streamlit as st

from providers.api_client import ErroAPI, carregar_bairros, carregar_relatos_publicos, obter_cliente
from state import sessao
from ui.componentes import badge_urgencia, botao_ouvir, dados, etapas, mostrar_erro, placa_protocolo
from ui.rotulos import CATEGORIAS, ORDEM_URGENCIA, rotulo_categoria, rotulo_urgencia

MIN_CARACTERES, MAX_CARACTERES, MAX_REFERENCIA = 20, 1000, 150

EXEMPLOS = {
    "Poste apagado": (
        "O poste da esquina está apagado há uma semana e a rua fica totalmente escura. "
        "Muita gente passa a pé à noite voltando do metrô.",
        "Tatuapé",
        "Saída do metrô Carrão",
    ),
    "Calçada sem rampa": (
        "A calçada em frente à UBS está toda quebrada e sem rampa. Minha mãe é cadeirante e "
        "precisa ir pela rua no meio dos carros para chegar na consulta.",
        "Capão Redondo",
        "Em frente à UBS",
    ),
    "Bueiro entupido": (
        "A boca de lobo da rua está entupida de lixo e toda vez que chove a água entra nas casas.",
        "Jardim Ângela",
        "",
    ),
}


def validar_entrada(descricao: str, bairro: str | None, referencia: str, consentiu: bool) -> dict[str, str]:
    """Validação no front-end, ANTES de gastar uma chamada à IA.
    (O back-end valida de novo com Pydantic: nunca confiamos só no cliente.)"""
    erros: dict[str, str] = {}
    texto = descricao.strip()
    if not texto:
        erros["Descrição"] = "Descreva o que está acontecendo."
    elif len(texto) < MIN_CARACTERES or len(texto.split()) < 4:
        erros["Descrição"] = f"Escreva pelo menos {MIN_CARACTERES} caracteres e 4 palavras."
    elif len(texto) > MAX_CARACTERES:
        erros["Descrição"] = f"Reduza o texto para até {MAX_CARACTERES} caracteres."
    if not bairro:
        erros["Bairro"] = "Escolha o bairro onde está o problema."
    if len(referencia.strip()) > MAX_REFERENCIA:
        erros["Ponto de referência"] = f"Use até {MAX_REFERENCIA} caracteres."
    if not consentiu:
        erros["Privacidade"] = "Marque a caixa de concordância para enviar o relato."
    return erros


# ---------------------------------------------------------------- etapa 1
def _formulario() -> None:
    etapas(0)
    try:
        with st.spinner("Conectando ao serviço. Na primeira visita isso pode levar até 1 minuto."):
            bairros = [b["nome"] for b in carregar_bairros()]
    except ErroAPI as e:
        mostrar_erro(e, "A lista de bairros é necessária para registrar o relato.")
        if st.button("Tentar de novo", key="retry_bairros"):
            carregar_bairros.clear()
            st.rerun()
        return

    with st.expander("Ver exemplos de relato"):
        st.caption("Escolha um exemplo para preencher o formulário.")
        cols = st.columns(len(EXEMPLOS))
        for col, (nome, valores) in zip(cols, EXEMPLOS.items()):
            col.button(nome, key=f"ex_{nome}", on_click=sessao.preencher_exemplo, args=valores, width="stretch")

    with st.form("form_relato", clear_on_submit=False, enter_to_submit=False, border=False):
        descricao = st.text_area(
            "Descreva o problema *",
            key="campo_descricao",
            max_chars=MAX_CARACTERES,
            height=150,
            placeholder="Por exemplo: há um buraco grande na rua em frente à escola e os carros desviam pela calçada.",
            help="Diga o que é, há quanto tempo está assim e se oferece perigo.",
        )
        c1, c2 = st.columns(2)
        bairro = c1.selectbox(
            "Bairro *", bairros, key="campo_bairro", index=None, placeholder="Escolha o bairro",
            help="Usado para encaminhar o pedido e consultar a previsão de chuva da região.",
        )
        referencia = c2.text_input(
            "Ponto de referência", key="campo_referencia", max_chars=MAX_REFERENCIA,
            placeholder="Por exemplo: em frente à padaria", help="Opcional. Não informe seu endereço residencial.",
        )
        consentiu = st.checkbox(
            "Concordo que o relato seja analisado por inteligência artificial. Telefone, CPF, e-mail e "
            "placas de veículo são removidos do texto antes da análise.",
            key="campo_consentimento",
        )
        st.caption("Campos com * são obrigatórios.")
        enviado = st.form_submit_button("Analisar relato", type="primary")

    if not enviado:
        return

    erros = validar_entrada(descricao, bairro, referencia, consentiu)
    if erros:
        st.error(
            "**Revise os campos abaixo para continuar.**\n\n" + "\n".join(f"- **{c}**: {m}" for c, m in erros.items()),
            icon=":material/edit_note:",
        )
        return

    entrada = {"descricao": descricao.strip(), "bairro": bairro, "referencia": referencia.strip() or None}
    inicio = time.perf_counter()
    # Design para latência: o cidadão vê o que está acontecendo durante a espera.
    with st.status("Analisando o relato. Isso leva alguns segundos.", expanded=True) as status:
        st.write("Removendo dados pessoais do texto")
        st.write("Consultando a previsão de chuva do bairro")
        st.write("Classificando o tipo e a urgência do problema")
        try:
            analise = obter_cliente().analisar(**entrada)
        except ErroAPI as e:
            status.update(label="A análise não foi concluída", state="error", expanded=False)
            mostrar_erro(e, "O texto continua no formulário para você tentar de novo.")
            return
        status.update(label=f"Análise concluída em {time.perf_counter() - inicio:.1f} s", state="complete", expanded=False)

    sessao.iniciar_revisao(entrada, analise)
    st.rerun()


# ---------------------------------------------------------------- etapa 2
def _revisao() -> None:
    etapas(1)
    analise, entrada = st.session_state.analise_atual, st.session_state.entrada_atual

    if analise["risco_imediato"]:
        st.error(
            "**Possível risco imediato.** Afaste-se do local. Se houver perigo agora, ligue para a "
            "Defesa Civil (199) ou para os Bombeiros (193).",
            icon=":material/warning:",
        )
    fora = analise["fora_do_escopo"]
    if fora:
        texto = (
            "Este serviço trata de problemas em ruas, calçadas e espaços públicos, e o relato parece ser de outro "
            "tipo, por isso não é possível gerar o protocolo aqui."
        )
        if analise["risco_imediato"]:
            texto += " Em emergências, ligue para a Polícia Militar (190), o SAMU (192) ou os Bombeiros (193)."
        else:
            texto += " Para esse assunto, ligue para o 156 ou acesse o site da Prefeitura (sp156.prefeitura.sp.gov.br)."
        st.warning(texto, icon=":material/info:")

    with st.container(border=True):
        st.markdown("#### Resultado da análise")
        st.markdown(f"{html.escape(analise['resumo'])}")
        campos = [
            ("Tipo de problema", html.escape(rotulo_categoria(analise["categoria"]))),
            ("Urgência", badge_urgencia(analise["urgencia"])),
            ("Órgão responsável", html.escape(analise["orgao_responsavel"])),
        ]
        if not fora:  # fora do escopo não tem reparo, então o prazo enganaria
            campos.append(("Prazo de referência", f"Até {analise['prazo_estimado_dias']} dia(s)"))
        dados(campos)
        st.markdown(f"**Motivo da urgência.** {html.escape(analise['justificativa_urgencia'])}")
        st.markdown("**O que fazer agora**" if fora else "**Orientações até o reparo**")
        for o in analise["orientacoes_cidadao"]:
            st.markdown(f"- {html.escape(o)}")

        notas = []
        if analise.get("dados_pessoais_removidos"):
            notas.append("Removemos do texto, por privacidade: " + ", ".join(analise["dados_pessoais_removidos"]) + ".")
        if analise.get("contexto_clima"):
            cl = analise["contexto_clima"]
            notas.append(f"Previsão de chuva hoje no bairro: {cl['chuva_prevista_mm']:.1f} mm, segundo o {cl['fonte']}.")
        notas.extend(analise.get("ajustes_por_regra", []))
        for n in notas:
            st.caption(n)

    if analise["precisa_revisao_humana"]:
        st.warning(
            "**Confira com atenção antes de confirmar.**\n\n"
            + "\n".join(f"- {html.escape(m)}" for m in analise["motivos_revisao"]),
            icon=":material/fact_check:",
        )

    # ------------------- human-in-the-loop ---------------------------------
    st.markdown("#### A análise está correta?")
    escolha = st.radio(
        "Confirme ou corrija antes de gerar o protocolo",
        ["Sim, está correta", "Quero corrigir"],
        horizontal=True,
        key="hitl_escolha",
        index=1 if analise["precisa_revisao_humana"] else 0,
        label_visibility="collapsed",
    )
    categoria_final, urgencia_final = analise["categoria"], analise["urgencia"]
    if escolha == "Quero corrigir":
        c1, c2 = st.columns(2)
        cats = list(CATEGORIAS)
        categoria_final = c1.selectbox(
            "Tipo de problema", cats, index=cats.index(analise["categoria"]), format_func=rotulo_categoria, key="hitl_cat"
        )
        urgencia_final = c2.selectbox(
            "Urgência", ORDEM_URGENCIA, index=ORDEM_URGENCIA.index(analise["urgencia"]), format_func=rotulo_urgencia,
            key="hitl_urg",
        )

    b1, b2, b3, _ = st.columns([1.4, 1, 1, 1.6])
    confirmar = b1.button(
        "Confirmar e gerar protocolo", type="primary", width="stretch", disabled=fora
    )
    b2.button("Editar relato", on_click=sessao.voltar_para_edicao, width="stretch")
    b3.button("Cancelar", on_click=sessao.novo_relato, width="stretch")
    if fora:
        st.caption(
            "O botão de confirmar está desativado porque este relato não é de zeladoria urbana. "
            "Se a análise errou, use Editar relato para ajustar o texto."
        )

    if confirmar:
        with st.spinner("Gerando o protocolo"):
            try:
                relato = obter_cliente().confirmar(analise["analise_id"], categoria_final, urgencia_final)
            except ErroAPI as e:
                mostrar_erro(e)
                return
        carregar_relatos_publicos.clear()  # painel precisa refletir o novo relato
        sessao.concluir(relato, analise)
        st.rerun()

    with st.expander("Texto enviado"):
        st.text(entrada["descricao"])


# ---------------------------------------------------------------- etapa 3
def _concluido() -> None:
    etapas(2)
    relato = st.session_state.relato_confirmado
    st.success("Protocolo gerado. O pedido foi encaminhado ao órgão responsável.", icon=":material/check_circle:")
    placa_protocolo(relato["protocolo"])
    st.caption("Guarde este número para acompanhar o atendimento na aba Meus protocolos.")
    dados([
        ("Tipo de problema", html.escape(rotulo_categoria(relato["categoria"]))),
        ("Urgência", badge_urgencia(relato["urgencia"])),
        ("Bairro", html.escape(relato["bairro"])),
        ("Órgão responsável", html.escape(relato["orgao_responsavel"])),
        ("Prazo de referência", f"Até {relato['prazo_estimado_dias']} dia(s)"),
    ])
    if relato.get("ia_corrigida"):
        st.caption("Você corrigiu a análise da IA. A correção fica registrada e ajuda a melhorar o sistema.")

    orientacoes = relato.get("orientacoes_cidadao", [])
    if orientacoes:
        st.markdown("**Orientações até o reparo**")
        for o in orientacoes:
            st.markdown(f"- {html.escape(o)}")
        botao_ouvir(" ".join(orientacoes))

    st.divider()
    avaliacao_ia(relato["protocolo"], chave="concluido")
    st.button("Registrar outro problema", on_click=sessao.novo_relato, type="primary")


def avaliacao_ia(protocolo: str, chave: str) -> None:
    """Segundo ponto de human-in-the-loop: o cidadão avalia a resposta da IA."""
    if sessao.feedback_de(protocolo):
        st.caption("Avaliação registrada.")
        return
    st.markdown("As orientações foram úteis?")
    valor = st.feedback("thumbs", key=f"fb_{chave}_{protocolo}")
    if valor is not None:
        avaliacao = "util" if valor == 1 else "incorreto"
        try:
            obter_cliente().enviar_feedback(protocolo, sessao.comprovante_de(protocolo), avaliacao)
            sessao.registrar_feedback(protocolo, avaliacao)
            carregar_relatos_publicos.clear()
            st.toast("Avaliação registrada.", icon=":material/check:")
        except ErroAPI as e:
            mostrar_erro(e)


def render() -> None:
    {sessao.FORMULARIO: _formulario, sessao.REVISAO: _revisao, sessao.CONCLUIDO: _concluido}[sessao.etapa()]()
