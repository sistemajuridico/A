from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
import json
import io
import PyPDF2
import docx
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from typing import List, Optional
from google import genai
from google.genai import types

# 1. Inicializa a API
app = FastAPI(title="M.A API Jurídica", version="2.0")

# 2. Configuração de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Rota Principal que carrega o seu Front-end (O Rosto)
@app.get("/")
def mostrar_site():
    # Quando alguém acessar o link, o servidor entrega o arquivo HTML
    return FileResponse("index.html")

# 4. Função Auxiliar de Leitura de PDF
def extrair_texto_pdf(arquivo_pdf_bytes: bytes) -> str:
    texto = ""
    try:
        leitor = PyPDF2.PdfReader(io.BytesIO(arquivo_pdf_bytes))
        for pagina in leitor.pages:
            texto += pagina.extract_text() + "\n"
    except Exception as e:
        print(f"Erro ao extrair PDF: {e}")
    return texto

# 5. Rota de Análise Jurídica (Recebe Textos e PDFs)
@app.post("/analisar")
async def analisar_caso(
    fatos_do_caso: str = Form(...),
    area_direito: str = Form(...),
    api_key: str = Form(...),
    arquivos: Optional[List[UploadFile]] = File(None)
):
    try:
        texto_documentos = ""
        if arquivos:
            for arq in arquivos:
                conteudo = await arq.read() 
                texto_extraido = extrair_texto_pdf(conteudo)
                if texto_extraido:
                    texto_documentos += f"\n--- {arq.filename} ---\n{texto_extraido}"

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
        raise HTTPException(status_code=500, detail=str(e))

# 6. Estrutura de dados para a geração do Word
class DadosPeca(BaseModel):
    texto_peca: str
    advogado_nome: str = ""
    advogado_oab: str = ""
    advogado_endereco: str = ""

# 7. Rota Exclusiva para Exportar o Word
@app.post("/gerar_docx")
def gerar_docx_endpoint(dados: DadosPeca):
    doc = docx.Document()
    
    if dados.advogado_nome:
        header = doc.add_paragraph()
        header.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_nome = header.add_run(dados.advogado_nome.upper())
        run_nome.bold = True
        run_nome.font.size = Pt(14)
        
        info = doc.add_paragraph()
        info.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_info = info.add_run(f"OAB: {dados.advogado_oab} | {dados.advogado_endereco}")
        run_info.font.size = Pt(9)
        run_info.italic = True
        
        doc.add_paragraph("_" * 60).alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph("\n")

    estilo = doc.styles['Normal']
    fonte = estilo.font
    fonte.name = 'Arial'
    fonte.size = Pt(12)
    
    paragrafos = dados.texto_peca.split('\n')
    for p in paragrafos:
        if p.strip():
            para = doc.add_paragraph(p.strip())
            para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    
    return StreamingResponse(
        buffer, 
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": "attachment; filename=peca_processual_MA.docx"}
    )
