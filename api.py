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

# Bibliotecas para processamento multimédia
from moviepy.editor import VideoFileClip
from pydub import AudioSegment

app = FastAPI()

# --- ROTAS DE NAVEGAÇÃO ---

@app.get("/")
async def serve_index():
    """Serve a interface principal do M.A"""
    return FileResponse("index.html")

# --- FERRAMENTAS DE TRATAMENTO ---

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

def comprimir_video(input_path, output_path):
    try:
        with VideoFileClip(input_path) as video:
            video_redimensionado = video.resize(height=480)
            video_redimensionado.write_videofile(output_path, fps=15, codec="libx264", audio_codec="aac", logger=None)
        return True
    except Exception as e:
        print(f"Erro Vídeo: {e}")
        return False

def comprimir_audio(input_path, output_path):
    try:
        audio = AudioSegment.from_file(input_path)
        audio = audio.set_channels(1).set_frame_rate(16000)
        audio.export(output_path, format="mp3", bitrate="64k")
        return True
    except Exception as e:
        print(f"Erro Áudio: {e}")
        return False

# --- NÚCLEO DE INTELIGÊNCIA JURÍDICA (ESTRATEGISTA DE ELITE) ---

@app.post("/analisar")
async def analisar_caso(
    fatos_do_caso: str = Form(...),
    area_direito: str = Form(...),
    magistrado: str = Form(None),
    tribunal: str = Form(None),
    arquivos: List[UploadFile] = None
):
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return JSONResponse(content={"erro": "Chave API não configurada no Render."}, status_code=500)

        conteudos_multimais = []
        texto_autos = ""

        if arquivos:
            for arquivo in arquivos:
                ext = arquivo.filename.lower().split('.')[-1]
                corpo = await arquivo.read()
                temp_in, temp_out = f"in_{arquivo.filename}", f"proc_{arquivo.filename}"
                with open(temp_in, "wb") as f: f.write(corpo)

                if ext == "pdf":
                    texto_autos += f"\n[DOC: {arquivo.filename}]\n{extrair_texto_pdf(corpo)}"
                elif ext in ["mp4", "mov", "avi"]:
                    if comprimir_video(temp_in, temp_out):
                        with open(temp_out, "rb") as f:
                            conteudos_multimais.append(types.Part.from_bytes(data=f.read(), mime_type="video/mp4"))
                elif ext in ["mp3", "wav", "m4a"]:
                    if comprimir_audio(temp_in, temp_out):
                        with open(temp_out, "rb") as f:
                            conteudos_multimais.append(types.Part.from_bytes(data=f.read(), mime_type="audio/mp3"))

                for f_temp in [temp_in, temp_out]:
                    if os.path.exists(f_temp): os.remove(f_temp)

        client = genai.Client(api_key=api_key)

        # DIAGNÓSTICO DE MODELOS
        print("--- [DIAGNÓSTICO] MODELOS DISPONÍVEIS ---")
        try:
            for m in client.models.list(): print(f"Disponível: {m.name}")
        except: pass

        instrucoes = f"""
        Você é o M.A | JUS IA EXPERIENCE. Especialidade: {area_direito}.
        Use Google Search para o magistrado '{magistrado}' no '{tribunal}'.
        RETORNE ESTRITAMENTE EM JSON, sem textos explicativos antes ou depois:
        {{
            "resumo_estrategico": "...", "jurimetria": "...", "resumo_cliente": "...",
            "timeline": [], "vulnerabilidades_contraparte": [], "checklist": [],
            "base_legal": [], "jurisprudencia": [], "doutrina": [], "peca_processual": "..."
        }}
        """

        prompt_final = [f"{instrucoes}\n\nAUTOS:\n{texto_autos}\n\nFATOS:\n{fatos_do_caso}"]
        prompt_final.extend(conteudos_multimais)

        # CONFIGURAÇÃO SEM CONFLITO (REMOVEU-SE O RESPONSE_MIME_TYPE)
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=prompt_final,
            config=types.GenerateContentConfig(
                temperature=0.1,
                tools=[{"google_search": {}}]
            )
        )

        # --- LIMPEZA DE JSON (CORRIGE O ERRO DE COLUNA 1) ---
        texto_limpo = response.text.strip()
        if texto_limpo.startswith("```json"):
            texto_limpo = texto_limpo.replace("```json", "", 1)
        if texto_limpo.endswith("```"):
            texto_limpo = texto_limpo.rsplit("```", 1)[0]
        
        return JSONResponse(content=json.loads(texto_limpo.strip()))

    except Exception as e:
        print(f"--- ERRO CRÍTICO NO M.A ---: {str(e)}")
        return JSONResponse(content={"erro": str(e)}, status_code=500)

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
