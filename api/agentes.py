from langchain_community.llms import Ollama
from google_calendar import buscar_eventos, criar_evento, alterar_evento, buscar_evento_por_titulo, deletar_evento
from typing import TypedDict
from langgraph.graph import StateGraph, END
from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime,timedelta,timezone
import json


#LLM local
llm = Ollama(model='llama3')

#Estrutura os da memoria utilizaada no fluxo
class Memoria(TypedDict):
    mensagem: str
    resposta: str
    historico: list[str]    #Manter contexto
    agente_usado: str

#Agentes

def extrair_datas(mensagem: str) -> dict:
    """
    Usa o LLM para interpretar datas em linguagem natural.
    Retorna um dict com data_inicio e data_fim em ISO 8601.
    """

    agora = datetime.now(timezone(timedelta(hours=-3))).isoformat()

    resultado = llm.invoke(f"""
        Hoje é: {agora}
        
        Com base na mensagem abaixo, extraia o período de datas que o usuário quer consultar.
        
        Responda APENAS com um JSON válido, sem explicação, sem markdown, no formato:
        {{"data_inicio": "2024-01-01T00:00:00Z", "data_fim": "2024-01-07T23:59:59Z"}}
        
        Regras:
        - Se o usuário disser "hoje", inicio = começo do dia atual, fim = fim do dia atual
        - Se disser "essa semana", inicio = segunda-feira da semana atual
        - Se disser "semana passada", inicio = segunda da semana anterior, fim = domingo anterior
        - Se disser "daqui X dias", inicio = agora, fim = daqui X dias
        - Se não mencionar período, inicio = agora, fim = daqui 7 dias (padrão)
        
        Mensagem: {mensagem}
    """).strip()
    try:
        limpo = resultado.replace('```json', '').replace('```', '').strip()
        return json.loads(limpo)
    except Exception:
        agora_dt = datetime.now(timezone.utc)
        return {
                'data_inicio': agora_dt.isoformat(),
                'data_fim': (agora_dt + timedelta(days=7)).isoformat()
            }

def extrair_intencao(mensagem: str) -> dict:
    """
    LLM decide o que o usuário quer fazer e extrai os parâmetros necessários.
    """
    agora = datetime.now(timezone(timedelta(hours=-3))).isoformat()

    resultado = llm.invoke(f"""
    Hoje é: {agora}. Fuso horário: America/Fortaleza (UTC-3).

    IMPORTANTE: todas as datas devem usar o offset -03:00, nunca Z.
    Exemplo correto: "2025-05-12T07:00:00-03:00"
    Exemplo errado:  "2025-05-12T07:00:00Z"

    Analise a mensagem e responda APENAS com JSON válido, sem explicação, sem markdown.

    Ações possíveis:
    - "consultar": ver eventos de um período
    - "criar": marcar um novo evento
    - "alterar": modificar um evento existente
    - "deletar": remover um evento

    Formato da resposta:
    {{
        "acao": "consultar" | "criar" | "alterar" | "deletar",
        "titulo": "nome do evento ou null",
        "data_inicio": "ISO 8601 ou null",
        "data_fim": "ISO 8601 ou null",
        "descricao": "descrição ou null",
        "evento_busca": "termo para encontrar o evento a alterar/deletar ou null"
    }}

    Exemplos:
    - "marca reunião amanhã às 14h por 1 hora" → criar, titulo=reunião, datas calculadas
    - "cancela minha consulta de sexta" → deletar, evento_busca=consulta
    - "muda a reunião de amanhã para 16h" → alterar, evento_busca=reunião, nova data_inicio
    - "o que tenho essa semana" → consultar, datas da semana

    Mensagem: {mensagem}
    """).strip()

    try:
        limpo = resultado.replace('```json', '').replace('```', '').strip()
        return json.loads(limpo)
    except Exception:
        return {'acao': 'consultar', 'data_inicio': None, 'data_fim': None}

def agente_agenda(memoria):
    pergunta = memoria['mensagem']

    try:
        intencao = extrair_intencao(pergunta)
        acao = intencao.get('acao', 'consultar')
        print(f'[AGENDA] Ação: {acao} | {intencao}')

        if acao == 'consultar':
            resultado_bruto = buscar_eventos(
                data_inicio=intencao.get('data_inicio'),
                data_fim=intencao.get('data_fim')
            )

        elif acao == 'criar':
            if not intencao.get('titulo') or not intencao.get('data_inicio'):
                return {
                    'resposta': 'Preciso do título e data/hora para criar. Pode dar mais detalhes?',
                    'agente_usado': 'agenda'
                }
            resultado_bruto = criar_evento(
                titulo=intencao['titulo'],
                data_inicio=intencao['data_inicio'],
                data_fim=intencao.get('data_fim', intencao['data_inicio']),
                descricao=intencao.get('descricao', '')
            )

        elif acao == 'alterar':
            eventos = buscar_evento_por_titulo(intencao.get('evento_busca', ''))
            if not eventos:
                return {'resposta': 'Não encontrei esse evento para alterar.', 'agente_usado': 'agenda'}
            resultado_bruto = alterar_evento(
                evento_id=eventos[0]['id'],
                titulo=intencao.get('titulo'),
                data_inicio=intencao.get('data_inicio'),
                data_fim=intencao.get('data_fim'),
                descricao=intencao.get('descricao')
            )

        elif acao == 'deletar':
            eventos = buscar_evento_por_titulo(intencao.get('evento_busca', ''))
            if not eventos:
                return {'resposta': 'Não encontrei esse evento para deletar.', 'agente_usado': 'agenda'}
            resultado_bruto = deletar_evento(eventos[0]['id'])

        else:
            resultado_bruto = 'Não entendi o que você quer fazer na agenda.'

        resposta = llm.invoke(f"""
        O usuário pediu: {pergunta}
        Resultado: {resultado_bruto}
        Responda em 1-2 frases curtas e diretas confirmando o que foi feito.
        Sem introduções, sem entusiasmo exagerado, sem repetir o ID do evento.
        """)

        return {'resposta': resposta, 'agente_usado': 'agenda'}

    except Exception as e:
        return {'resposta': f'Erro ao processar agenda: {str(e)}', 'agente_usado': 'agenda'}

def agente_pesquisa(memoria):
    pergunta = memoria['mensagem']
    historico = memoria.get('historico', [])
    contexto = '\n'.join(historico[-4:])

    try:
        resultado = llm.invoke(f'''
        Você é um assistente de pesquisa detalhista.
        
        Histórico recente:
        {contexto}
        
        Pesquise e explique sobre: {pergunta}
        ''')
        return {'resposta': resultado}
    except Exception as e:
        return {'resposta': f'Erro ao processar pesquisa: {str(e)}'}

def agente_conversa(memoria):
    pergunta = memoria['mensagem']
    historico = memoria.get('historico', []) 
    contexto = '\n'.join(historico[-4:])        

    try:
        resultado = llm.invoke(f'''
        Você é um assistente simpático.
        
        Histórico recente:
        {contexto}
        
        Responda naturalmente: {pergunta}
        ''')
        return {'resposta': resultado}
    except Exception as e:
        return {'resposta': f'Erro ao processar conversa: {str(e)}'}

#Supervisor que decide qual agente utilziar
def supervisor(memoria):
    texto = memoria['mensagem']
    
    classificacao = llm.invoke(f"""  # ← adicionar o 'f'
    Classifique a mensagem abaixo em UMA das categorias:
    - agenda: perguntas sobre eventos, compromissos, datas
    - pesquisa: perguntas que pedem explicação ou informação
    - conversa: bate-papo geral, sem intenção clara
    
    Responda APENAS com a palavra da categoria, sem explicação.
    
    Mensagem: {texto}
    """).strip().lower()
    
    if classificacao not in ['agenda', 'pesquisa', 'conversa']:
        return 'conversa' 
    
    return classificacao

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
        'mensagem': texto_limpo,
        'resposta': '',
        'historico': [],
        'agente_usado': ''
    })
 
    return {'resposta': resultado['resposta']}