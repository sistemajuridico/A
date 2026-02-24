import os
import io
import json
import time
import uuid
import unicodedata
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, Request
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import List, Optional
import docx
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from google import genai
from google.genai import types

# --- SEU SCHEMA COM O TRUQUE DO ARRAY ---
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
    peca_processual: List[str] # Mantive sua lógica de Array para evitar quebra de JSON

class DadosPeca(BaseModel):
    texto_peca: str
    advogado_nome: Optional[str] = ""
    advogado_oab: Optional[str] = ""
    advogado_endereco: Optional[str] = ""

app = FastAPI()
TASKS = {}

# ESCUDO DE REPARO (Para garantir que o JSON longo não trave)
def extrair_json_seguro(texto_bruto):
    texto = texto_bruto.strip()
    if texto.startswith("```json"): texto = texto[7:]
    if texto.endswith("```"): texto = texto[:-3]
    texto = texto.strip()
    try:
        return json.loads(texto, strict=False)
    except json.JSONDecodeError:
        for sufixo in ['"', '"]', '"}', '"]}', ']}', '}']:
            try: return json.loads(texto + sufixo, strict=False)
            except: continue
        raise Exception("A resposta foi cortada por ser muito longa. Tente simplificar o prompt.")

@app.get("/")
def serve_index():
    return FileResponse("index.html")

async def processar_background(task_id: str, fatos: str, area: str, mag: str, trib: str, arquivos_brutos: list):
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        conteudos = []

        for target_file in arquivos_brutos:
            gemini_file = client.files.upload(file=target_file, config={'mime_type': 'application/pdf'})
            while client.files.get(name=gemini_file.name).state.name != "ACTIVE":
                time.sleep(3)
            conteudos.append(types.Part.from_uri(file_uri=gemini_file.uri, mime_type='application/pdf'))

        instrucao = f"Você é o M.A JUS IA. Especialidade: {area}. Siga o schema JSON rigorosamente."
        prompt = f"ESTRATÉGIA:\n{fatos}\n\nJuízo: {mag} | Vara: {trib}"

        response = client.models.generate_content(
            model='gemini-3-flash', # Única mudança: Modelo atual de 2026
            contents=conteudos + [prompt],
            config=types.GenerateContentConfig(
                system_instruction=instrucao,
                temperature=0.3,
                max_output_tokens=8192,
                response_mime_type="application/json",
                response_schema=SchemaRespostaIA
            )
        )

        dados_json = extrair_json_seguro(response.text)
        
        # SUA LÓGICA DE RECONSTRUÇÃO: Junta o Array em uma String única para o Frontend
        if isinstance(dados_json.get('peca_processual'), list):
            dados_json['peca_processual'] = '\n\n'.join(dados_json['peca_processual'])

        TASKS[task_id] = {"status": "done", "resultado": dados_json}
    except Exception as e:
        TASKS[task_id] = {"status": "error", "erro": str(e)}
    finally:
        for f in arquivos_brutos:
            if os.path.exists(f): os.remove(f)

@app.post("/analisar")
async def analisar(
    background_tasks: BackgroundTasks,
    fatos_do_caso: str = Form(...),
    area_direito: str = Form(...),
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
            with open(tmp, "wb") as f: f.write(await arq.read())
            caminhos.append(tmp)
    
    background_tasks.add_task(processar_background, task_id, fatos_do_caso, area_direito, magistrado, tribunal, caminhos)
    return {"task_id": task_id}

@app.get("/status/{task_id}")
def check_status(task_id: str):
    return TASKS.get(task_id, {"status": "error", "erro": "Tarefa não encontrada"})

@app.post("/gerar_docx")
def gerar_docx(dados: DadosPeca):
    doc = docx.Document()
    for linha in dados.texto_peca.split('\n'):
        if linha.strip():
            p = doc.add_paragraph(linha.strip())
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": "attachment; filename=MA_Elite.docx"})
