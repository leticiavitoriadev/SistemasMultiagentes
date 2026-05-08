from langchain_community.llms import Ollama
from google_calendar import buscar_eventos
from typing import TypedDict
from langgraph.graph import StateGraph, END
from fastapi import FastAPI
from pydantic import BaseModel


#LLM local
llm = Ollama(model='llama3')

#Estrutura os da memoria utilizaada no fluxo
class Memoria(TypedDict):
    mensagem: str
    resposta: str

#Agentes
def agente_conversa(memoria):
    pergunta = memoria['mensagem']

    resultado = llm.invoke(
        f'Converse naturalmente sobre: {pergunta}'
    )
    return{'resposta': resultado}

def agente_agenda(memoria):
    print('AGENTE AGENDA ATIVADO')

    eventos = buscar_eventos()
    return{'resposta': eventos}

def agente_pesquisa(memoria):
    pergunta = memoria['mensagem']
 
    resultado = llm.invoke(
        f'''
        Pesquise de forma detalhada e explique sobre:
 
        {pergunta}
        '''
    )
    return {'resposta': resultado}

#Supervisor que decide qual agente utilziar
def supervisor(memoria):
    texto = memoria['mensagem'].lower()

    if any(palavra in texto for palavra in ['agenda', 'hoje', 'amanhã', 'evento']):
        return 'agenda'
    
    elif '?' in texto:
        return 'pesquisa'
    
    return 'conversa'

#Fluxo
workflow = StateGraph(Memoria)


workflow.add_node('pesquisa', agente_pesquisa)
workflow.add_node('conversa', agente_conversa)
workflow.add_node('agenda', agente_agenda)
workflow.add_node('supervisor', lambda x: x)

#Inicia no supervisor
workflow.set_entry_point("supervisor")

workflow.add_conditional_edges(
    'supervisor',
    supervisor,
    {
        'pesquisa': 'pesquisa',
        'conversa': 'conversa',
        'agenda': 'agenda'        
    }
)

workflow.add_edge('pesquisa', END)
workflow.add_edge('conversa', END)
workflow.add_edge('agenda', END)

graph = workflow.compile()

#Cria a aplicacao da API
app = FastAPI()

class Mensagem(BaseModel):
    texto: str

@app.post('/chat')
def chat(msg: Mensagem):
    #Remove prefixo "!bot" caso venha na mensagem
    texto_limpo = msg.texto.lower().replace('!bot', '').strip()
 
    resultado = graph.invoke({
        'mensagem': texto_limpo
    })
 
    return {'resposta': resultado['resposta']}