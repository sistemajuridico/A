import os
import io
import json
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import PyPDF2
import docx
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from google import genai
from google.genai import types

app = FastAPI()

# --- UTILITÁRIOS ---

def extrair_texto_pdf(file_bytes):
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

# --- MOTOR JURÍDICO (NÍVEL JUS IA) ---

@app.post("/analisar")
async def analisar_caso(
    api_key: str = Form(...),
    fatos_do_caso: str = Form(...),
    area_direito: str = Form(...),
    arquivos: List[UploadFile] = None
):
    try:
        texto_documentos = ""
        if arquivos:
            for arquivo in arquivos:
                conteudo = await arquivo.read()
                if arquivo.filename.lower().endswith(".pdf"):
                    texto_documentos += f"\n[DOCUMENTO: {arquivo.filename}]\n"
                    texto_documentos += extrair_texto_pdf(conteudo)

        client = genai.Client(api_key=api_key)

        instrucoes_sistema = f"""
        Você é o M.A JURÍDICO, uma IA de alta performance para advogados, operando no nível de Planos Avançados de Pesquisa.
        Sua especialidade atual é {area_direito}.

        MISSÃO:
        1. ANÁLISE DE PROVAS: Identifique lacunas nos fatos narrados ou nos documentos anexados e sugira quais provas (documentais ou testemunhais) o advogado deve buscar.
        2. PESQUISA WEB REAL: Use o Google Search para encontrar acórdãos do último ano. Não aceite alucinações.
        3. ESTRATÉGIA DE DEFESA/ATAQUE: Crie teses subsidiárias caso a principal seja rejeitada.
        4. PEÇA PROCESSUAL DE ELITE: Redija uma petição completa com:
           - Endereçamento e Qualificação (use [NOME COMPLETO] para dados faltantes);
           - Dos Fatos (narrativa lógica e persuasiva);
           - Do Direito (subsunção do fato à norma e jurisprudência);
           - Dos Pedidos (detalhados, incluindo valor da causa e honorários).

        IMPORTANTE: Retorne APENAS um objeto JSON puro.
        Estrutura:
        {{
            "resumo_estrategico": "Análise técnica + Probabilidade de êxito + Sugestão de Provas faltantes",
            "base_legal": ["Artigos comentados"],
            "jurisprudencia": ["Ementas reais e links/referências"],
            "doutrina": ["Citações doutrinárias de peso"],
            "peca_processual": "Texto completo da petição"
        }}
        """

        prompt = f"{instrucoes_sistema}\n\nDOCUMENTOS:\n{texto_documentos}\n\nRELATO DO CASO:\n{fatos_do_caso}"

        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3,
                tools=[{"google_search": {}}]
            )
        )

        return JSONResponse(content=json.loads(response.text))

    except Exception as e:
        return JSONResponse(content={"erro": str(e)}, status_code=500)

# --- GERADOR DE WORD PROFISSIONAL (PADRÃO ABNT/JURÍDICO) ---

class DadosPeca(BaseModel):
    texto_peca: str
    advogado_nome: Optional[str] = ""
    advogado_oab: Optional[str] = ""
    advogado_endereco: Optional[str] = ""

@app.post("/gerar_docx")
async def gerar_docx(dados: DadosPeca):
    doc = docx.Document()
    
    # Configuração de Margens (Padrão Petição)
    sections = doc.sections
    for section in sections:
        section.top_margin = Cm(3)
        section.bottom_margin = Cm(2)
        section.left_margin = Cm(3)
        section.right_margin = Cm(2)

    # Cabeçalho Elegante
    if dados.advogado_nome:
        header_table = doc.add_table(rows=1, cols=1)
        header_table.width = Cm(16)
        cell = header_table.rows[0].cells[0]
        
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run_name = p.add_run(dados.advogado_nome.upper())
        run_name.bold = True
        run_name.font.size = Pt(12)
        run_name.font.name = 'Times New Roman'
        
        p_info = cell.add_paragraph()
        p_info.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        info_text = f"OAB: {dados.advogado_oab}\n{dados.advogado_endereco}"
        run_info = p_info.add_run(info_text)
        run_info.font.size = Pt(8)
        run_info.italic = True
        run_info.font.name = 'Times New Roman'
        
        doc.add_paragraph("\n")

    # Formatação do Texto da Peça
    style = doc.styles['Normal']
    style.font.name = 'Times New Roman'
    style.font.size = Pt(12)
    
    paragrafos = dados.texto_peca.split('\n')
    for p_text in paragrafos:
        if p_text.strip():
            para = doc.add_paragraph(p_text.strip())
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
        headers={"Content-Disposition": f"attachment; filename=MA_Peca_Profissional.docx"}
    )
