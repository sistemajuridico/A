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

# Bibliotecas de compressão para otimizar o Render Free
from moviepy.editor import VideoFileClip
from pydub import AudioSegment

app = FastAPI()

# --- ROTA DE ENTRADA ---

@app.get("/")
async def serve_index():
    """Serve o ficheiro index.html na raiz do servidor"""
    return FileResponse("index.html")

# --- UTILITÁRIOS DE TRATAMENTO E COMPRESSÃO ---

def extrair_texto_pdf(file_bytes):
    """Extrai texto de PDFs anexados"""
    texto = ""
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        for page in pdf_reader.pages:
            extraido = page.extract_text()
            if extraido:
                texto += extraido + "\n"
    except Exception as e:
        print(f"Erro na extração de PDF: {e}")
    return texto

def comprimir_video(input_path, output_path):
    """Reduz vídeo para 480p e 15fps para não estourar os 512MB de RAM do Render"""
    try:
        with VideoFileClip(input_path) as video:
            video_redimensionado = video.resize(height=480)
            video_redimensionado.write_videofile(output_path, fps=15, codec="libx264", audio_codec="aac", logger=None)
        return True
    except Exception as e:
        print(f"Erro ao comprimir vídeo: {e}")
        return False

def comprimir_audio(input_path, output_path):
    """Converte áudio para Mono e reduz qualidade para análise de IA"""
    try:
        audio = AudioSegment.from_file(input_path)
        audio = audio.set_channels(1).set_frame_rate(16000)
        audio.export(output_path, format="mp3", bitrate="64k")
        return True
    except Exception as e:
        print(f"Erro ao comprimir áudio: {e}")
        return False

# --- MOTOR DE INTELIGÊNCIA JURÍDICA ELITE ---

@app.post("/analisar")
async def analisar_caso(
    fatos_do_caso: str = Form(...),
    area_direito: str = Form(...),
    magistrado: str = Form(None),
    tribunal: str = Form(None),
    arquivos: List[UploadFile] = None
):
    try:
        # CAPTURA AUTOMÁTICA DA CHAVE DO RENDER
        api_key = os.getenv("GEMINI_API_KEY")
        
        if not api_key:
            print("--- ERRO CRÍTICO ---: Variável GEMINI_API_KEY não encontrada no Render.")
            return JSONResponse(content={"erro": "Chave API não configurada no servidor Render."}, status_code=500)

        conteudos_multimais = []
        texto_autos = ""

        if arquivos:
            for arquivo in arquivos:
                ext = arquivo.filename.lower().split('.')[-1]
                corpo = await arquivo.read()
                
                temp_input = f"temp_in_{arquivo.filename}"
                temp_output = f"comp_{arquivo.filename}"
                
                with open(temp_input, "wb") as f:
                    f.write(corpo)

                if ext == "pdf":
                    texto_autos += f"\n[DOC: {arquivo.filename}]\n{extrair_texto_pdf(corpo)}"
                
                elif ext in ["mp4", "mpeg", "mov", "avi"]:
                    if comprimir_video(temp_input, temp_output):
                        with open(temp_output, "rb") as f:
                            conteudos_multimais.append(types.Part.from_bytes(data=f.read(), mime_type="video/mp4"))
                    else:
                        conteudos_multimais.append(types.Part.from_bytes(data=corpo, mime_type=arquivo.content_type))
                
                elif ext in ["mp3", "wav", "m4a", "ogg"]:
                    if comprimir_audio(temp_input, temp_output):
                        with open(temp_output, "rb") as f:
                            conteudos_multimais.append(types.Part.from_bytes(data=f.read(), mime_type="audio/mp3"))
                    else:
                        conteudos_multimais.append(types.Part.from_bytes(data=corpo, mime_type=arquivo.content_type))

                for f_temp in [temp_input, temp_output]:
                    if os.path.exists(f_temp): os.remove(f_temp)

        client = genai.Client(api_key=api_key)

        instrucoes_sistema = f"""
        Você é o M.A | JUS IA EXPERIENCE, a inteligência jurídica de elite no Brasil. 
        Sua especialidade agora é {area_direito}.
        
        MISSÃO ESTRATÉGICA:
        1. JURIMETRIA: Pesquise no Google Search por decisões do magistrado '{magistrado}' no '{tribunal}'. Identifique padrões de julgamento.
        2. LINHA DO TEMPO: Crie uma cronologia rigorosa. Aponte alertas de prescrição.
        3. MODO COMBATE: Analise documentos da contraparte e identifique furos na narrativa.
        4. TRADUÇÃO CLIENTE: Crie um resumo para WhatsApp explicativo e sem juridiquês.
        5. VISUAL LAW: Petição moderna, persuasiva e escaneável.

        RETORNE ESTRITAMENTE EM JSON:
        {{
            "resumo_estrategico": "Análise técnica",
            "jurimetria": "Tendências do juízo",
            "resumo_cliente": "Texto para WhatsApp",
            "timeline": [{{ "data": "DD/MM/AAAA", "evento": "descrição", "alerta": "opcional" }}],
            "vulnerabilidades_contraparte": ["Ponto 1", "..."],
            "checklist": ["Providência 1", "..."],
            "base_legal": ["Artigos"],
            "jurisprudencia": ["Ementas reais"],
            "doutrina": ["Autores"],
            "peca_processual": "Texto da petição"
        }}
        """

        prompt_partes = [f"{instrucoes_sistema}\n\nAUTOS:\n{texto_autos}\n\nFATOS:\n{fatos_do_caso}"]
        prompt_partes.extend(conteudos_multimais)

       # MODELO ESTÁVEL PARA 2026 (EVITA O ERRO 404 DE MODELO APOSENTADO)
        response = client.models.generate_content(
            model='gemini-1.5-flash', 
            contents=prompt_partes,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
                tools=[{"google_search": {}}]
            )
        )

        return JSONResponse(content=json.loads(response.text))

    except Exception as e:
        # DIAGNÓSTICO PARA LOGS DO RENDER
        print(f"--- ERRO DETECTADO NO M.A ---: {str(e)}")
        return JSONResponse(content={"erro": str(e)}, status_code=500)

# --- GERADOR DE WORD PROFISSIONAL ---

class DadosPeca(BaseModel):
    texto_peca: str
    advogado_nome: Optional[str] = ""
    advogado_oab: Optional[str] = ""
    advogado_endereco: Optional[str] = ""

@app.post("/gerar_docx")
async def gerar_docx(dados: DadosPeca):
    doc = docx.Document()
    # Configuração de Margens de Tribunal
    for s in doc.sections:
        s.top_margin, s.bottom_margin = Cm(3), Cm(2)
        s.left_margin, s.right_margin = Cm(3), Cm(2)

    if dados.advogado_nome:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        header_text = f"{dados.advogado_nome.upper()}\nOAB: {dados.advogado_oab}\n{dados.advogado_endereco}"
        run_h = p.add_run(header_text)
        run_h.font.size, run_h.font.name = Pt(10), 'Times New Roman'
        run_h.italic = True
        doc.add_paragraph("\n")

    for linha in dados.texto_peca.split('\n'):
        if linha.strip():
            para = doc.add_paragraph(linha.strip())
            para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
            para.paragraph_format.first_line_indent = Cm(2.0)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": "attachment; filename=MA_Elite_Estrategia.docx"})
