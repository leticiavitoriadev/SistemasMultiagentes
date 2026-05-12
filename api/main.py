from typing import TypedDict
from langgraph.graph import StateGraph, END
from agentes import *
from google_calendar import buscar_eventos, criar_evento, alterar_evento, deletar_evento, buscar_evento_por_titulo

app = FastAPI()
 
 
class Mensagem(BaseModel):
    texto: str
 
 
@app.post('/chat')
def chat(msg: Mensagem):
    # Remove prefixo "!bot" caso venha na mensagem
    texto_limpo = msg.texto.lower().replace('!bot', '').strip()
 
    resultado = graph.invoke({
        'mensagem': texto_limpo
    })
 
    return {'resposta': resultado['resposta']}