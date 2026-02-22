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
    page_title="M.A - Plataforma de Inteligência Jurídica",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Customizado para DARK MODE PREMIUM (Textos Brancos)
st.markdown("""
    <style>
    /* Forçar tema noturno/escuro elegante nas tags principais */
    .stApp, [data-testid="stAppViewContainer"] { background-color: #0f172a; }
    [data-testid="stHeader"] { background-color: #0f172a; }
    [data-testid="stSidebar"] { background-color: #1e293b !important; }
    
    /* Textos principais para branco */
    h1, h2, h3 { color: #ffffff !important; font-family: 'Georgia', serif; font-weight: 800; }
    p, label, .stMarkdown { color: #e2e8f0 !important; }
    
    /* Botão Vibrante com Gradiente */
    .stButton>button {
        background: linear-gradient(135deg, #2563eb, #1d4ed8);
        color: white !important;
        border-radius: 8px;
        padding: 12px 24px;
        font-weight: bold;
        font-size: 1.1rem;
        border: none;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        transition: all 0.3s ease;
    }
    .stButton>button:hover { 
        background: linear-gradient(135deg, #3b82f6, #2563eb); 
        color: white !important; 
        transform: translateY(-2px);
    }
    
    .css-1d391kg { padding-top: 2rem; }
    
    /* Caixa da Tese Principal Escura */
    .estilo-caixa {
        background: #1e293b;
        padding: 25px;
        border-radius: 10px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
        border: 1px solid #334155;
        border-left: 8px solid #3b82f6;
        margin-bottom: 30px;
        color: #ffffff;
    }
    
    /* Estilo das Abas (Tabs) para Dark Mode */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background-color: transparent;
        border-bottom: 2px solid #334155;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #1e293b;
        border-radius: 8px 8px 0px 0px;
        border: 1px solid #334155;
        border-bottom: none;
        color: #94a3b8 !important;
        font-weight: bold;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2563eb !important;
        color: white !important;
        border: none;
    }
    
    /* Ajuste de Caixas de Texto (Inputs) */
    .stTextArea textarea, .stTextInput input {
        background-color: #1e293b !important;
        color: #ffffff !important;
        border: 1px solid #334155 !important;
    }
    
    /* Uploader de arquivo */
    [data-testid="stFileUploadDropzone"] {
        background-color: #1e293b !important;
        border: 2px dashed #334155 !important;
    }
    </style>
""", unsafe_allow_html=True)

# 2. GERENCIAMENTO DE CONFIGURAÇÕES (Chave e Dados do Advogado)
ARQUIVO_CONFIG = "config_ma.json"

def carregar_config():
    if os.path.exists(ARQUIVO_CONFIG):
        with open(ARQUIVO_CONFIG, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"api_key": "", "advogado_nome": "", "advogado_oab": "", "advogado_endereco": ""}

def salvar_config(dados):
    with open(ARQUIVO_CONFIG, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4)

# Inicializa sessão
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
    """Gera um arquivo Word com cabeçalho personalizado"""
    doc = docx.Document()
    
    # Adicionar Cabeçalho (Opcional se os dados existirem)
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

    # Configurar fonte padrão da peça
    estilo = doc.styles['Normal']
    fonte = estilo.font
    fonte.name = 'Arial'
    fonte.size = Pt(12)
    
    # Adicionar o texto parágrafo por parágrafo
    paragrafos = texto_peca.split('\n')
    for p in paragrafos:
        if p.strip():
            para = doc.add_paragraph(p.strip())
            para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            
    # Salvar em memória
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# 3. FUNÇÃO DO MOTOR DE IA (O Cérebro)
def realizar_pesquisa_processual(fatos_do_caso: str, texto_documentos: str, area_direito: str, api_key: str) -> dict:
    try:
        cliente = genai.Client(api_key=api_key)
        
        instrucoes_sistema = f"""
        Você é um advogado sênior, jurista renomado e pesquisador especialista em {area_direito} no Brasil.
        Sua missão é atuar na ETAPA 1 de um caso: A Pesquisa e Análise Processual Estratégica.
        
        DIRETRIZES OBRIGATÓRIAS:
        1. Responda ESTRITAMENTE em Português do Brasil (PT-BR).
        2. Utilize vernáculo jurídico adequado, formal e profissional, típico das petições brasileiras.
        3. Você TEM ACESSO À INTERNET através do Google Search. É OBRIGATÓRIO buscar jurisprudência real, atualizada e verídica. NÃO invente números de processos, temas ou súmulas. Baseie-se APENAS em entendimentos consolidados reais do STF, STJ ou TJs.
        
        A partir dos fatos narrados pelo usuário, você deve fornecer um parecer técnico estruturado focado em encontrar a melhor tese de defesa/acusação para o cliente.
        
        Responda EXCLUSIVAMENTE em formato JSON com a seguinte estrutura exata:
        {{
            "resumo_estrategico": "texto do resumo claro, direto e persuasivo",
            "base_legal": ["Artigo X da Lei Y: Explicação de como se aplica aos fatos", "Artigo Z..."],
            "jurisprudencia": ["Tribunal (ex: STJ) - Tema/Súmula: Explicação do entendimento pacificado real e atualizado encontrado nas buscas", "TJSP..."],
            "doutrina": ["Nome do Autor: Resumo do entendimento aplicável ao caso", "Outro Autor..."],
            "peca_processual": "Texto COMPLETO da peça processual (petição inicial, contestação, etc.), com quebras de linha (\\n), contendo Endereçamento, Qualificação, Dos Fatos, Do Direito e Dos Pedidos."
        }}
        """

        prompt_completo = f"{instrucoes_sistema}\n\n"
        if texto_documentos.strip():
            prompt_completo += f"--- INÍCIO DOS DOCUMENTOS DO PROCESSO ---\n{texto_documentos}\n--- FIM DOS DOCUMENTOS ---\n\n"
        
        prompt_completo += f"PEDIDO/INSTRUÇÕES DO ADVOGADO:\n{fatos_do_caso}"

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

# 4. INTERFACE VISUAL (A Tela Principal)
st.markdown("<h1>⚖️ M.A - Plataforma de Inteligência Jurídica</h1>", unsafe_allow_html=True)
st.markdown("<p style='font-size: 1.2rem; color: #cbd5e1 !important; margin-bottom: 30px; font-weight: 500;'>Sistema avançado de apoio à decisão e pesquisa jurisprudencial em tempo real.</p>", unsafe_allow_html=True)

# --- BARRA LATERAL (Configurações) ---
with st.sidebar:
    st.markdown("### ⚙️ Configurações da Conta")
    
    # API Key
    api_key_input = st.text_input("Chave da API (Google Gemini):", value=st.session_state.config["api_key"], type="password")
    
    st.divider()
    st.markdown("### 👤 Dados do Advogado (Peça)")
    nome_adv = st.text_input("Nome Completo:", value=st.session_state.config["advogado_nome"])
    oab_adv = st.text_input("Inscrição OAB:", value=st.session_state.config["advogado_oab"])
    end_adv = st.text_area("Endereço/Contatos:", value=st.session_state.config["advogado_endereco"], height=70)
    
    # Salvar configurações
    if st.button("💾 Salvar Configurações", use_container_width=True):
        st.session_state.config = {
            "api_key": api_key_input,
            "advogado_nome": nome_adv,
            "advogado_oab": oab_adv,
            "advogado_endereco": end_adv
        }
        salvar_config(st.session_state.config)
        st.success("Configurações salvas!")
            
    st.divider()
    
    st.markdown("### 📚 Especialidade")
    area_selecionada = st.selectbox(
        "Selecione o ramo aplicável:",
        ["Direito Civil, Imobiliário e Consumidor", "Direito de Família e Sucessões", "Direito Penal e Processual Penal", "Direito Previdenciário", "Direito do Trabalho", "Direito Tributário e Empresarial"]
    )

# --- ÁREA PRINCIPAL (Entrada de Dados) ---
st.markdown("### 📁 Autos do Processo (Opcional)")
arquivos_anexados = st.file_uploader("Arraste PDFs aqui para análise documental profunda.", type=["pdf"], accept_multiple_files=True)

fatos_input = st.text_area(
    "📝 Relato dos Fatos ou Instruções para a IA:", 
    height=200, 
    placeholder="Descreva o caso ou as ordens específicas para a IA aqui..."
)

if st.button("⚖️ Executar Análise Jurídica e Pesquisa Web", use_container_width=True):
    if not st.session_state.config["api_key"]:
        st.error("⚠️ Insira e salve sua Chave da API na barra lateral.")
    elif len(fatos_input.strip()) < 10 and not arquivos_anexados:
        st.warning("⚠️ Forneça um relato ou anexe documentos.")
    else:
        with st.spinner('A processar análise jurídica avançada...'):
            texto_extraido = ""
            if arquivos_anexados:
                for arq in arquivos_anexados:
                    texto_extraido += f"\n--- Documento: {arq.name} ---\n{extrair_texto_pdf(arq)}"
            
            resultado = realizar_pesquisa_processual(fatos_input, texto_extraido, area_selecionada, st.session_state.config["api_key"])
            
            if "erro" in resultado:
                st.error(f"❌ Erro: {resultado['erro']}")
            else:
                st.markdown(f"""
                <div class="estilo-caixa">
                    <h3 style='margin-top: 0;'>📌 Tese Principal (Resumo Estratégico)</h3>
                    <p style='font-size: 1.1rem; line-height: 1.6;'>{resultado.get("resumo_estrategico", "")}</p>
                </div>
                """, unsafe_allow_html=True)
                
                tab1, tab2, tab3 = st.tabs(["⚖️ Fundamentação Legal", "🏛️ Jurisprudência", "📚 Doutrina"])
                
                with tab1:
                    st.markdown("<br>", unsafe_allow_html=True)
                    for item in resultado.get("base_legal", []):
                        st.markdown(f'<div style="background-color: #1e293b; border-left: 6px solid #3b82f6; padding: 15px; border-radius: 4px; margin-bottom: 15px; border: 1px solid #334155; color: white;">📖 {item}</div>', unsafe_allow_html=True)
                        
                with tab2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    for item in resultado.get("jurisprudencia", []):
                        st.markdown(f'<div style="background-color: #1e293b; border-left: 6px solid #f59e0b; padding: 15px; border-radius: 4px; margin-bottom: 15px; border: 1px solid #334155; color: white;">⚖️ {item}</div>', unsafe_allow_html=True)
                        
                with tab3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    for item in resultado.get("doutrina", []):
                        st.markdown(f'<div style="background-color: #1e293b; border-left: 6px solid #10b981; padding: 15px; border-radius: 4px; margin-bottom: 15px; border: 1px solid #334155; color: white;">✍️ {item}</div>', unsafe_allow_html=True)
                        
                peca_texto = resultado.get("peca_processual", "")
                if peca_texto:
                    st.markdown("---")
                    st.markdown("### 📄 Minuta da Peça Processual")
                    st.text_area("Pré-visualização:", peca_texto, height=300)
                    
                    docx_buffer = gerar_docx(peca_texto, st.session_state.config)
                    st.download_button(
                        label="⬇️ Descarregar Peça Personalizada (.docx)",
                        data=docx_buffer,
                        file_name="peca_processual_M_A.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        type="primary",
                        use_container_width=True
                    )
