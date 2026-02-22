from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse # <-- Adicionamos o FileResponse aqui
from pydantic import BaseModel
import json
from google import genai
from google.genai import types

# 1. Inicializa a API
app = FastAPI(
    title="M.A API Jurídica", 
    description="Motor de processamento jurídico com IA",
    version="1.0"
)

# 2. Configuração de CORS (Fundamental)
# Isso permite que o seu futuro Front-end (site bonito) consiga "conversar" com esta API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Em produção, colocaremos a URL exata do seu site aqui
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Definição da Estrutura de Dados (O que a API espera receber)
class RequisicaoCaso(BaseModel):
    fatos_do_caso: str
    area_direito: str
    api_key: str
    texto_documentos: str = "" # Opcional, para quando adicionarmos leitura de PDF no front

# 4. Rota Principal de Análise
@app.post("/analisar")
async def analisar_caso(req: RequisicaoCaso):
    try:
        cliente = genai.Client(api_key=req.api_key)
        
        instrucoes_sistema = f"""
        Você é um advogado sênior, jurista renomado e pesquisador especialista em {req.area_direito} no Brasil.
        Sua missão é atuar na ETAPA 1 de um caso: A Pesquisa e Análise Processual Estratégica.
        
        DIRETRIZES OBRIGATÓRIAS:
        1. Responda ESTRITAMENTE em Português do Brasil (PT-BR).
        2. Utilize vernáculo jurídico adequado, formal e profissional.
        
        Responda EXCLUSIVAMENTE em formato JSON com a seguinte estrutura exata:
        {{
            "resumo_estrategico": "...",
            "base_legal": ["..."],
            "jurisprudencia": ["..."],
            "doutrina": ["..."],
            "peca_processual": "..."
        }}
        """

        prompt_completo = f"{instrucoes_sistema}\n\n"
        if req.texto_documentos.strip():
            prompt_completo += f"--- DOCUMENTOS ---\n{req.texto_documentos}\n--- FIM ---\n\n"
        prompt_completo += f"FATOS DO CASO:\n{req.fatos_do_caso}"

        resposta = cliente.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt_completo,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2
            )
        )
        
        return json.loads(resposta.text)

    except Exception as e:
        # Se algo der errado (ex: chave API inválida), a API avisa o Front-end
        raise HTTPException(status_code=500, detail=str(e))

# Rota de teste para ver se o servidor está online
@app.get("/")
def home():
    return {"status": "M.A Motor Jurídico está online e operante."}
