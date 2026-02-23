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

# --- FERRAMENTAS DE COMPRESSÃO (Otimizadas para Render Free) ---

def extrair_texto_pdf(file_bytes):
    """Extrai texto de documentos PDF"""
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
    """Reduz vídeo para caber nos 512MB de RAM do Render"""
    try:
        with VideoFileClip(input_path) as video:
            video_redimensionado = video.resize(height=480)
            video_redimensionado.write_videofile(output_path, fps=15, codec="libx264", audio_codec="aac", logger=None)
        return True
    except Exception as e:
        print(f"Erro Vídeo: {e}")
        return False

def comprimir_audio(input_path, output_path):
    """Otimiza áudio para análise de IA"""
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
        # CAPTURA DA CHAVE CONFIGURADA NO RENDER
        api_key = os.getenv("GEMINI_API_KEY")
        
        if not api_key:
            return JSONResponse(content={"erro": "Configure a GEMINI_API_KEY no painel do Render."}, status_code=500)

        conteudos_multimais = []
        texto_autos = ""

        # PROCESSAMENTO DE ANEXOS
        if arquivos:
            for arquivo in arquivos:
                ext = arquivo.filename.lower().split('.')[-1]
                corpo = await arquivo.read()
                
                temp_in = f"in_{arquivo.filename}"
                temp_out = f"proc_{arquivo.filename}"
                
                with open(temp_in, "wb") as f:
                    f.write(corpo)

                if ext == "pdf":
                    texto_autos += f"\n[ARQUIVO: {arquivo.filename}]\n{extrair_texto_pdf(corpo)}"
                
                elif ext in ["mp4", "mov", "avi"]:
                    if comprimir_video(temp_in, temp_out):
                        with open(temp_out, "rb") as f:
                            conteudos_multimais.append(types.Part.from_bytes(data=f.read(), mime_type="video/mp4"))
                
                elif ext in ["mp3", "wav", "m4a"]:
                    if comprimir_audio(temp_in, temp_out):
                        with open(temp_out, "rb") as f:
                            conteudos_multimais.append(types.Part.from_bytes(data=f.read(), mime_type="audio/mp3"))

                # Limpeza de arquivos temporários
                for f_temp in [temp_in, temp_out]:
                    if os.path.exists(f_temp): os.remove(f_temp)

        # INICIALIZAÇÃO DO CLIENTE GOOGLE GENAI 0.2.0
        client = genai.Client(api_key=api_key)

        # --- BLOCO DE DIAGNÓSTICO (LISTAGEM DE MODELOS NOS LOGS) ---
        print("--- [DIAGNÓSTICO M.A] MODELOS DISPONÍVEIS NA SUA CONTA PAGA ---")
        try:
            for m in client.models.list():
                print(f"Disponível: {m.name}")
        except Exception as d_err:
            print(f"Falha ao listar modelos: {d_err}")
        # -----------------------------------------------------------

        instrucoes_juridicas = f"""
        Você é o M.A | JUS IA EXPERIENCE, a inteligência jurídica de elite para {area_direito}.
        
        TAREFAS DE ALTO NÍVEL:
        1. JURIMETRIA: Use Google Search para analisar o magistrado '{magistrado}' no '{tribunal}'.
        2. ESTRATÉGIA: Identifique falhas na narrativa da contraparte e aponte teses vencedoras.
        3. VISUAL LAW: Crie uma petição persuasiva, moderna e pronta para o protocolo.

        RESPOSTA OBRIGATÓRIA EM JSON:
        {{
            "resumo_estrategico": "Análise técnica profunda",
            "jurimetria": "Comportamento do juiz/tribunal",
            "resumo_cliente": "Explicação simples para WhatsApp",
            "timeline": [{{ "data": "DD/MM/AAAA", "evento": "descrição" }}],
            "vulnerabilidades_contraparte": ["Ponto A", "Ponto B"],
            "checklist": ["Ação 1", "Ação 2"],
            "base_legal": ["Artigos fundamentais"],
            "jurisprudencia": ["Precedentes reais"],
            "doutrina": ["Autores de peso"],
            "peca_processual": "Texto completo da petição"
        }}
        """

        prompt_final = [f"{instrucoes_juridicas}\n\nAUTOS EXTRAÍDOS:\n{texto_autos}\n\nFATOS NARRADOS:\n{fatos_do_caso}"]
        prompt_final.extend(conteudos_multimais)

        # MOTOR DE ELITE ATUALIZADO PARA 2026 (EVITA ERRO 404)
        response = client.models.generate_content(
            model='gemini-2.5-flash', # O padrão de estabilidade para novas contas pagas em 2026
            contents=prompt_final,
            config=types.GenerateContentConfig(
                temperature=0.1,
                tools=[{"google_search": {}}]
            )
        )

        return JSONResponse(content=json.loads(response.text))

    except Exception as e:
        # IMPRIME O ERRO REAL NOS LOGS DO RENDER PARA ANÁLISE
        print(f"--- ERRO DETECTADO NO M.A ---: {str(e)}")
        return JSONResponse(content={"erro": str(e)}, status_code=500)

# --- GERADOR DE DOCUMENTOS WORD ---

class DadosPeca(BaseModel):
    texto_peca: str
    advogado_nome: Optional[str] = ""
    advogado_oab: Optional[str] = ""
    advogado_endereco: Optional[str] = ""

@app.post("/gerar_docx")
async def gerar_docx(dados: DadosPeca):
    doc = docx.Document()
    # Padrão de Margens Jurídicas
    for s in doc.sections:
        s.top_margin, s.bottom_margin = Cm(3), Cm(2)
        s.left_margin, s.right_margin = Cm(3), Cm(2)

    if dados.advogado_nome:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        header = f"{dados.advogado_nome.upper()}\nOAB: {dados.advogado_oab}\n{dados.advogado_endereco}"
        run = p.add_run(header)
        run.font.size, run.font.name = Pt(10), 'Times New Roman'
        run.italic = True

    for linha in dados.texto_peca.split('\n'):
        if linha.strip():
            para = doc.add_paragraph(linha.strip())
            para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
            para.paragraph_format.first_line_indent = Cm(2.0)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": "attachment; filename=MA_Estrategia_Elite.docx"})
