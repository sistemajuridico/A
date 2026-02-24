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

# --- SCHEMAS DE DADOS ---
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

# --- MOTOR DE REPARO DE JSON ---
def extrair_json_seguro(texto_bruto):
    texto = texto_bruto.strip()
    if texto.startswith("```json"): texto = texto[7:]
    elif texto.startswith("```"): texto = texto[3:]
    if texto.endswith("```"): texto = texto[:-3]
    texto = texto.strip()

    try:
        return json.loads(texto, strict=False)
    except json.JSONDecodeError:
        # Tenta fechar chaves cortadas por limite de tokens
        for sufixo in ['"', '"]', '"}', '"]}', ']}', '}']:
            try:
                return json.loads(texto + sufixo, strict=False)
            except:
                continue
        raise Exception("A resposta da IA foi excessivamente longa e o JSON quebrou. Tente simplificar o prompt.")

@app.get("/")
def serve_index():
    return FileResponse("index.html")

def processar_background(task_id: str, fatos: str, area: str, mag: str, trib: str, arquivos_brutos: list):
    arquivos_para_gemini = []
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        conteudos_multimais = []

        for target_file in arquivos_brutos:
            gemini_file = client.files.upload(file=target_file, config={'mime_type': 'application/pdf'})
            while True:
                f_info = client.files.get(name=gemini_file.name)
                if str(f_info.state).upper() == "ACTIVE": break
                time.sleep(3)
            conteudos_multimais.append(types.Part.from_uri(file_uri=f_info.uri, mime_type='application/pdf'))

        instrucao_sistema = f"""
        Você é o M.A | JUS IA EXPERIENCE. Especialidade: {area}.
        Responda obrigatoriamente em JSON.
        REGRAS: 
        1. Use apenas aspas simples (') dentro dos textos. 
        2. Use '\\n' para quebras de linha.
        3. Se a peça for longa, priorize a fundamentação jurídica.
        """
        
        prompt_comando = f"ESTRATÉGIA:\n{fatos}\n\nJuízo: {mag} | Vara: {trib}"
        
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            contents=conteudos_multimais + [prompt_comando],
            config=types.GenerateContentConfig(
                system_instruction=instrucao_sistema,
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
        for f in arquivos_brutos:
            if os.path.exists(f): os.remove(f)

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
            if not arq.filename: continue
            tmp = f"temp_{uuid.uuid4().hex}.pdf"
            with open(tmp, "wb") as b: b.write(arq.file.read())
            caminhos.append(tmp)

    background_tasks.add_task(processar_background, task_id, fatos_do_caso, area_direito, magistrado, tribunal, caminhos)
    return {"task_id": task_id}

@app.get("/status/{task_id}")
def status(task_id: str):
    return TASKS.get(task_id, {"status": "error", "erro": "Tarefa não encontrada"})

@app.post("/gerar_docx")
def gerar_docx(dados: DadosPeca):
    doc = docx.Document()
    for s in doc.sections: s.top_margin, s.bottom_margin = Cm(3), Cm(2)
    
    if dados.advogado_nome:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r = p.add_run(f"{dados.advogado_nome.upper()}\nOAB: {dados.advogado_oab}\n{dados.advogado_endereco}")
        r.font.size, r.font.name, r.italic = Pt(10), 'Times New Roman', True

    for linha in dados.texto_peca.replace('\\n', '\n').split('\n'):
        if linha.strip():
            para = doc.add_paragraph(linha.strip())
            para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            para.paragraph_format.first_line_indent = Cm(2.0)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": "attachment; filename=MA_Dossie.docx"})