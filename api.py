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
    api_key: str = Form(...),
    fatos_do_caso: str = Form(...),
    area_direito: str = Form(...),
    magistrado: str = Form(None),
    tribunal: str = Form(None),
    arquivos: List[UploadFile] = None
):
    try:
        conteudos_multimais = []
        texto_autos = ""

        if arquivos:
            for arquivo in arquivos:
                ext = arquivo.filename.lower().split('.')[-1]
                corpo = await arquivo.read()
                
                # Nome de ficheiros temporários
                temp_input = f"temp_in_{arquivo.filename}"
                temp_output = f"comp_{arquivo.filename}"
                
                # Salva o original para processar
                with open(temp_input, "wb") as f:
                    f.write(corpo)

                if ext == "pdf":
                    texto_autos += f"\n[DOC: {arquivo.filename}]\n{extrair_texto_pdf(corpo)}"
                
                elif ext in ["mp4", "mpeg", "mov", "avi"]:
                    # Aplica compressão de vídeo antes de enviar para o Gemini
                    if comprimir_video(temp_input, temp_output):
                        with open(temp_output, "rb") as f:
                            conteudos_multimais.append(types.Part.from_bytes(data=f.read(), mime_type="video/mp4"))
                    else: # Se falhar, tenta enviar o original se não for muito grande
                        conteudos_multimais.append(types.Part.from_bytes(data=corpo, mime_type=arquivo.content_type))
                
                elif ext in ["mp3", "wav", "m4a", "ogg"]:
                    # Aplica compressão de áudio
                    if comprimir_audio(temp_input, temp_output):
                        with open(temp_output, "rb") as f:
                            conteudos_multimais.append(types.Part.from_bytes(data=f.read(), mime_type="audio/mp3"))
                    else:
                        conteudos_multimais.append(types.Part.from_bytes(data=corpo, mime_type=arquivo.content_type))

                # Limpeza imediata de temporários para libertar RAM e Disco
                for f_temp in [temp_input, temp_output]:
                    if os.path.exists(f_temp): os.remove(f_temp)

        # Configura o Cliente Gemini
        client = genai.Client(api_key=api_key)

        # Prompt de Instruções - O Coração do M.A Jus IA Experience
        instrucoes_sistema = f"""
        Você é o M.A | JUS IA EXPERIENCE, a inteligência jurídica de elite no Brasil. 
        Sua especialidade agora é {area_direito}.
        
        MISSÃO ESTRATÉGICA:
        1. JURIMETRIA: Pesquise no Google Search por decisões do magistrado '{magistrado}' no '{tribunal}'. Identifique padrões de julgamento e 'humor' jurídico.
        2. LINHA DO TEMPO: Crie uma cronologia rigorosa. Aponte alertas de prescrição ou datas contraditórias.
        3. MODO COMBATE: Analise documentos da contraparte. Identifique furos na narrativa e sugira a melhor estratégia de réplica.
        4. TRADUÇÃO CLIENTE: Crie um resumo para WhatsApp (sem juridiquês) para o advogado enviar ao cliente.
        5. DOUTRINA E JURISPRUDÊNCIA: Use o Search para encontrar citações REAIS e ementas dos últimos 12 meses.
        6. VISUAL LAW: A petição deve ser moderna, persuasiva e com tópicos bem definidos.

        RETORNE ESTRITAMENTE EM JSON:
        {{
            "resumo_estrategico": "Análise técnica profunda e chances de vitória",
            "jurimetria": "Tendências identificadas do juízo",
            "resumo_cliente": "Texto amigável para WhatsApp",
            "timeline": [{{ "data": "DD/MM/AAAA", "evento": "descrição", "alerta": "opcional" }}],
            "vulnerabilidades_contraparte": ["Ponto 1", "Ponto 2"],
            "checklist": ["Providência 1", "Prova necessária 2"],
            "base_legal": ["Artigos fundamentados"],
            "jurisprudencia": ["Ementas reais e referências"],
            "doutrina": ["Autores e teses"],
            "peca_processual": "Texto completo da petição"
        }}
        """

        prompt_partes = [f"{instrucoes_sistema}\n\nAUTOS TEXTUAIS:\n{texto_autos}\n\nFATOS E INSTRUÇÕES:\n{fatos_do_caso}"]
        prompt_partes.extend(conteudos_multimais)

        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt_partes,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
                tools=[{"google_search": {}}]
            )
        )

        return JSONResponse(content=json.loads(response.text))

    except Exception as e:
        return JSONResponse(content={"erro": str(e)}, status_code=500)

# --- GERADOR DE DOCUMENTO WORD PROFISSIONAL ---

class DadosPeca(BaseModel):
    texto_peca: str
    advogado_nome: Optional[str] = ""
    advogado_oab: Optional[str] = ""
    advogado_endereco: Optional[str] = ""

@app.post("/gerar_docx")
async def gerar_docx(dados: DadosPeca):
    doc = docx.Document()
    
    # Margens Padrão Tribunal (3cm Esq/Sup, 2cm Dir/Inf)
    for s in doc.sections:
        s.top_margin, s.bottom_margin = Cm(3), Cm(2)
        s.left_margin, s.right_margin = Cm(3), Cm(2)

    # Cabeçalho Profissional alinhado à Direita
    if dados.advogado_nome:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        header_text = f"{dados.advogado_nome.upper()}\nOAB: {dados.advogado_oab}\n{dados.advogado_endereco}"
        run_h = p.add_run(header_text)
        run_h.font.size, run_h.font.name = Pt(10), 'Times New Roman'
        run_h.italic = True
        doc.add_paragraph("\n")

    # Formatação do Corpo do Texto (Times New Roman, 12, 1.5)
    style = doc.styles['Normal']
    style.font.name = 'Times New Roman'
    style.font.size = Pt(12)
    
    for linha in dados.texto_peca.split('\n'):
        if linha.strip():
            para = doc.add_paragraph(linha.strip())
            para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
            para.paragraph_format.first_line_indent = Cm(2.0)
            para.paragraph_format.space_after = Pt(6)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    
    return StreamingResponse(
        buffer, 
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": "attachment; filename=Estrategia_MA_Elite.docx"}
    )
