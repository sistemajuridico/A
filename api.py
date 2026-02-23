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
                    # Envia arquivos de mídia diretamente para a multimodalidade do Gemini
                    conteudos_multimais.append(types.Part.from_bytes(data=corpo, mime_type=arquivo.content_type))

        client = genai.Client(api_key=api_key)

        instrucoes_sistema = f"""
        Você é o M.A JURÍDICO ELITE. Sua especialidade é {area_direito}.
        
        Sua análise deve ser MULTIDIMENSIONAL:
        1. LINHA DO TEMPO: Extraia todas as datas e crie uma cronologia. Identifique prescrições e contradições temporais.
        2. MODO COMBATE: Analise documentos da contraparte. Identifique furos na narrativa, falta de provas e preveja a estratégia deles.
        3. INTELIGÊNCIA DE AUDIÊNCIA: Se houver áudio/vídeo, transcreva pontos-chave e aponte contradições entre depoimentos e autos.
        4. VISUAL LAW: A petição deve ser moderna, com tabelas comparativas (se útil) e tópicos claros.

        RETORNE APENAS JSON:
        {{
            "resumo_estrategico": "Análise de alto nível + chances de êxito",
            "timeline": [{{ "data": "DD/MM/AAAA", "evento": "descrição", "alerta": "prescrição/contradição?" }}],
            "vulnerabilidades_contraparte": ["Furo 1", "Ponto fraco 2"],
            "checklist": ["Providência 1", "Provas a coletar"],
            "base_legal": ["Leis/Súmulas"],
            "jurisprudencia": ["Precedentes reais"],
            "doutrina": ["Doutrina de peso"],
            "peca_processual": "Petição completa com Visual Law estruturado"
        }}
        """

        prompt = [f"{instrucoes_sistema}\n\nAUTOS TEXTUAIS:\n{texto_autos}\n\nFATOS/INSTRUÇÕES:\n{fatos_do_caso}"]
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
    return StreamingResponse(buffer, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": "attachment; filename=Estrategia_MA_Elite.docx"})
