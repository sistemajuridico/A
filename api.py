import os
import io
import json
import shutil
import time
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

# --- ROTA DE ENTRADA ---

@app.get("/")
def serve_index():
    """Serve o ficheiro index.html na raiz do servidor"""
    return FileResponse("index.html")

# --- UTILITÁRIOS DE TRATAMENTO (Importação Local para RAM) ---

def comprimir_video(input_path, output_path):
    try:
        from moviepy.editor import VideoFileClip
        with VideoFileClip(input_path) as video:
            video_redimensionado = video.resize(height=480)
            video_redimensionado.write_videofile(output_path, fps=15, codec="libx264", audio_codec="aac", logger=None)
        return True
    except Exception as e:
        print(f"Erro vídeo: {e}")
        return False

def comprimir_audio(input_path, output_path):
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(input_path)
        audio = audio.set_channels(1).set_frame_rate(16000)
        audio.export(output_path, format="mp3", bitrate="64k")
        return True
    except Exception as e:
        print(f"Erro áudio: {e}")
        return False

# --- MOTOR DE INTELIGÊNCIA JURÍDICA ELITE ---

# CORREÇÃO 422: arquivos agora tem default=[] para evitar erro de validação
# CORREÇÃO ASYNC: Removido 'async' para o servidor não congelar em uploads longos
@app.post("/analisar")
def analisar_caso(
    fatos_do_caso: str = Form(...),
    area_direito: str = Form(...),
    magistrado: Optional[str] = Form(None),
    tribunal: Optional[str] = Form(None),
    arquivos: List[UploadFile] = File(default=[])
):
    temp_files_to_clean = []
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return JSONResponse(content={"erro": "Chave API não configurada."}, status_code=500)

        client = genai.Client(api_key=api_key)
        conteudos_multimais = []

        if arquivos:
            for arquivo in arquivos:
                if not arquivo.filename: continue
                ext = arquivo.filename.lower().split('.')[-1]
                temp_input = f"temp_in_{int(time.time())}_{arquivo.filename}"
                temp_files_to_clean.append(temp_input)
                
                # Salvamento por Streaming (Proteção de RAM)
                with open(temp_input, "wb") as buffer:
                    shutil.copyfileobj(arquivo.file, buffer)

                target_file = temp_input
                mime = "application/pdf"
                
                if ext == "pdf":
                    mime = "application/pdf"
                elif ext in ["mp4", "mpeg", "mov", "avi"]:
                    mime = "video/mp4"
                    temp_output = f"comp_{int(time.time())}_{arquivo.filename}"
                    if comprimir_video(temp_input, temp_output):
                        target_file = temp_output
                        temp_files_to_clean.append(temp_output)
                elif ext in ["mp3", "wav", "m4a", "ogg"]:
                    mime = "audio/mp3"
                    temp_output = f"comp_{int(time.time())}_{arquivo.filename}"
                    if comprimir_audio(temp_input, temp_output):
                        target_file = temp_output
                        temp_files_to_clean.append(temp_output)

                # CORREÇÃO SDK: Uso do parâmetro 'file=' em vez de 'path='
                gemini_file = client.files.upload(file=target_file, config={'mime_type': mime})
                
                # Loop de processamento seguro (Roda em thread separada pelo FastAPI)
                while True:
                    f_info = client.files.get(name=gemini_file.name)
                    if f_info.state.name == "FAILED":
                        raise Exception(f"A IA falhou ao ler {arquivo.filename}. Verifique se o arquivo está corrompido.")
                    if f_info.state.name != "PROCESSING": 
                        break
                    time.sleep(2)
                conteudos_multimais.append(f_info)

        instrucoes_sistema = f"""
        Você é o M.A | JUS IA EXPERIENCE. Especialidade: {area_direito}.
        Use Google Search para o magistrado '{magistrado}' no '{tribunal}'.
        RETORNE ESTRITAMENTE EM JSON:
        {{
            "resumo_estrategico": "...", "jurimetria": "...", "resumo_cliente": "...",
            "timeline": [], "vulnerabilidades_contraparte": [], "checklist": [],
            "base_legal": [], "jurisprudencia": [], "doutrina": [], "peca_processual": "..."
        }}
        """
        prompt_partes = [f"{instrucoes_sistema}\n\nFATOS:\n{fatos_do_caso}"]
        prompt_partes.extend(conteudos_multimais)

        # Gemini 2.5 Flash para máxima estabilidade em 2026
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=prompt_partes,
            config=types.GenerateContentConfig(temperature=0.1, tools=[{"google_search": {}}])
        )

        # Limpeza de Markdown (Evita Erro de Parsing JSON)
        texto_puro = response.text.strip()
        if texto_puro.startswith("```json"):
            texto_puro = texto_puro.replace("```json", "", 1)
        if texto_puro.endswith("```"):
            texto_puro = texto_puro.rsplit("```", 1)[0]
            
        return JSONResponse(content=json.loads(texto_puro.strip()))

    except Exception as e:
        print(f"--- ERRO M.A ---: {str(e)}")
        return JSONResponse(content={"erro": str(e)}, status_code=500)
    finally:
        for f in temp_files_to_clean:
            if os.path.exists(f): os.remove(f)

# --- GERADOR DE WORD PROFISSIONAL ---

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
        return JSONResponse(content={"erro": str(e)}, status_code=500)
