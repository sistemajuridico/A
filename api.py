import os
import io
import json
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import List, Optional
import PyPDF2
import docx
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from google import genai
from google.genai import types

app = FastAPI()

@app.get("/")
async def serve_index():
    return FileResponse("index.html")

def extrair_texto_pdf(file_bytes):
    texto = ""
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        for page in pdf_reader.pages:
            extraido = page.extract_text()
            if extraido:
                texto += extraido + "\n"
    except Exception as e:
        print(f"Erro PDF: {e}")
    return texto

@app.post("/analisar")
async def analisar_caso(
    api_key: str = Form(...),
    fatos_do_caso: str = Form(...),
    area_direito: str = Form(...),
    magistrado: str = Form(None),
    tribunal: str = Form(None),
    arquivos: List[UploadFile] = None
):
    try:
        conteudos_multimais = []
        texto_autos = ""

        if arquivos:
            for arquivo in arquivos:
                ext = arquivo.filename.lower().split('.')[-1]
                corpo = await arquivo.read()
                if ext == "pdf":
                    texto_autos += f"\n[DOC: {arquivo.filename}]\n{extrair_texto_pdf(corpo)}"
                elif ext in ["mp3", "mp4", "mpeg", "wav"]:
                    conteudos_multimais.append(types.Part.from_bytes(data=corpo, mime_type=arquivo.content_type))

        client = genai.Client(api_key=api_key)

        instrucoes_sistema = f"""
        Você é o M.A JURÍDICO ELITE. Especialista em {area_direito}.
        Sua missão é fornecer Inteligência Estratégica Total.

        OBJETIVOS OBRIGATÓRIOS:
        1. JURIMETRIA: Pesquise tendências do magistrado '{magistrado}' no '{tribunal}'.
        2. LINHA DO TEMPO: Cronologia detalhada de datas e fatos.
        3. MODO COMBATE: Identifique vulnerabilidades na narrativa da contraparte.
        4. TRADUÇÃO CLIENTE: Texto simples para WhatsApp explicando o status do caso.
        5. DOUTRINA E JURISPRUDÊNCIA: Use Google Search para citações REAIS e atuais.
        6. PEÇA PROCESSUAL: Redija com Visual Law e formatação técnica.

        RETORNE APENAS JSON PURO:
        {{
            "resumo_estrategico": "Análise técnica de mérito",
            "jurimetria": "Tendências e perfil do magistrado",
            "resumo_cliente": "Texto amigável para WhatsApp",
            "timeline": [{{ "data": "DD/MM/AAAA", "evento": "descrição", "alerta": "opcional" }}],
            "vulnerabilidades_contraparte": ["Ponto 1", "Ponto 2"],
            "checklist": ["Providência 1", "Prova 2"],
            "base_legal": ["Artigos"],
            "jurisprudencia": ["Precedentes"],
            "doutrina": ["Autores"],
            "peca_processual": "Petição completa"
        }}
        """

        prompt = [f"{instrucoes_sistema}\n\nAUTOS:\n{texto_autos}\n\nCASO/INSTRUÇÕES:\n{fatos_do_caso}"]
        prompt.extend(conteudos_multimais)

        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
                tools=[{"google_search": {}}]
            )
        )

        return JSONResponse(content=json.loads(response.text))

    except Exception as e:
        return JSONResponse(content={"erro": str(e)}, status_code=500)

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
    return StreamingResponse(buffer, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": "attachment; filename=MA_Elite_Estrategia.docx"})
