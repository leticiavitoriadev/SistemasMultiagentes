const qrcode = require('qrcode-terminal'); //Biblioteca do QrCode

const { Client } = require('whatsapp-web.js'); //Responsavel por controlar o wpp

const axios = require('axios'); //Biblioteca para conversar com a api


// cria cliente
const client = new Client(); //cria o bot


// QR CODE
client.on('qr', qr => {

    qrcode.generate(qr, {
        small: true
    });

});


// conectado
client.on('ready', () => {

    console.log('BOT CONECTADO');

});


// mensagens
client.on('message_create', async message => { //Agir quando a msg for criada

    try {

        // ignora mensagens vazias
        if (!message.body) return;

        // ignora grupos
        if (message.from.includes('@g.us')) return;

        // responde só com !bot
        if (!message.body.startsWith('!bot')) return;

        console.log('Mensagem recebida:');
        console.log(message.body);


        const resposta = await axios.post( //Envia para a api rodando localmente
            'http://127.0.0.1:8000/chat', 
            {
                texto: message.body 
            }
        );


        await message.reply(
            resposta.data.resposta
        );

    } catch (erro) {

        console.log(erro);

    }

});


client.initialize();