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

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(
    page_title="M.A Inteligência Jurídica",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Customizado para MINIMALISMO PREMIUM (Preto e Branco Corporativo)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,600;1,400&family=Inter:wght@300;400;500&display=swap');

    /* Fundo da tela principal bem limpo */
    .stApp, [data-testid="stAppViewContainer"] { 
        background-color: #FAFAFA; 
        font-family: 'Inter', sans-serif;
        color: #111111;
    }
    
    [data-testid="stSidebar"] { 
        background-color: #FFFFFF !important; 
        border-right: 1px solid #EAEAEA;
    }
    
    /* Tipografia Clássica Jurídica para Títulos */
    h1, h2, h3 { 
        color: #111111 !important; 
        font-family: 'EB Garamond', serif !important; 
        font-weight: 600; 
    }
    
    p, label, .stMarkdown, span { 
        font-family: 'Inter', sans-serif; 
        color: #333333 !important; 
    }
    
    /* Botão Principal - Estilo Luxo/Minimalista */
    .stButton>button {
        background-color: #111111 !important;
        color: #FFFFFF !important;
        border-radius: 2px;
        padding: 16px 24px;
        font-weight: 500;
        font-size: 0.85rem;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        border: 1px solid #111111;
        transition: all 0.3s ease;
        width: 100%;
    }
    .stButton>button:hover { 
        background-color: #333333 !important; 
        color: #FFFFFF !important; 
    }
    
    /* Caixa da Tese (Escura, contrastando com o fundo branco) */
    .estilo-caixa {
        background-color: #111111;
        padding: 35px;
        border-radius: 4px;
        margin-bottom: 35px;
        color: #FFFFFF;
    }
    .estilo-caixa h3 { color: #FFFFFF !important; margin-top: 0; font-size: 1.5rem; }
    .estilo-caixa p { color: #F0F0F0 !important; font-size: 1.1rem; line-height: 1.6; }
    
    /* Inputs minimalistas */
    .stTextArea textarea, .stTextInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: #FFFFFF !important;
        color: #111111 !important;
        border: 1px solid #CCCCCC !important;
        border-radius: 2px;
        box-shadow: none !important;
    }
    .stTextArea textarea:focus, .stTextInput input:focus {
        border-color: #111111 !important;
    }
    
    /* Abas Redesenhadas (Simples e diretas) */
    .stTabs [data-baseweb="tab-list"] {
        background-color: transparent;
        border-bottom: 1px solid #EAEAEA;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        border: none;
        color: #888888 !important;
        font-weight: 500;
        text-transform: uppercase;
        font-size: 0.8rem;
        letter-spacing: 1px;
    }
    .stTabs [aria-selected="true"] {
        color: #111111 !important;
        border-bottom: 2px solid #111111 !important;
    }
    
    /* Uploader minimalista */
    [data-testid="stFileUploadDropzone"] {
        background-color: #FFFFFF !important;
        border: 1px dashed #CCCCCC !important;
        border-radius: 2px;
    }

    /* Cards de Resultados - Estilo Papel Timbrado */
    .result-card {
        background-color: #FFFFFF;
        padding: 25px;
        margin-bottom: 15px;
        border: 1px solid #EAEAEA;
        border-left: 3px solid #111111;
        color: #333333;
        font-size: 0.95rem;
        line-height: 1.7;
    }

    hr { border-color: #EAEAEA; }
    </style>
""", unsafe_allow_html=True)

# 2. CONFIGURAÇÕES
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

def extrair_texto_pdf(arquivo_pdf):
    texto = ""
    try:
        leitor = PyPDF2.PdfReader(arquivo_pdf)
        for pagina in leitor.pages:
            texto += pagina.extract_text() + "\n"
    except Exception as e:
        st.error(f"Erro na leitura do PDF: {e}")
    return texto

def gerar_docx(texto_peca, dados_advogado):
    doc = docx.Document()
    
    if dados_advogado['advogado_nome']:
        header = doc.add_paragraph()
        header.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_nome = header.add_run(dados_advogado['advogado_nome'].upper())
        run_nome.bold = True
        run_nome.font.size = Pt(12)
        
        info = doc.add_paragraph()
        info.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_info = info.add_run(f"OAB: {dados_advogado['advogado_oab']} | {dados_advogado['advogado_endereco']}")
        run_info.font.size = Pt(9)
        
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

# 3. MOTOR DA IA
def realizar_pesquisa_processual(fatos_do_caso: str, texto_documentos: str, area_direito: str, api_key: str) -> dict:
    try:
        cliente = genai.Client(api_key=api_key)
        
        instrucoes_sistema = f"""
        Você é um advogado sênior, jurista renomado e pesquisador especialista em {area_direito} no Brasil.
        Missão: ETAPA 1 - Pesquisa e Análise Processual Estratégica.
        
        DIRETRIZES:
        1. Responda ESTRITAMENTE em Português do Brasil (PT-BR).
        2. Utilize vernáculo jurídico formal.
        3. Você tem acesso à internet. Cite jurisprudência real e consolidada. Não invente dados.
        
        Responda EXCLUSIVAMENTE em formato JSON com esta estrutura:
        {{
            "resumo_estrategico": "texto do resumo",
            "base_legal": ["Artigo X: Explicação", "Artigo Z..."],
            "jurisprudencia": ["Tribunal - Tema: Explicação", "TJSP..."],
            "doutrina": ["Nome: Resumo", "Outro Autor..."],
            "peca_processual": "Texto completo da peça com quebras de linha."
        }}
        """

        prompt_completo = f"{instrucoes_sistema}\n\n"
        if texto_documentos.strip():
            prompt_completo += f"DOCUMENTOS:\n{texto_documentos}\n\n"
        prompt_completo += f"FATOS:\n{fatos_do_caso}"

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

# 4. INTERFACE VISUAL
st.markdown("<h1 style='text-align: center; border-bottom: 1px solid #EAEAEA; padding-bottom: 20px; margin-bottom: 40px; letter-spacing: 1px;'>M.A INTELIGÊNCIA JURÍDICA</h1>", unsafe_allow_html=True)

# --- BARRA LATERAL ---
with st.sidebar:
    st.markdown("### PAINEL DE CONTROLE")
    st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
    
    api_key_input = st.text_input("Chave API (Google Gemini):", value=st.session_state.config["api_key"], type="password")
    
    st.markdown("<br>### DADOS DA ASSINATURA", unsafe_allow_html=True)
    nome_adv = st.text_input("Nome do Advogado(a):", value=st.session_state.config["advogado_nome"])
    oab_adv = st.text_input("Registro OAB:", value=st.session_state.config["advogado_oab"])
    end_adv = st.text_area("Endereço / Contato:", value=st.session_state.config["advogado_endereco"], height=100)
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("SALVAR CONFIGURAÇÕES"):
        st.session_state.config = {"api_key": api_key_input, "advogado_nome": nome_adv, "advogado_oab": oab_adv, "advogado_endereco": end_adv}
        salvar_config(st.session_state.config)
        st.success("Salvo com sucesso.")

# --- ENTRADA DE DADOS ---
col1, col2 = st.columns([1, 2], gap="large")

with col1:
    st.markdown("### PARÂMETROS DA ANÁLISE")
    area_selecionada = st.selectbox(
        "Selecione o Ramo do Direito:",
        ["Direito Civil e Consumidor", "Direito de Família e Sucessões", "Direito Penal e Processual", "Direito Previdenciário", "Direito do Trabalho", "Direito Tributário e Empresarial"]
    )
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### DOCUMENTOS (OPCIONAL)")
    arquivos_anexados = st.file_uploader("Anexar PDFs (Iniciais, Contratos, etc.)", type=["pdf"], accept_multiple_files=True, label_visibility="collapsed")

with col2:
    st.markdown("### NARRATIVA DOS FATOS")
    fatos_input = st.text_area(
        "", 
        height=220, 
        placeholder="Descreva os fatos e as instruções estratégicas de forma clara e objetiva...",
        label_visibility="collapsed"
    )

st.markdown("<br>", unsafe_allow_html=True)

_, col_btn, _ = st.columns([1, 2, 1])
with col_btn:
    executar = st.button("PROCESSAR ANÁLISE ESTRATÉGICA")

st.markdown("<hr style='margin: 40px 0;'>", unsafe_allow_html=True)

# --- RESULTADOS ---
if executar:
    if not st.session_state.config["api_key"]:
        st.error("Insira a Chave da API no painel lateral.")
    elif len(fatos_input.strip()) < 10 and not arquivos_anexados:
        st.warning("Forneça a narrativa dos fatos ou anexe documentos.")
    else:
        with st.spinner('Acessando bases de dados e estruturando tese...'):
            texto_extraido = ""
            if arquivos_anexados:
                for arq in arquivos_anexados:
                    texto_extraido += f"\n{extrair_texto_pdf(arq)}"
            
            resultado = realizar_pesquisa_processual(fatos_input, texto_extraido, area_selecionada, st.session_state.config["api_key"])
            
            if "erro" in resultado:
                st.error(f"Erro no processamento: {resultado['erro']}")
            else:
                st.markdown("<h2 style='text-align: center; margin-bottom: 30px;'>PARECER TÉCNICO</h2>", unsafe_allow_html=True)
                
                st.markdown(f"""
                <div class="estilo-caixa">
                    <h3>SÍNTESE DA TESE ESTRATÉGICA</h3>
                    <p>{resultado.get("resumo_estrategico", "")}</p>
                </div>
                """, unsafe_allow_html=True)
                
                tab1, tab2, tab3 = st.tabs(["FUNDAMENTAÇÃO LEGAL", "JURISPRUDÊNCIA", "DOUTRINA"])
                
                with tab1:
                    st.markdown("<br>", unsafe_allow_html=True)
                    for item in resultado.get("base_legal", []):
                        st.markdown(f'<div class="result-card"><strong>Legislação Aplicável:</strong><br>{item}</div>', unsafe_allow_html=True)
                        
                with tab2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    for item in resultado.get("jurisprudencia", []):
                        st.markdown(f'<div class="result-card"><strong>Precedente Consolidado:</strong><br>{item}</div>', unsafe_allow_html=True)
                        
                with tab3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    for item in resultado.get("doutrina", []):
                        st.markdown(f'<div class="result-card"><strong>Entendimento Doutrinário:</strong><br>{item}</div>', unsafe_allow_html=True)
                        
                peca_texto = resultado.get("peca_processual", "")
                if peca_texto:
                    st.markdown("<hr style='margin: 40px 0;'>", unsafe_allow_html=True)
                    st.markdown("### MINUTA DA PEÇA PROCESSUAL")
                    st.text_area("Revisão do Documento (Editável):", peca_texto, height=450, label_visibility="collapsed")
                    
                    docx_buffer = gerar_docx(peca_texto, st.session_state.config)
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    _, col_down, _ = st.columns([1, 2, 1])
                    with col_down:
                        st.download_button(
                            label="EXPORTAR DOCUMENTO (.DOCX)",
                            data=docx_buffer,
                            file_name="Peca_Processual_MA.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True
                        )
