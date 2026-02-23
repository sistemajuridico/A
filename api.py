import os
import io
import json
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

# --- INTERFACE ---

@app.get("/")
async def serve_index():
    return FileResponse("index.html")

# --- MOTOR DE INTELIGÊNCIA JURÍDICA (ESTRATÉGIA DE ELITE) ---

@app.post("/analisar")
async def analisar_caso(
    fatos_do_caso: str = Form(...),
    area_direito: str = Form(...),
    magistrado: str = Form(None),
    tribunal: str = Form(None),
    arquivos: List[UploadFile] = None
):
    temp_files = [] # Para limpeza posterior
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return JSONResponse(content={"erro": "Chave API não configurada."}, status_code=500)

        client = genai.Client(api_key=api_key)
        conteudos_para_ia = []

       # 1. PROCESSAMENTO DE ARQUIVOS (ULTRA EFICIENTE EM RAM)
        if arquivos:
            for arquivo in arquivos:
                if not arquivo.filename: continue
                
                path_temp = f"upload_{int(time.time())}_{arquivo.filename}"
                
                # EM VEZ DE .read(), usamos um buffer para salvar direto no disco
                with open(path_temp, "wb") as buffer:
                    while True:
                        chunk = await arquivo.read(1024 * 1024) # Lê 1MB por vez
                        if not chunk: break
                        buffer.write(chunk)
                
                temp_files.append(path_temp)

                # Envia para o Google (que tem memória ilimitada para ler o arquivo)
                file_upload = client.files.upload(path=path_temp)
                
                while file_upload.state.name == "PROCESSING":
                    time.sleep(2)
                    file_upload = client.files.get(name=file_upload.name)
                
                conteudos_para_ia.append(file_upload)

        # 2. INSTRUÇÕES DO SISTEMA
        instrucoes = f"""
        Você é o M.A | JUS IA EXPERIENCE, a inteligência jurídica de elite.
        ÁREA: {area_direito}. JUIZ: {magistrado}. TRIBUNAL: {tribunal}.
        
        MISSÃO:
        - Use Google Search para pesquisar precedentes reais e o perfil do magistrado.
        - Analise os documentos anexados com rigor técnico.
        - Gere uma petição moderna (Visual Law) e um resumo para o cliente.
        
        RETORNE ESTRITAMENTE EM JSON:
        {{
            "resumo_estrategico": "...", "jurimetria": "...", "resumo_cliente": "...",
            "timeline": [], "vulnerabilidades_contraparte": [], "checklist": [],
            "base_legal": [], "jurisprudencia": [], "doutrina": [], "peca_processual": "..."
        }}
        """

        conteudos_para_ia.append(f"{instrucoes}\n\nFATOS DO CASO: {fatos_do_caso}")

        # 3. CHAMADA DA IA COM BUSCA ATIVA
        # Usamos o modelo 2.5 Flash, que é o padrão reconhecido para sua conta paga
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=conteudos_para_ia,
            config=types.GenerateContentConfig(
                temperature=0.1,
                tools=[{"google_search": {}}]
            )
        )

        # 4. LIMPEZA E TRATAMENTO DO JSON
        texto_limpo = response.text.strip()
        if texto_limpo.startswith("```json"):
            texto_limpo = texto_limpo.replace("```json", "", 1)
        if texto_limpo.endswith("```"):
            texto_limpo = texto_limpo.rsplit("```", 1)[0]
        
        return JSONResponse(content=json.loads(texto_limpo.strip()))

    except Exception as e:
        print(f"--- ERRO CRÍTICO NO M.A ---: {str(e)}")
        return JSONResponse(content={"erro": str(e)}, status_code=500)
    
    finally:
        # Limpa os arquivos temporários do servidor Render
        for f in temp_files:
            if os.path.exists(f): os.remove(f)

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
        s.top_margin, s.bottom_margin = Cm(3), Cm(2)
        s.left_margin, s.right_margin = Cm(3), Cm(2)

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
