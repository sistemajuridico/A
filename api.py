import os
import io
import json
import shutil
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

app = FastAPI()

# --- 1. MIDDLEWARE DE PROTEÇÃO: Limita o Upload a 50MB ---
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  

@app.middleware("http")
async def limit_upload_size(request: Request, call_next):
    if request.method == "POST":
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_UPLOAD_SIZE:
            return JSONResponse(
                {"erro": "Arquivo muito grande. O limite máximo é de 50MB."},
                status_code=413
            )
    return await call_next(request)

# Dicionário em memória para guardar o status das análises
TASKS = {}

@app.get("/")
def serve_index():
    return FileResponse("index.html")

def comprimir_video(input_path, output_path):
    try:
        from moviepy.editor import VideoFileClip
        with VideoFileClip(input_path) as video:
            video_redimensionado = video.resize(height=480)
            video_redimensionado.write_videofile(output_path, fps=15, codec="libx264", audio_codec="aac", logger=None)
        return True
    except Exception as e:
        return False

def comprimir_audio(input_path, output_path):
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(input_path)
        audio = audio.set_channels(1).set_frame_rate(16000)
        audio.export(output_path, format="mp3", bitrate="64k")
        return True
    except Exception as e:
        return False

# NÚCLEO EM 2º PLANO: Processa a IA fora da ligação principal para evitar Timeout
def processar_background(task_id: str, fatos: str, area: str, mag: str, trib: str, arquivos_salvos: list):
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            TASKS[task_id] = {"status": "error", "erro": "Chave API não configurada."}
            return

        client = genai.Client(api_key=api_key)
        conteudos_multimais = []

        for target_file, mime in arquivos_salvos:
            gemini_file = client.files.upload(file=target_file, config={'mime_type': mime})
            while True:
                f_info = client.files.get(name=gemini_file.name)
                if f_info.state.name == "FAILED":
                    raise Exception("A IA falhou ao ler um dos arquivos. Pode estar corrompido.")
                if f_info.state.name != "PROCESSING": 
                    break
                time.sleep(3)
            conteudos_multimais.append(f_info)

        # PROMPT AGRESSIVO QUE GARANTE A PEÇA COMPLETA
        instrucoes = f"""
        Você é o M.A | JUS IA EXPERIENCE, um Advogado de Elite e Doutrinador. Especialidade: {area}.
        Use Google Search para o magistrado '{mag}' no '{trib}'.
        
        ATENÇÃO MÁXIMA PARA A PEÇA PROCESSUAL: No campo 'peca_processual', você é PROIBIDO de resumir. 
        Você DEVE redigir a PETIÇÃO COMPLETA, EXTENSA e PRONTA PARA PROTOCOLO. 
        Inclua obrigatoriamente: 
        1. Endereçamento correto.
        2. Qualificação completa (use colchetes [ ] para dados faltantes).
        3. Dos Fatos (narrativa persuasiva).
        4. Do Direito (fundamentação profunda conectando lei, doutrina e a jurisprudência pesquisada ao caso concreto).
        5. Dos Pedidos (específicos, claros e com requerimento de provas).
        6. Valor da causa e fecho formal.

        RETORNE ESTRITAMENTE EM JSON COM ESTA ESTRUTURA:
        {{
            "resumo_estrategico": "...", "jurimetria": "...", "resumo_cliente": "...",
            "timeline": [], "vulnerabilidades_contraparte": [], "checklist": [],
            "base_legal": [], "jurisprudencia": [], "doutrina": [], 
            "peca_processual": "TEXTO INTEGRAL E EXTENSO DA PEÇA AQUI..."
        }}
        """
        
        prompt_partes = [f"{instrucoes}\n\nFATOS:\n{fatos}"]
        prompt_partes.extend(conteudos_multimais)

        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=prompt_partes,
            config=types.GenerateContentConfig(temperature=0.1, tools=[{"google_search": {}}])
        )

        texto_puro = response.text.strip()
        if texto_puro.startswith("```json"):
            texto_puro = texto_puro.replace("```json", "", 1)
        if texto_puro.endswith("```"):
            texto_puro = texto_puro.rsplit("```", 1)[0]
            
        TASKS[task_id] = {"status": "done", "resultado": json.loads(texto_puro.strip())}

    except Exception as e:
        TASKS[task_id] = {"status": "error", "erro": "Erro no processamento da IA. O arquivo pode estar protegido ou o modelo demorou demais."}
    finally:
        for f, m in arquivos_salvos:
            if os.path.exists(f): os.remove(f)

# --- 2. LEITURA ASSÍNCRONA EM CHUNKS (async def) ---
@app.post("/analisar")
async def analisar_caso(
    background_tasks: BackgroundTasks,
    fatos_do_caso: str = Form(default=""),
    area_direito: str = Form(default=""),
    magistrado: str = Form(default=""),
    tribunal: str = Form(default=""),
    arquivos: Optional[List[UploadFile]] = File(default=[])
):
    if not fatos_do_caso or len(fatos_do_caso.strip()) < 5:
        return JSONResponse(content={"erro": "Descreva os fatos."}, status_code=400)

    task_id = str(uuid.uuid4())
    TASKS[task_id] = {"status": "processing"}

    arquivos_salvos = []
    try:
        if arquivos:
            for arquivo in arquivos:
                if not arquivo.filename: continue
                ext = arquivo.filename.lower().split('.')[-1]
                
                # Nomes seguros gerados por UUID para contornar erros ASCII de caracteres como 'ç' e 'ã'
                safe_name = f"doc_{uuid.uuid4().hex}.{ext}"
                temp_input = f"temp_in_{safe_name}"
                
                # --- LEITURA DIVIDIDA (A MÁGICA PARA PDFS GRANDES) ---
                # Lê em pedaços de 1MB e liberta a RAM, não bloqueando o servidor
                with open(temp_input, "wb") as buffer:
                    while True:
                        chunk = await arquivo.read(1024 * 1024)
                        if not chunk:
                            break
                        buffer.write(chunk)
                
                target_file = temp_input
                mime = "application/pdf"
                if ext == "pdf": 
                    mime = "application/pdf"
                elif ext in ["mp4", "mpeg", "mov", "avi"]:
                    mime = "video/mp4"
                    temp_output = f"comp_{safe_name}"
                    if comprimir_video(temp_input, temp_output):
                        os.remove(temp_input)
                        target_file = temp_output
                elif ext in ["mp3", "wav", "m4a", "ogg"]:
                    mime = "audio/mp3"
                    temp_output = f"comp_{safe_name}"
                    if comprimir_audio(temp_input, temp_output):
                        os.remove(temp_input)
                        target_file = temp_output
                        
                arquivos_salvos.append((target_file, mime))
                
    except Exception as e:
        return JSONResponse(content={"erro": "Erro de codificação ao salvar o arquivo no servidor."}, status_code=500)

    # Inicia a IA em 2º plano e liberta o frontend de imediato!
    background_tasks.add_task(processar_background, task_id, fatos_do_caso, area_direito, magistrado, tribunal, arquivos_salvos)
    
    return JSONResponse(content={"task_id": task_id})

@app.get("/status/{task_id}")
def check_status(task_id: str):
    task = TASKS.get(task_id)
    if not task:
        return JSONResponse(content={"status": "error", "erro": "Tarefa perdida ou expirada."})
    return JSONResponse(content=task)

class DadosPeca(BaseModel):
    texto_peca: str
    advogado_nome: Optional[str] = ""
    advogado_oab: Optional[str] = ""
    advogado_endereco: Optional[str] = ""

@app.post("/gerar_docx")
def gerar_docx(dados: DadosPeca):
    try:
        doc = docx.Document()
        for s in doc.sections:
            s.top_margin, s.bottom_margin, s.left_margin, s.right_margin = Cm(3), Cm(2), Cm(3), Cm(2)

        if dados.advogado_nome:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            nome = str(dados.advogado_nome).upper()
            oab = str(dados.advogado_oab) if dados.advogado_oab else "---"
            end = str(dados.advogado_endereco) if dados.advogado_endereco else ""
            run_h = p.add_run(f"{nome}\nOAB: {oab}\n{end}")
            run_h.font.size, run_h.font.name, run_h.italic = Pt(10), 'Times New Roman', True

        for linha in dados.texto_peca.split('\n'):
            if linha.strip():
                para = doc.add_paragraph(linha.strip())
                para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
                para.paragraph_format.first_line_indent = Cm(2.0)

        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return StreamingResponse(buffer, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": "attachment; filename=MA_Elite.docx"})
    except Exception as e:
        return JSONResponse(content={"erro": "Erro na geração do arquivo Word."}, status_code=500)
