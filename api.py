import os
import io
import json
import time
import shutil
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import List, Optional
import docx
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from google import genai
from google.genai import types

app = FastAPI()

@app.get("/")
async def serve_index():
    return FileResponse("index.html")

# --- MOTOR DE INTELIGÊNCIA JURÍDICA ---

@app.post("/analisar")
async def analisar_caso(
    fatos_do_caso: str = Form(...),
    area_direito: str = Form(...),
    magistrado: str = Form(None),
    tribunal: str = Form(None),
    arquivos: List[UploadFile] = None
):
    temp_files = []
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        conteudos_para_ia = []

        if arquivos:
            for arquivo in arquivos:
                if not arquivo.filename: continue
                
                # Criar caminho temporário
                path_temp = f"strm_{int(time.time())}_{arquivo.filename}"
                temp_files.append(path_temp)

                # TRANSFERÊNCIA DE FLUXO (SHUTIL): Usa 0% de RAM extra
                # Copia o arquivo do upload diretamente para o disco do Render
                with open(path_temp, "wb") as buffer:
                    shutil.copyfileobj(arquivo.file, buffer)
                
                # Upload para o Google (Google processa o PDF pesado)
                file_upload = client.files.upload(path=path_temp)
                
                # Aguarda o Google terminar de indexar o arquivo
                while file_upload.state.name == "PROCESSING":
                    time.sleep(3)
                    file_upload = client.files.get(name=file_upload.name)
                
                conteudos_para_ia.append(file_upload)

        # Instruções de Sistema
        instrucoes = f"""
        Você é o M.A | JUS IA EXPERIENCE. Especialista em {area_direito}.
        Use Google Search para o magistrado '{magistrado}' no '{tribunal}'.
        Retorne estritamente em JSON:
        {{
            "resumo_estrategico": "...", "jurimetria": "...", "resumo_cliente": "...",
            "timeline": [], "vulnerabilidades_contraparte": [], "checklist": [],
            "base_legal": [], "jurisprudencia": [], "doutrina": [], "peca_processual": "..."
        }}
        """
        conteudos_para_ia.append(f"{instrucoes}\n\nFATOS: {fatos_do_caso}")

        # Chamada ao modelo 2.5 Flash (Padrão para conta paga em 2026)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=conteudos_para_ia,
            config=types.GenerateContentConfig(
                temperature=0.1,
                tools=[{"google_search": {}}]
            )
        )

        # Limpeza do JSON (evita erro de coluna 1)
        res_text = response.text.strip().replace("```json", "").replace("```", "").strip()
        return JSONResponse(content=json.loads(res_text))

    except Exception as e:
        print(f"--- ERRO M.A ---: {str(e)}")
        return JSONResponse(content={"erro": str(e)}, status_code=500)
    finally:
        for f in temp_files:
            if os.path.exists(f): os.remove(f)

# --- GERADOR DE DOCX ---

class DadosPeca(BaseModel):
    texto_peca: str
    advogado_nome: Optional[str] = ""
    advogado_oab: Optional[str] = ""
    advogado_endereco: Optional[str] = ""

@app.post("/gerar_docx")
async def gerar_docx(dados: DadosPeca):
    doc = docx.Document()
    for s in doc.sections:
        s.top_margin, s.bottom_margin, s.left_margin, s.right_margin = Cm(3), Cm(2), Cm(3), Cm(2)

    if dados.advogado_nome:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        header = f"{dados.advogado_nome.upper()}\nOAB: {dados.advogado_oab}\n{dados.advogado_endereco}"
        run = p.add_run(header)
        run.font.size, run.font.name, run.italic = Pt(10), 'Times New Roman', True

    for linha in dados.texto_peca.split('\n'):
        if linha.strip():
            para = doc.add_paragraph(linha.strip())
            para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
            para.paragraph_format.first_line_indent = Cm(2.0)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": "attachment; filename=MA_Estrategia.docx"})
