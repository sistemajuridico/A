import os
import io
import json
import shutil
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

app = FastAPI()

MAX_UPLOAD_SIZE = 300 * 1024 * 1024  

@app.middleware("http")
async def limit_upload_size(request: Request, call_next):
    if request.method == "POST":
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_UPLOAD_SIZE:
            return JSONResponse(
                {"erro": "A soma total dos ficheiros excede 300MB. Envie menos volumes por vez."},
                status_code=413
            )
    return await call_next(request)

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

def processar_background(task_id: str, fatos: str, area: str, mag: str, trib: str, arquivos_brutos: list):
    arquivos_para_gemini = []
    try:
        for temp_input, ext, safe_name in arquivos_brutos:
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
                    
            arquivos_para_gemini.append((target_file, mime))

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            TASKS[task_id] = {"status": "error", "erro": "Chave API não configurada."}
            return

        client = genai.Client(api_key=api_key)
        conteudos_multimais = []

        for target_file, mime in arquivos_para_gemini:
            gemini_file = client.files.upload(file=target_file, config={'mime_type': mime})
            while True:
                f_info = client.files.get(name=gemini_file.name)
                state_str = str(f_info.state).upper()
                if "FAILED" in state_str:
                    raise Exception("A IA falhou ao processar o ficheiro nos servidores da Google.")
                if "ACTIVE" in state_str:
                    break
                time.sleep(3)
            
            conteudos_multimais.append(
                types.Part.from_uri(file_uri=f_info.uri, mime_type=mime)
            )

        instrucao_sistema = f"""
        Você é o M.A | JUS IA EXPERIENCE, um Advogado de Elite e Doutrinador. Especialidade: {area}.
        
        REGRA DE OURO E INEGOCIÁVEL: O documento PDF enviado é APENAS MATERIAL DE CONSULTA.
        VOCÊ ESTÁ TERMINANTEMENTE PROIBIDO DE COPIAR OU TRANSCREVER PEÇAS EXISTENTES NO PDF.

        ARQUITETURA DE PENSAMENTO (SIGA ESTA ORDEM):
        1. Leia o PDF e extraia os fatos crus.
        2. Preencha 'resumo_estrategico', 'timeline' e 'vulnerabilidades_contraparte'.
        3. Preencha 'base_legal', 'jurisprudencia' e 'doutrina'.

        REGRA ABSOLUTA DE FORMATAÇÃO (ANTI-ERRO JSON):
        - NUNCA use aspas duplas (" ") dentro do texto das suas respostas, substitua SEMPRE por aspas simples (' ').
        """
        
        prompt_comando = f"FATOS NOVOS E DIRECIONAMENTO DO ADVOGADO:\n{fatos}\n\nINFORMAÇÕES DO JUÍZO:\nMagistrado: {mag}\nTribunal/Vara: {trib}\n\nCrie a estratégia processual baseada nestes direcionamentos."

        prompt_partes = []
        prompt_partes.extend(conteudos_multimais)
        prompt_partes.append(prompt_comando)

        filtros_seguranca = [
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
        ]

        config_ia_kwargs = dict(
            system_instruction=instrucao_sistema,
            temperature=0.35, 
            max_output_tokens=8192, 
            response_mime_type="application/json",
            response_schema=SchemaRespostaIA, 
            safety_settings=filtros_seguranca
        )
        
        if len(conteudos_multimais) == 0:
            config_ia_kwargs["tools"] = [{"googleSearch": {}}]
            
        config_ia = types.GenerateContentConfig(**config_ia_kwargs)

        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=prompt_partes,
            config=config_ia
        )

        if getattr(response, 'text', None) is None:
            motivo = "A Google bloqueou a resposta silenciosamente."
            if hasattr(response, 'candidates') and response.candidates and hasattr(response.candidates[0], 'finish_reason'):
                motivo = f"A IA recusou-se a gerar o texto. Motivo oficial: {response.candidates[0].finish_reason}"
            raise Exception(motivo)

        texto_puro = response.text.strip()
        if texto_puro.startswith("```json"):
            texto_puro = texto_puro[7:]
        elif texto_puro.startswith("```"):
            texto_puro = texto_puro[3:]
        if texto_puro.endswith("```"):
            texto_puro = texto_puro[:-3]
            
        texto_puro = texto_puro.strip()
        
        dados_json = json.loads(texto_puro, strict=False)

        TASKS[task_id] = {"status": "done", "resultado": dados_json}

    except Exception as e:
        erro_seguro = str(e).encode('ascii', 'ignore').decode('ascii')
        TASKS[task_id] = {"status": "error", "erro": f"Erro interno ou formatação corrompida: {erro_seguro}"}
    finally:
        for f, m in arquivos_para_gemini:
            if os.path.exists(f): os.remove(f)

@app.post("/analisar")
async def analisar_caso(
    background_tasks: BackgroundTasks,
    fatos_do_caso: str = Form(default=""),
    area_direito: str = Form(default=""),
    magistrado: str = Form(default=""),
    tribunal: str = Form(default=""),
    arquivos: Optional[List[UploadFile]] = File(default=[])
):
    fatos_limpos = unicodedata.normalize('NFC', fatos_do_caso) if fatos_do_caso else ""
    mag_limpo = unicodedata.normalize('NFC', magistrado) if magistrado else ""
    trib_limpo = unicodedata.normalize('NFC', tribunal) if tribunal else ""

    if not fatos_limpos or len(fatos_limpos.strip()) < 5:
        return JSONResponse(content={"erro": "Descreva os fatos."}, status_code=400)

    task_id = str(uuid.uuid4())
    TASKS[task_id] = {"status": "processing"}

    arquivos_brutos = []
    try:
        if arquivos:
            for arquivo in arquivos:
                if not arquivo.filename: continue
                ext = arquivo.filename.lower().split('.')[-1]
                safe_name = f"doc_{uuid.uuid4().hex}.{ext}"
                temp_input = f"temp_in_{safe_name}"
                
                with open(temp_input, "wb") as buffer:
                    while True:
                        chunk = await arquivo.read(1024 * 1024)
                        if not chunk:
                            break
                        buffer.write(chunk)
                
                arquivos_brutos.append((temp_input, ext, safe_name))
                
    except Exception as e:
        return JSONResponse(content={"erro": "Erro de codificação ao salvar o arquivo."}, status_code=500)

    background_tasks.add_task(processar_background, task_id, fatos_limpos, area_direito, mag_limpo, trib_limpo, arquivos_brutos)
    
    return JSONResponse(content={"task_id": task_id})

@app.get("/status/{task_id}")
def check_status(task_id: str):
    task = TASKS.get(task_id)
    if not task:
        return JSONResponse(content={"status": "error", "erro": "Tarefa perdida."})
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
            run_h = p.add_run(f"{str(dados.advogado_nome).upper()}\nOAB: {dados.advogado_oab if dados.advogado_oab else '---'}\n{dados.advogado_endereco if dados.advogado_endereco else ''}")
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
