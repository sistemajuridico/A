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
from streamlit_option_menu import option_menu

# 1. CONFIGURAÇÃO DA PÁGINA E ESTILIZAÇÃO
st.set_page_config(
    page_title="M.A | Inteligência Jurídica",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Customizado (Agora com a limpeza do Streamlit nativo)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=Playfair+Display:wght@600;700&display=swap');

    /* Ocultar elementos padrão do Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display:none;}
    .block-container { padding-top: 2rem !important; }

    /* Fundos e Textos Gerais */
    .stApp, [data-testid="stAppViewContainer"] { 
        background-color: #0b1120;
        font-family: 'Inter', sans-serif;
    }
    [data-testid="stSidebar"] { 
        background-color: #111827 !important; 
        border-right: 1px solid #1f2937;
    }
    
    /* Tipografia de Títulos */
    h1, h2, h3 { 
        color: #f8fafc !important; 
        font-family: 'Playfair Display', serif !important; 
        font-weight: 700; 
        letter-spacing: -0.5px;
    }
    p, label, .stMarkdown, span { color: #cbd5e1 !important; font-family: 'Inter', sans-serif; }
    
    /* Botões */
    .stButton>button {
        background: linear-gradient(135deg, #1e3a8a, #3b82f6);
        color: white !important;
        border-radius: 6px;
        padding: 14px 28px;
        font-weight: 600;
        font-size: 1.05rem;
        border: 1px solid #3b82f6;
        transition: all 0.3s ease;
        width: 100%;
    }
    .stButton>button:hover { 
        background: linear-gradient(135deg, #2563eb, #60a5fa); 
        transform: translateY(-2px);
    }
    
    /* Inputs e Áreas de Texto */
    .stTextArea textarea, .stTextInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: #1e293b !important;
        color: #f8fafc !important;
        border: 1px solid #334155 !important;
        border-radius: 8px;
    }
    
    /* Uploader Minimalista */
    [data-testid="stFileUploadDropzone"] {
        background-color: rgba(30, 41, 59, 0.5) !important;
        border: 2px dashed #475569 !important;
        border-radius: 12px;
        padding: 30px;
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

# Funções Auxiliares (Omitidas para brevidade visual, mas presentes no código)
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
        Você é um advogado sênior, jurista renomado e pesquisador especialista em {area_direito} no Brasil.
        Sua missão é atuar na ETAPA 1 de um caso: A Pesquisa e Análise Processual Estratégica.
        DIRETRIZES: 1. PT-BR. 2. Vernáculo jurídico. 3. Busque jurisprudência real no Google.
        Responda EXCLUSIVAMENTE em JSON: {{"resumo_estrategico": "...", "base_legal": ["..."], "jurisprudencia": ["..."], "doutrina": ["..."], "peca_processual": "..."}}
        """
        prompt_completo = f"{instrucoes_sistema}\n\n"
        if texto_documentos.strip():
            prompt_completo += f"--- DOCUMENTOS ---\n{texto_documentos}\n--- FIM ---\n\n"
        prompt_completo += f"FATOS:\n{fatos_do_caso}"

        resposta = cliente.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt_completo,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2, tools=[{"google_search": {}}])
        )
        return json.loads(resposta.text)
    except Exception as e:
        return {"erro": str(e)}

# 3. INTERFACE E NAVEGAÇÃO
with st.sidebar:
    st.markdown("<h2 style='text-align: center; color: #f8fafc; font-family: Playfair Display;'>M.A Legal</h2>", unsafe_allow_html=True)
    st.markdown("<hr style='border-color: #334155; margin-top: 0;'>", unsafe_allow_html=True)
    
    # Menu interativo moderno
    selecao = option_menu(
        menu_title=None,
        options=["Análise de Caso", "Configurações do Sistema"],
        icons=["briefcase", "gear"],
        menu_icon="cast",
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "icon": {"color": "#60a5fa", "font-size": "18px"}, 
            "nav-link": {"font-size": "15px", "text-align": "left", "margin":"5px 0", "--hover-color": "#1e293b", "color": "#cbd5e1"},
            "nav-link-selected": {"background-color": "#1e3a8a", "color": "#ffffff"},
        }
    )

# --- ROTA: CONFIGURAÇÕES ---
if selecao == "Configurações do Sistema":
    st.markdown("## ⚙️ Painel de Controle e Credenciais")
    st.markdown("Configure os parâmetros globais da aplicação abaixo.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🔑 Inteligência Artificial")
        api_key_input = st.text_input("Chave API (Google Gemini):", value=st.session_state.config["api_key"], type="password")
    
    with col2:
        st.markdown("### 👤 Dados do Perfil Jurídico")
        nome_adv = st.text_input("Nome do Advogado(a):", value=st.session_state.config["advogado_nome"])
        oab_adv = st.text_input("OAB:", value=st.session_state.config["advogado_oab"])
        end_adv = st.text_area("Endereço/Contato (Cabeçalho da Peça):", value=st.session_state.config["advogado_endereco"], height=100)
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾 Salvar Configurações no Servidor"):
        st.session_state.config = {"api_key": api_key_input, "advogado_nome": nome_adv, "advogado_oab": oab_adv, "advogado_endereco": end_adv}
        salvar_config(st.session_state.config)
        st.success("Configurações atualizadas com sucesso!")

# --- ROTA: ANÁLISE DE CASO (PRINCIPAL) ---
elif selecao == "Análise de Caso":
    st.markdown("<h1 style='text-align: center; margin-bottom: 0.5rem;'>M.A <span style='color: #60a5fa;'>|</span> Inteligência Jurídica</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size: 1.1rem; color: #94a3b8 !important; margin-bottom: 3rem;'>Sistema avançado de apoio à decisão e pesquisa jurisprudencial</p>", unsafe_allow_html=True)

    col_esq, col_dir = st.columns([1, 2], gap="large")

    with col_esq:
        area_selecionada = st.selectbox(
            "Ramo do Direito Aplicável:",
            ["Direito Civil, Imobiliário e Consumidor", "Direito de Família e Sucessões", "Direito Penal e Processual Penal", "Direito Previdenciário", "Direito do Trabalho", "Direito Tributário e Empresarial"]
        )
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("<p style='font-weight: 500; margin-bottom: 5px;'>📄 Autos do Processo (Opcional)</p>", unsafe_allow_html=True)
        arquivos_anexados = st.file_uploader("Arraste PDFs iniciais, B.O. ou contratos aqui", type=["pdf"], accept_multiple_files=True, label_visibility="collapsed")

    with col_dir:
        fatos_input = st.text_area(
            "📝 Relato Estratégico e Instruções:", 
            height=240, 
            placeholder="Descreva detalhadamente os fatos do caso..."
        )

    st.markdown("<br>", unsafe_allow_html=True)

    _, col_btn, _ = st.columns([1, 2, 1])
    with col_btn:
        executar = st.button("⚖️ Executar Análise Jurídica Avançada")

    st.markdown("<hr style='margin-top: 3rem; margin-bottom: 3rem;'>", unsafe_allow_html=True)

    if executar:
        if not st.session_state.config["api_key"]:
            st.error("⚠️ Atenção: Acesse a aba 'Configurações do Sistema' e insira sua Chave da API.")
        elif len(fatos_input.strip()) < 10 and not arquivos_anexados:
            st.warning("⚠️ Forneça um relato mínimo dos fatos ou anexe documentos para análise.")
        else:
            with st.spinner('🔍 Analisando doutrina, consultando tribunais e estruturando tese...'):
                texto_extraido = ""
                if arquivos_anexados:
                    for arq in arquivos_anexados:
                        texto_extraido += f"\n--- {arq.name} ---\n{extrair_texto_pdf(arq)}"
                
                resultado = realizar_pesquisa_processual(fatos_input, texto_extraido, area_selecionada, st.session_state.config["api_key"])
                
                if "erro" in resultado:
                    st.error(f"❌ Erro na comunicação com a IA: {resultado['erro']}")
                else:
                    st.markdown("## 📊 Parecer Estratégico M.A")
                    
                    st.markdown(f"""
                    <div style="background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); padding: 30px; border-radius: 12px; border-left: 6px solid #60a5fa; margin-bottom: 30px; color: #f1f5f9;">
                        <h3 style='margin-top: 0; font-size: 1.4rem;'>📌 Tese Principal Formada</h3>
                        <p style='font-size: 1.1rem; line-height: 1.7;'>{resultado.get("resumo_estrategico", "")}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    tab1, tab2, tab3 = st.tabs(["⚖️ Fundamentação Legal", "🏛️ Jurisprudência Consolidada", "📚 Entendimento Doutrinário"])
                    
                    with tab1:
                        st.markdown("<br>", unsafe_allow_html=True)
                        for item in resultado.get("base_legal", []):
                            st.markdown(f'<div style="background-color: #1e293b; padding: 20px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #3b82f6; color: #e2e8f0;">📖 <strong>Dispositivo:</strong> {item}</div>', unsafe_allow_html=True)
                            
                    with tab2:
                        st.markdown("<br>", unsafe_allow_html=True)
                        for item in resultado.get("jurisprudencia", []):
                            st.markdown(f'<div style="background-color: #1e293b; padding: 20px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #f59e0b; color: #e2e8f0;">⚖️ <strong>Precedente:</strong> {item}</div>', unsafe_allow_html=True)
                            
                    with tab3:
                        st.markdown("<br>", unsafe_allow_html=True)
                        for item in resultado.get("doutrina", []):
                            st.markdown(f'<div style="background-color: #1e293b; padding: 20px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #10b981; color: #e2e8f0;">✍️ <strong>Doutrina:</strong> {item}</div>', unsafe_allow_html=True)
                            
                    peca_texto = resultado.get("peca_processual", "")
                    if peca_texto:
                        st.markdown("<br><br>", unsafe_allow_html=True)
                        st.markdown("### 📄 Minuta da Peça Processual Gerada")
                        st.text_area("Revisão Rápida da Peça (Editável):", peca_texto, height=400)
                        
                        docx_buffer = gerar_docx(peca_texto, st.session_state.config)
                        
                        _, col_down, _ = st.columns([1, 2, 1])
                        with col_down:
                            st.download_button(
                                label="⬇️ Exportar Peça em Microsoft Word (.docx)",
                                data=docx_buffer,
                                file_name="peca_processual_MA.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                type="primary"
                            )
