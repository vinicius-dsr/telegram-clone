# Telegram Clone

Clone de canais do Telegram com suporte a checkpoint e bypass de proteção.

## Funcionalidades

- Clona mensagens de texto, fotos, vídeos, documentos e áudios
- Sistema de checkpoint para retomar de onde parou
- Detecção de duplicatas no canal de destino
- Download e upload com barra de progresso
- Bypass de FloodWait com retry automático

## Requisitos

- Python 3.7+
- Conta no Telegram com API credentials em https://my.telegram.org

## Instalação

```bash
git clone https://github.com/vinicius-dsr/telegram-clone.git
cd telegram-clone
python -m venv venv
source venv/bin/activate
pip install hydrogram
```

## Uso

```bash
python clone.py
```

O script irá solicitar:
1. API ID (obtido em https://my.telegram.org)
2. API Hash (obtido em https://my.telegram.org)
3. Link do canal de origem
4. Link do canal de destino

Na primeira execução, será necessário autenticar com número de telefone e código recebido.

## Estrutura

```
telegram-clone/
├── clone.py              # Script principal
├── requirements.txt      # Dependências
├── checkpoint.json       # Progresso (gerado automaticamente)
├── temp_telegram_clone/  # Arquivos temporários
└── minha_sessao.session  # Sessão autenticada
```
