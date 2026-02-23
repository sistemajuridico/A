import os
import io
import json
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import PyPDF2
import docx
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from google import genai
from google.genai import types

app = FastAPI()

# --- FUNÇÕES DE APOIO ---

def extrair_texto_pdf(file_bytes):
    texto = ""
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        for page in pdf_reader.pages:
            texto += page.extract_text() + "\n"
    except Exception as e:
        print(f"Erro ao ler PDF: {e}")
    return texto

# --- MOTOR DE INTELIGÊNCIA JURÍDICA ---

@app.post("/analisar")
async def analisar_caso(
    api_key: str = Form(...),
    fatos_do_caso: str = Form(...),
    area_direito: str = Form(...),
    arquivos: List[UploadFile] = None
):
    try:
        # 1. Extrair textos dos anexos se houver
        texto_documentos = ""
        if arquivos:
            for arquivo in arquivos:
                conteudo = await arquivo.read()
                if arquivo.filename.lower().endswith(".pdf"):
                    texto_documentos += f"\n--- Doc: {arquivo.filename} ---\n"
                    texto_documentos += extrair_texto_pdf(conteudo)

        # 2. Configurar o Cliente Gemini
        client = genai.Client(api_key=api_key)

        # 3. Prompt Jurídico Blindado (Baseado no seu código original)
        instrucoes_sistema = f"""
        Você é um advogado sênior, jurista renomado e pesquisador especialista em {area_direito} no Brasil.
        Sua missão é atuar na Pesquisa e Análise Processual Estratégica.
        
        DIRETRIZES OBRIGATÓRIAS:
        1. Responda ESTRITAMENTE em Português do Brasil (PT-BR).
        2. Utilize vernáculo jurídico formal e profissional, típico das petições brasileiras.
        3. É OBRIGATÓRIO buscar jurisprudência real através do Google Search. Não invente números de processos.
        4. Baseie-se APENAS em entendimentos consolidados reais (STF, STJ ou TJs).
        
        Responda EXCLUSIVAMENTE em formato JSON com esta estrutura:
        {{
            "resumo_estrategico": "parecer técnico direto e persuasivo",
            "base_legal": ["Artigo X da Lei Y: Explicação", "..."],
            "jurisprudencia": ["Tribunal - Tema: Entendimento real encontrado", "..."],
            "doutrina": ["Autor: Entendimento aplicável", "..."],
            "peca_processual": "Texto completo da peça com \\n para quebras de linha"
        }}
        """

        prompt_completo = f"{instrucoes_sistema}\n\n"
        if texto_documentos:
            prompt_completo += f"DOCUMENTOS DO PROCESSO:\n{texto_documentos}\n\n"
        prompt_completo += f"FATOS E PEDIDO:\n{fatos_do_caso}"

        # 4. Chamada à API com Google Search (O Cérebro)
        response = client.models.generate_content(
            model='gemini-2.0-flash', # Versão mais estável e rápida para produção
            contents=prompt_completo,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
                tools=[{"google_search": {}}]
            )
        )

        return JSONResponse(content=json.loads(response.text))

    except Exception as e:
        return JSONResponse(content={"erro": str(e)}, status_code=500)

# --- GERADOR DE DOCX (WORD) ---

class DadosWord(BaseModel):
    texto_peca: str
    advogado_nome: Optional[str] = ""
    advogado_oab: Optional[str] = ""
    advogado_endereco: Optional[str] = ""

@app.post("/gerar_docx")
async def gerar_arquivo_word(dados: DadosWord):
    doc = docx.Document()
    
    # Cabeçalho Profissional
    if dados.advogado_nome:
        h = doc.add_paragraph()
        h.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = h.add_run(dados.advogado_nome.upper())
        run.bold = True
        run.font.size = Pt(14)
        
        info = doc.add_paragraph()
        info.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_info = info.add_run(f"OAB: {dados.advogado_oab} | {dados.advogado_endereco}")
        run_info.font.size = Pt(9)
        run_info.italic = True
        
        doc.add_paragraph("_" * 60).alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph("\n")

    # Texto da Peça
    style = doc.styles['Normal']
    style.font.name = 'Arial'
    style.font.size = Pt(12)
    
    for linha in dados.texto_peca.split('\n'):
        if linha.strip():
            p = doc.add_paragraph(linha.strip())
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    
    return StreamingResponse(
        buffer, 
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": "attachment; filename=peca_M_A.docx"}
    )
