import streamlit as st
import json
import os
import io
import PyPDF2
import docx
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from google import genai
from google.genai import types

# 1. CONFIGURAÇÃO DA PÁGINA E ESTILIZAÇÃO DASHBOARD
st.set_page_config(
    page_title="M.A - Plataforma de Inteligência Jurídica",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS PROFISSIONAL INSPIRADO NO DASHBOARD EXECUTIVO
st.markdown("""
    <style>
    /* Fundo geral do sistema */
    .stApp { background-color: #f0f2f6; }
    
    /* Barra lateral estilo Conciliare */
    [data-testid="stSidebar"] {
        background-color: #0a0e1a !important;
        border-right: 1px solid #1e293b;
    }
    [data-testid="stSidebar"] * { color: #ffffff !important; }
    
    /* Títulos e Tipografia */
    h1, h2, h3 { 
        color: #1e293b !important; 
        font-family: 'Inter', sans-serif; 
        font-weight: 700; 
        letter-spacing: -0.5px;
    }
    
    /* Cartões de Indicadores (KPIs) */
    .kpi-card {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border: 1px solid #e2e8f0;
        text-align: left;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .kpi-title { color: #64748b; font-size: 0.8rem; font-weight: 600; text-transform: uppercase; }
    .kpi-value { color: #1e293b; font-size: 1.8rem; font-weight: 700; margin: 5px 0; }
    
    /* Área Principal de Trabalho (Cards Brancos) */
    .main-card {
        background-color: #ffffff;
        padding: 30px;
        border-radius: 16px;
        box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);
        border: 1px solid #e2e8f0;
        margin-bottom: 25px;
    }
    
    /* Botões Estilo Executivo */
    .stButton>button {
        background: #2563eb;
        color: white !important;
        border-radius: 8px;
        padding: 12px 24px;
        font-weight: 600;
        border: none;
        width: 100%;
        transition: all 0.2s ease;
    }
    .stButton>button:hover { 
        background: #1d4ed8; 
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
    }
    
    /* Estilo das Abas de Resultados */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #f8fafc;
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
        font-weight: 600;
        color: #64748b;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2563eb !important;
        color: white !important;
    }
    
    /* Inputs */
    .stTextArea textarea {
        border-radius: 10px !important;
        border: 1px solid #e2e8f0 !important;
        background-color: #f8fafc !important;
    }
    </style>
""", unsafe_allow_html=True)

# 2. GERENCIAMENTO DE CONFIGURAÇÕES
ARQUIVO_CONFIG = "config_ma.json"

def carregar_config():
    if os.path.exists(ARQUIVO_CONFIG):
        with open(ARQUIVO_CONFIG, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"api_key": "", "advogado_nome": "", "advogado_oab": "", "advogado_endereco": ""}

def salvar_config(dados):
    with open(ARQUIVO_CONFIG, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4)

if "config" not in st.session_state:
    st.session_state.config = carregar_config()

# Funções auxiliares
def extrair_texto_pdf(arquivo_pdf):
    texto = ""
    try:
        leitor = PyPDF2.PdfReader(arquivo_pdf)
        for pagina in leitor.pages:
            texto += pagina.extract_text() + "\n"
    except Exception as e:
        st.error(f"Erro ao ler o PDF: {e}")
    return texto

def gerar_docx(texto_peca, dados_advogado):
    doc = docx.Document()
    if dados_advogado['advogado_nome']:
        header = doc.add_paragraph()
        header.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_nome = header.add_run(dados_advogado['advogado_nome'].upper())
        run_nome.bold = True
        run_nome.font.size = Pt(14)
        info = doc.add_paragraph()
        info.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_info = info.add_run(f"OAB: {dados_advogado['advogado_oab']} | {dados_advogado['advogado_endereco']}")
        run_info.font.size = Pt(9)
        run_info.italic = True
        doc.add_paragraph("_" * 60).alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph("\n")
    estilo = doc.styles['Normal']
    fonte = estilo.font
    fonte.name = 'Arial'
    fonte.size = Pt(12)
    paragrafos = texto_peca.split('\n')
    for p in paragrafos:
        if p.strip():
            para = doc.add_paragraph(p.strip())
            para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

def realizar_pesquisa_processual(fatos_do_caso: str, texto_documentos: str, area_direito: str, api_key: str) -> dict:
    try:
        cliente = genai.Client(api_key=api_key)
        instrucoes_sistema = f"""
        Você é um advogado sênior especialista em {area_direito} no Brasil.
        Sua missão é realizar pesquisa jurídica e redigir peças.
        Responda em JSON: resumo_estrategico, base_legal[], jurisprudencia[], doutrina[], peca_processual.
        """
        prompt_completo = f"{instrucoes_sistema}\n\n"
        if texto_documentos.strip():
            prompt_completo += f"DOCUMENTOS: {texto_documentos}\n"
        prompt_completo += f"PEDIDO: {fatos_do_caso}"

        resposta = cliente.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt_completo,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
                tools=[{"google_search": {}}]
            )
        )
        return json.loads(resposta.text)
    except Exception as e:
        return {"erro": str(e)}

# --- BARRA LATERAL (ESTILO EXECUTIVO) ---
with st.sidebar:
    st.markdown("### 🏢 Profissional")
    st.caption(f"Olá, {st.session_state.config['advogado_nome'] or 'Advogado'}")
    
    st.divider()
    
    # Simulação de Menu de Dashboard
    st.markdown("#### 🧭 Navegação")
    menu = st.radio("Ir para:", [
        "📊 Dashboard Executivo",
        "⚖️ Criação de Peças (IA)",
        "📅 Agenda",
        "👥 Clientes",
        "⚙️ Configurações"
    ], label_visibility="collapsed")
    
    st.divider()
    
    if menu == "⚙️ Configurações":
        st.markdown("#### 🔧 Ajustes")
        api_key_input = st.text_input("Chave Gemini:", value=st.session_state.config["api_key"], type="password")
        nome_adv = st.text_input("Nome:", value=st.session_state.config["advogado_nome"])
        oab_adv = st.text_input("OAB:", value=st.session_state.config["advogado_oab"])
        end_adv = st.text_area("Contatos:", value=st.session_state.config["advogado_endereco"], height=70)
        if st.button("💾 Guardar"):
            st.session_state.config = {"api_key": api_key_input, "advogado_nome": nome_adv, "advogado_oab": oab_adv, "advogado_endereco": end_adv}
            salvar_config(st.session_state.config)
            st.rerun()

# --- ÁREA PRINCIPAL ---
if menu == "📊 Dashboard Executivo":
    st.markdown("<h1>Dashboard Executivo</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #64748b;'>Visão geral do escritório em tempo real</p>", unsafe_allow_html=True)
    
    # Row de KPIs
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown("""<div class="kpi-card"><div><div class="kpi-title">Tarefas Pendentes</div><div class="kpi-value">12</div></div><div style="font-size: 2rem;">📝</div></div>""", unsafe_allow_html=True)
    with c2:
        st.markdown("""<div class="kpi-card"><div><div class="kpi-title">Processos Ativos</div><div class="kpi-value">48</div></div><div style="font-size: 2rem;">⚖️</div></div>""", unsafe_allow_html=True)
    with c3:
        st.markdown("""<div class="kpi-card"><div><div class="kpi-title">Petições p/ Revisar</div><div class="kpi-value">5</div></div><div style="font-size: 2rem;">📄</div></div>""", unsafe_allow_html=True)
    with c4:
        st.markdown("""<div class="kpi-card"><div><div class="kpi-title">Eventos Hoje</div><div class="kpi-value">3</div></div><div style="font-size: 2rem;">📅</div></div>""", unsafe_allow_html=True)
        
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
        <div class="main-card">
            <h3>Bem-vindo ao M.A Jurídico</h3>
            <p style='color: #64748b;'>Selecione <b>'Criação de Peças'</b> no menu lateral para iniciar uma nova análise processual com inteligência artificial ancorada em dados reais.</p>
        </div>
    """, unsafe_allow_html=True)

elif menu == "⚖️ Criação de Peças (IA)":
    st.markdown("<h1>⚖️ Criação de Peças Processuais</h1>", unsafe_allow_html=True)
    
    with st.container():
        st.markdown('<div class="main-card">', unsafe_allow_html=True)
        
        area_selecionada = st.selectbox("Selecione a área do Direito:", ["Direito Civil, Imobiliário e Consumidor", "Direito de Família e Sucessões", "Direito Penal", "Direito Previdenciário", "Trabalhista"])
        
        st.markdown("#### 📁 Instrução e Documentação")
        arquivos_anexados = st.file_uploader("Opcional: Arraste PDFs do processo para análise documental", type=["pdf"], accept_multiple_files=True)
        
        fatos_input = st.text_area(
            "📝 Detalhe o caso ou dê instruções específicas:", 
            height=200, 
            placeholder="Ex: Réplica à contestação alegando prescrição em caso de atraso de obra..."
        )
        
        if st.button("Executar Inteligência Estratégica"):
            if not st.session_state.config["api_key"]:
                st.error("Configure a sua chave de API nas definições.")
            else:
                with st.spinner('A processar análise jurídica avançada...'):
                    texto_extraido = ""
                    if arquivos_anexados:
                        for arq in arquivos_anexados:
                            texto_extraido += f"\n--- {arq.name} ---\n{extrair_texto_pdf(arq)}"
                    
                    resultado = realizar_pesquisa_processual(fatos_input, texto_extraido, area_selecionada, st.session_state.config["api_key"])
                    
                    if "erro" in resultado:
                        st.error(f"Erro: {resultado['erro']}")
                    else:
                        st.session_state.ultimo_resultado = resultado
        
        st.markdown('</div>', unsafe_allow_html=True)

    # Resultados
    if "ultimo_resultado" in st.session_state:
        res = st.session_state.ultimo_resultado
        st.markdown('<div class="main-card">', unsafe_allow_html=True)
        st.markdown(f"### 📌 Tese Estratégica\n{res.get('resumo_estrategico', '')}")
        
        t1, t2, t3, t4 = st.tabs(["⚖️ Fundamentação", "🏛️ Jurisprudência", "📚 Doutrina", "📄 Peça Final"])
        
        with t1:
            for i in res.get("base_legal", []): st.info(i)
        with t2:
            for i in res.get("jurisprudencia", []): st.warning(i)
        with t3:
            for i in res.get("doutrina", []): st.success(i)
        with t4:
            peca = res.get("peca_processual", "")
            st.text_area("Minuta:", peca, height=400)
            docx_buffer = gerar_docx(peca, st.session_state.config)
            st.download_button("⬇️ Descarregar .docx Personalizado", data=docx_buffer, file_name="peca_juridica_ma.docx", type="primary")
        
        st.markdown('</div>', unsafe_allow_html=True)

else:
    st.info(f"Módulo '{menu}' em desenvolvimento para integração com o seu fluxo de trabalho.")
