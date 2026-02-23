import os
import io
import json
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse # Adicionado FileResponse
from pydantic import BaseModel
from typing import List, Optional
import PyPDF2
import docx
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from google import genai
from google.genai import types

app = FastAPI()

# --- ROTA PARA SERVIR O SITE (Corrige o Erro 404) ---
@app.get("/")
async def serve_index():
    return FileResponse("index.html")

# --- UTILITÁRIOS ---
def extrair_texto_pdf(file_bytes):
    texto = ""
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        for page in pdf_reader.pages:
            extraido = page.extract_text()
            if extraido:
                texto += extraido + "\n"
    except Exception as e:
        print(f"Erro na extração de PDF: {e}")
    return texto

# --- MOTOR JURÍDICO ---
@app.post("/analisar")
async def analisar_caso(
    api_key: str = Form(...),
    fatos_do_caso: str = Form(...),
    area_direito: str = Form(...),
    arquivos: List[UploadFile] = None
):
    try:
        texto_documentos = ""
        if arquivos:
            for arquivo in arquivos:
                conteudo = await arquivo.read()
                if arquivo.filename.lower().endswith(".pdf"):
                    texto_documentos += f"\n[DOCUMENTO: {arquivo.filename}]\n"
                    texto_documentos += extrair_texto_pdf(conteudo)

        client = genai.Client(api_key=api_key)

        instrucoes_sistema = f"""
        Você é o M.A JURÍDICO, nível Jus IA Experience. Especialista em {area_direito}.
        
        MISSÃO:
        1. ANÁLISE DE PROVAS: Liste no campo 'checklist' 3 a 5 providências ou provas cruciais.
        2. PESQUISA REAL: Use Google Search para acórdãos e súmulas reais.
        3. PEÇA DE ELITE: Redija a petição completa com fundamentação robusta.

        RETORNE APENAS JSON:
        {{
            "resumo_estrategico": "Análise técnica e probabilidade",
            "checklist": ["Providência 1", "Prova 2", "..."],
            "base_legal": ["Artigos"],
            "jurisprudencia": ["Precedentes"],
            "doutrina": ["Doutrinadores"],
            "peca_processual": "Texto da petição"
        }}
        """

        prompt = f"{instrucoes_sistema}\n\nDOCUMENTOS:\n{texto_documentos}\n\nCASO:\n{fatos_do_caso}"

        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3,
                tools=[{"google_search": {}}]
            )
        )

        return JSONResponse(content=json.loads(response.text))

    except Exception as e:
        return JSONResponse(content={"erro": str(e)}, status_code=500)

# --- GERADOR DE WORD PROFISSIONAL ---
class DadosPeca(BaseModel):
    texto_peca: str
    advogado_nome: Optional[str] = ""
    advogado_oab: Optional[str] = ""
    advogado_endereco: Optional[str] = ""

@app.post("/gerar_docx")
async def gerar_docx(dados: DadosPeca):
    doc = docx.Document()
    for s in doc.sections:
        s.top_margin, s.bottom_margin = Cm(3), Cm(2)
        s.left_margin, s.right_margin = Cm(3), Cm(2)

    if dados.advogado_nome:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r = p.add_run(f"{dados.advogado_nome.upper()}\nOAB: {dados.advogado_oab}\n{dados.advogado_endereco}")
        r.font.size, r.font.name = Pt(10), 'Times New Roman'
        doc.add_paragraph("\n")

    for p_text in dados.texto_peca.split('\n'):
        if p_text.strip():
            para = doc.add_paragraph(p_text.strip())
            para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
            para.paragraph_format.first_line_indent = Cm(2.0)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": "attachment; filename=Peca_MA_Premium.docx"})
