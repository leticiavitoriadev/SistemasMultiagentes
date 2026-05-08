from datetime import datetime
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

#Permissoes Google
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

#Login
flow = InstalledAppFlow.from_client_secrets_file(
    'credenciais.json',
    SCOPES
)

creds = flow.run_local_server(port=0)

#Conexao
service = build('calendar', 'v3', credentials=creds)

def buscar_eventos():
    agora = datetime.utcnow()
    inicio_do_dia = agora.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'
    fim_do_dia = agora.replace(hour=23, minute=59, second=59, microsecond=0).isoformat() + 'Z'
 
    eventos = service.events().list(
        calendarId='primary',
        timeMin=inicio_do_dia,
        timeMax=fim_do_dia,
        maxResults=10,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
 
    itens = eventos.get('items', [])
 
    if not itens:
        return 'Você não possui eventos hoje.'
 
    resposta = 'Seus próximos eventos:\n\n'
 
    #Pega o titulo e o inicio e os formata
    for evento in itens:
        titulo = evento['summary']
        inicio = evento['start'].get(
            'dateTime',
            evento['start'].get('date')
        )
        resposta += f'- {titulo} | {inicio}\n'
 
    return resposta