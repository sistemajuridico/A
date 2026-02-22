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

# 1. CONFIGURAÇÃO DA PÁGINA E ESTILIZAÇÃO
st.set_page_config(
    page_title="M.A | Inteligência Jurídica",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Reduzido: O config.toml agora cuida das cores.
# Mantemos apenas as fontes premium e a ocultação das marcas do Streamlit.
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=Playfair+Display:wght@600;700&display=swap');

    /* Tipografia (Estilo Editorial/Jurídico) */
    h1, h2, h3 { 
        font-family: 'Playfair Display', serif !important; 
        font-weight: 700; 
        letter-spacing: -0.5px;
    }
    p, label, .stMarkdown, span, li { 
        font-family: 'Inter', sans-serif; 
    }
    
    /* Limpeza da Interface do Streamlit (Modo "App Próprio") */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
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

# 3. FUNÇÃO DO MOTOR DE IA
def realizar_pesquisa_processual(fatos_do_caso: str, texto_documentos: str, area_direito: str, api_key: str) -> dict:
    try:
        cliente = genai.Client(api_key=api_key)
        
        instrucoes_sistema = f"""
        Você é um advogado sênior, jurista renomado e pesquisador especialista em {area_direito} no Brasil.
        Sua missão é atuar na ETAPA 1 de um caso: A Pesquisa e Análise Processual Estratégica.
        
        DIRETRIZES OBRIGATÓRIAS:
        1. Responda ESTRITAMENTE em Português do Brasil (PT-BR).
        2. Utilize vernáculo jurídico adequado, formal e profissional.
        3. Você TEM ACESSO À INTERNET através do Google Search. É OBRIGATÓRIO buscar jurisprudência real, atualizada e verídica. NÃO invente números.
        
        Responda EXCLUSIVAMENTE em formato JSON com a seguinte estrutura exata:
        {{
            "resumo_estrategico": "texto do resumo claro, direto e persuasivo",
            "base_legal": ["Artigo X da Lei Y: Explicação", "Artigo Z..."],
            "jurisprudencia": ["Tribunal (ex: STJ) - Tema/Súmula: Explicação", "TJSP..."],
            "doutrina": ["Nome do Autor: Resumo do entendimento", "Outro Autor..."],
            "peca_processual": "Texto COMPLETO da peça processual com quebras de linha (\\n)."
        }}
        """

        prompt_completo = f"{instrucoes_sistema}\n\n"
        if texto_documentos.strip():
            prompt_completo += f"--- DOCUMENTOS DO PROCESSO ---\n{texto_documentos}\n--- FIM ---\n\n"
        prompt_completo += f"FATOS DO CASO:\n{fatos_do_caso}"

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

# 4. INTERFACE VISUAL PRINCIPAL
# Cabeçalho
st.markdown("<h1 style='text-align: center; margin-bottom: 0;'>M.A <span style='color: #3b82f6;'>|</span> Inteligência Jurídica</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size: 1.1rem; opacity: 0.8; margin-bottom: 3rem;'>Sistema avançado de apoio à decisão e pesquisa jurisprudencial</p>", unsafe_allow_html=True)

# --- BARRA LATERAL ---
with st.sidebar:
    st.markdown("### ⚙️ Painel de Controle")
    st.divider()
    
    with st.expander("🔑 Credenciais da IA", expanded=True):
        api_key_input = st.text_input("Chave API (Google Gemini):", value=st.session_state.config["api_key"], type="password")
    
    with st.expander("👤 Dados da Assinatura (Peça)"):
        nome_adv = st.text_input("Nome do Advogado(a):", value=st.session_state.config["advogado_nome"])
        oab_adv = st.text_input("OAB:", value=st.session_state.config["advogado_oab"])
        end_adv = st.text_area("Endereço/Contato:", value=st.session_state.config["advogado_endereco"], height=100)
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾 Salvar Configurações", use_container_width=True):
        st.session_state.config = {"api_key": api_key_input, "advogado_nome": nome_adv, "advogado_oab": oab_adv, "advogado_endereco": end_adv}
        salvar_config(st.session_state.config)
        st.success("Configurações salvas!")

# --- ÁREA DE INPUT (Dentro de um Container Estilizado) ---
with st.container(border=True):
    st.markdown("### 📋 Configuração do Caso")
    st.markdown("<br>", unsafe_allow_html=True)

    col_esq, col_dir = st.columns([1, 2], gap="large")

    with col_esq:
        area_selecionada = st.selectbox(
            "Ramo do Direito Aplicável:",
            ["Direito Civil, Imobiliário e Consumidor", "Direito de Família e Sucessões", "Direito Penal e Processual Penal", "Direito Previdenciário", "Direito do Trabalho", "Direito Tributário e Empresarial"]
        )
        st.markdown("<br>", unsafe_allow_html=True)
        arquivos_anexados = st.file_uploader("📄 Autos do Processo (Opcional - PDFs)", type=["pdf"], accept_multiple_files=True)

    with col_dir:
        fatos_input = st.text_area(
            "📝 Relato Estratégico e Instruções:", 
            height=220, 
            placeholder="Descreva detalhadamente os fatos do caso. Ex:\n\n'Meu cliente sofreu um golpe via Pix. O banco recebedor da fraude não bloqueou a conta mesmo após o alerta MED...'"
        )

st.markdown("<br>", unsafe_allow_html=True)

# Botão de Ação Principal (Usando o tipo 'primary' para pegar a cor azul do config.toml)
_, col_btn, _ = st.columns([1, 2, 1])
with col_btn:
    executar = st.button("⚖️ Executar Análise Jurídica Avançada", type="primary", use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- EXECUÇÃO E RESULTADOS ---
if executar:
    if not st.session_state.config["api_key"]:
        st.error("⚠️ Atenção: Configure sua Chave da API no painel lateral esquerdo.")
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
                st.divider()
                st.markdown("## 📊 Parecer Estratégico M.A")
                
                # Tese Principal destacada usando container nativo
                with st.container(border=True):
                    st.markdown("### 📌 Tese Principal Formada")
                    st.info(resultado.get("resumo_estrategico", ""))
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                # Sistema de Abas Nativas
                tab1, tab2, tab3 = st.tabs(["⚖️ Fundamentação Legal", "🏛️ Jurisprudência Consolidada", "📚 Entendimento Doutrinário"])
                
                with tab1:
                    for item in resultado.get("base_legal", []):
                        with st.container(border=True):
                            st.markdown(f"📖 **Dispositivo:** {item}")
                        
                with tab2:
                    for item in resultado.get("jurisprudencia", []):
                        with st.container(border=True):
                            st.markdown(f"⚖️ **Precedente:** {item}")
                        
                with tab3:
                    for item in resultado.get("doutrina", []):
                        with st.container(border=True):
                            st.markdown(f"✍️ **Doutrina:** {item}")
                        
                # Geração da Peça
                peca_texto = resultado.get("peca_processual", "")
                if peca_texto:
                    st.divider()
                    st.markdown("### 📄 Minuta da Peça Processual Gerada")
                    st.text_area("Revisão Rápida da Peça (Editável):", peca_texto, height=400, label_visibility="collapsed")
                    
                    docx_buffer = gerar_docx(peca_texto, st.session_state.config)
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    _, col_down, _ = st.columns([1, 2, 1])
                    with col_down:
                        st.download_button(
                            label="⬇️ Exportar Peça em Microsoft Word (.docx)",
                            data=docx_buffer,
                            file_name="peca_processual_MA.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            type="primary",
                            use_container_width=True
                        )
