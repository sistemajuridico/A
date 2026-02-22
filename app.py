import streamlit as st
import json
import os
import io
import PyPDF2
import docx
from docx.shared import Pt
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

# 2. GERENCIAMENTO DA CHAVE API
ARQUIVO_CHAVE = "gemini_key.txt"

def carregar_chave():
    if os.path.exists(ARQUIVO_CHAVE):
        with open(ARQUIVO_CHAVE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""

def salvar_chave(chave):
    with open(ARQUIVO_CHAVE, "w", encoding="utf-8") as f:
        f.write(chave.strip())

# Carrega a chave para a sessão atual
if "api_key" not in st.session_state:
    st.session_state.api_key = carregar_chave()

def extrair_texto_pdf(arquivo_pdf):
    texto = ""
    try:
        leitor = PyPDF2.PdfReader(arquivo_pdf)
        for pagina in leitor.pages:
            texto += pagina.extract_text() + "\n"
    except Exception as e:
        st.error(f"Erro ao ler o PDF: {e}")
    return texto

def gerar_docx(texto_peca):
    """Gera um arquivo Word em memória a partir do texto da peça"""
    doc = docx.Document()
    
    # Configurar fonte padrão (estilo jurídico)
    estilo = doc.styles['Normal']
    fonte = estilo.font
    fonte.name = 'Arial'
    fonte.size = Pt(12)
    
    # Adicionar o texto parágrafo por parágrafo
    paragrafos = texto_peca.split('\n')
    for p in paragrafos:
        if p.strip():
            doc.add_paragraph(p.strip())
            
    # Salvar em memória para o Streamlit fazer o download
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

        # Chamada à IA com o Search Grounding (Ancoragem na Internet) ativado
        resposta = cliente.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt_completo,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
                tools=[{"google_search": {}}]  # Aqui está a mágica: Liga a IA na internet!
            )
        )
        
        return json.loads(resposta.text)

    except Exception as e:
        return {"erro": str(e)}

# 4. INTERFACE VISUAL (A Tela Principal)
st.markdown("<h1>⚖️ M.A - Plataforma de Inteligência Jurídica</h1>", unsafe_allow_html=True)
st.markdown("<p style='font-size: 1.2rem; color: #cbd5e1 !important; margin-bottom: 30px; font-weight: 500;'>Sistema avançado de apoio à decisão, fundamentação legal e pesquisa jurisprudencial ancorada em resultados reais da web.</p>", unsafe_allow_html=True)

# --- BARRA LATERAL (Configurações) ---
with st.sidebar:
    st.markdown("### ⚙️ Configurações do Sistema")
    
    nova_chave = st.text_input("Chave da API (Google Gemini):", value=st.session_state.api_key, type="password")
    
    if nova_chave != st.session_state.api_key:
        st.session_state.api_key = nova_chave
        
    if st.button("💾 Salvar Chave Neste Computador", use_container_width=True):
        if st.session_state.api_key:
            salvar_chave(st.session_state.api_key)
            st.success("Chave salva com sucesso!")
        else:
            st.warning("Insira uma chave antes de salvar.")
            
    st.divider()
    
    st.markdown("### 📚 Especialidade")
    area_selecionada = st.selectbox(
        "Selecione o ramo de atuação aplicável:",
        [
            "Direito Civil, Imobiliário e Consumidor",
            "Direito de Família e Sucessões",
            "Direito Penal e Processual Penal",
            "Direito Previdenciário",
            "Direito do Trabalho e Processo do Trabalho",
            "Direito Tributário e Empresarial"
        ]
    )
    
    st.divider()
    st.info("💡 **Dica do Sistema:** A IA agora consulta a internet em tempo real para embasar a jurisprudência. Análises podem levar alguns segundos a mais, mas garantem altíssima precisão.")

# --- ÁREA PRINCIPAL (Entrada de Dados) ---
st.markdown("### 📁 Anexar Documentos do Processo (Opcional)")
arquivos_anexados = st.file_uploader("Envie as peças (PDF). O sistema lerá os documentos para embasar a análise.", type=["pdf"], accept_multiple_files=True)

fatos_input = st.text_area(
    "📝 Relato dos Fatos ou Instruções para a IA:", 
    height=200, 
    placeholder="Ex: Anexei a petição inicial e a contestação. Analise os argumentos da parte contrária e me dê a base legal e jurisprudência para a Réplica..."
)

col_btn, col_espaco = st.columns([1, 2])
with col_btn:
    btn_analisar = st.button("⚖️ Executar Análise Jurídica e Pesquisa Web", use_container_width=True)

if btn_analisar:
    if not st.session_state.api_key:
        st.error("⚠️ Autenticação necessária: Por favor, insira a sua Chave da API na barra lateral esquerda.")
    elif len(fatos_input.strip()) < 10 and not arquivos_anexados:
        st.warning("⚠️ Forneça um relato ou anexe documentos para prosseguir.")
    else:
        with st.spinner('A processar análise e pesquisando fontes reais na internet. Lendo os autos, consultando bases legais, doutrina e jurisprudência...'):
            
            # Extrair texto dos PDFs anexados
            texto_extraido = ""
            if arquivos_anexados:
                for arq in arquivos_anexados:
                    texto_extraido += f"\n--- Documento: {arq.name} ---\n"
                    texto_extraido += extrair_texto_pdf(arq)
            
            resultado = realizar_pesquisa_processual(fatos_input, texto_extraido, area_selecionada, st.session_state.api_key)
            
            if "erro" in resultado:
                st.error(f"❌ Erro de processamento: {resultado['erro']}\nVerifique sua chave de API ou conexão de internet.")
            else:
                st.markdown(f"""
                <div class="estilo-caixa">
                    <h3 style='margin-top: 0; color: #ffffff !important;'>📌 Tese Principal (Resumo Estratégico)</h3>
                    <p style='font-size: 1.1rem; line-height: 1.6; color: #e2e8f0;'>{resultado.get("resumo_estrategico", "Resumo não disponível.")}</p>
                </div>
                """, unsafe_allow_html=True)
                
                tab1, tab2, tab3 = st.tabs(["⚖️ Fundamentação Legal", "🏛️ Jurisprudência Consolidada", "📚 Embasamento Doutrinário"])
                
                with tab1:
                    st.markdown("<br>", unsafe_allow_html=True)
                    for item in resultado.get("base_legal", []):
                        # Caixa Escura com Borda Azul
                        st.markdown(f"""
                        <div style="background-color: #1e293b; border-left: 6px solid #3b82f6; padding: 15px; border-radius: 4px; margin-bottom: 15px; border: 1px solid #334155;">
                            <span style="font-size: 1.1em;">📖</span> <span style="color: #ffffff; font-weight: 500;">{item}</span>
                        </div>
                        """, unsafe_allow_html=True)
                        
                with tab2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    for item in resultado.get("jurisprudencia", []):
                        # Caixa Escura com Borda Dourada/Âmbar
                        st.markdown(f"""
                        <div style="background-color: #1e293b; border-left: 6px solid #f59e0b; padding: 15px; border-radius: 4px; margin-bottom: 15px; border: 1px solid #334155;">
                            <span style="font-size: 1.1em;">⚖️</span> <span style="color: #ffffff; font-weight: 500;">{item}</span>
                        </div>
                        """, unsafe_allow_html=True)
                        
                with tab3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    for item in resultado.get("doutrina", []):
                        # Caixa Escura com Borda Verde
                        st.markdown(f"""
                        <div style="background-color: #1e293b; border-left: 6px solid #10b981; padding: 15px; border-radius: 4px; margin-bottom: 15px; border: 1px solid #334155;">
                            <span style="font-size: 1.1em;">✍️</span> <span style="color: #ffffff; font-weight: 500;">{item}</span>
                        </div>
                        """, unsafe_allow_html=True)
                        
                # --- NOVA SEÇÃO: GERAÇÃO DA PEÇA E DOWNLOAD ---
                peca_texto = resultado.get("peca_processual", "")
                if peca_texto:
                    st.markdown("---")
                    st.markdown("<h3 style='color: #ffffff !important;'>📄 Minuta da Peça Processual</h3>", unsafe_allow_html=True)
                    
                    # Mostrar um preview da peça
                    st.text_area("Pré-visualização (poderá editar formatações finas depois no Word):", peca_texto, height=300)
                    
                    # Gerar arquivo Word em memória
                    docx_buffer = gerar_docx(peca_texto)
                    
                    # Botão de Download
                    st.download_button(
                        label="⬇️ Descarregar Peça Processual (.docx)",
                        data=docx_buffer,
                        file_name="peca_processual_IA.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        type="primary",
                        use_container_width=True
                    )