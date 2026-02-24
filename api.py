import os
import io
import json
import time
import uuid
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, Request
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import List, Optional
import docx
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from google import genai
from google.genai import types

# --- SCHEMAS ---
class SchemaTimeline(BaseModel):
    data: str
    evento: str

class SchemaRespostaIA(BaseModel):
    resumo_estrategico: str
    jurimetria: str
    resumo_cliente: str
    timeline: List[SchemaTimeline]
    vulnerabilidades_contraparte: List[str]
    checklist: List[str]
    base_legal: List[str]
    jurisprudencia: List[str]
    doutrina: List[str]
    peca_processual: str 

class DadosPeca(BaseModel):
    texto_peca: str
    advogado_nome: Optional[str] = ""
    advogado_oab: Optional[str] = ""
    advogado_endereco: Optional[str] = ""

app = FastAPI()
TASKS = {}

def extrair_json_seguro(texto_bruto):
    texto = texto_bruto.strip()
    if texto.startswith("```json"): texto = texto[7:]
    elif texto.startswith("```"): texto = texto[3:]
    if texto.endswith("```"): texto = texto[:-3]
    texto = texto.strip()
    try:
        return json.loads(texto, strict=False)
    except json.JSONDecodeError:
        for sufixo in ['"', '"]', '"}', '"]}', ']}', '}']:
            try: return json.loads(texto + sufixo, strict=False)
            except: continue
        raise Exception("Erro na formatação da resposta. Tente novamente.")

@app.get("/")
def serve_index():
    return FileResponse("index.html")

def processar_background(task_id: str, fatos: str, area: str, mag: str, trib: str, caminhos: list):
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        parts = []

        for path in caminhos:
            f = client.files.upload(file=path, config={'mime_type': 'application/pdf'})
            while client.files.get(name=f.name).state.name != "ACTIVE":
                time.sleep(3)
            parts.append(types.Part.from_uri(file_uri=f.uri, mime_type='application/pdf'))

        sys_instr = f"Você é o M.A JUS IA. Especialidade: {area}. Responda apenas em JSON com aspas simples nos textos."
        prompt = f"ESTRATÉGIA:\n{fatos}\n\nJuízo: {mag} | Vara: {trib}"
        
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=parts + [prompt],
            config=types.GenerateContentConfig(
                system_instruction=sys_instr,
                temperature=0.2,
                max_output_tokens=8192,
                response_mime_type="application/json",
                response_schema=SchemaRespostaIA
            )
        )
        TASKS[task_id] = {"status": "done", "resultado": extrair_json_seguro(response.text)}
    except Exception as e:
        TASKS[task_id] = {"status": "error", "erro": str(e)}
    finally:
        for p in caminhos:
            if os.path.exists(p): os.remove(p)

@app.post("/analisar")
async def analisar(
    background_tasks: BackgroundTasks,
    fatos_do_caso: str = Form(...),
    area_direito: str = Form("Direito Criminal"),
    magistrado: str = Form(""),
    tribunal: str = Form(""),
    arquivos: Optional[List[UploadFile]] = File(None)
):
    task_id = str(uuid.uuid4())
    TASKS[task_id] = {"status": "processing"}
    caminhos = []
    if arquivos:
        for arq in arquivos:
            tmp = f"temp_{uuid.uuid4().hex}.pdf"
            content = await arq.read() # Correção para leitura assíncrona
            with open(tmp, "wb") as f: f.write(content)
            caminhos.append(tmp)
    background_tasks.add_task(processar_background, task_id, fatos_do_caso, area_direito, magistrado, tribunal, caminhos)
    return {"task_id": task_id}

@app.get("/status/{task_id}")
def status(task_id: str):
    return TASKS.get(task_id, {"status": "error", "erro": "ID inválido"})

@app.post("/gerar_docx")
async def gerar_docx(dados: DadosPeca):
    doc = docx.Document()
    for s in doc.sections: s.top_margin, s.bottom_margin = Cm(3), Cm(2)
    
    if dados.advogado_nome:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r = p.add_run(f"{dados.advogado_nome.upper()}\nOAB: {dados.advogado_oab}\n{dados.advogado_endereco}")
        r.font.size, r.font.name, r.italic = Pt(10), 'Times New Roman', True

    texto = dados.texto_peca.replace('\\n', '\n')
    for linha in texto.split('\n'):
        if linha.strip():
            para = doc.add_paragraph(linha.strip())
            para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            para.paragraph_format.first_line_indent = Cm(2.0)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": "attachment; filename=MA_Dossie.docx"})
