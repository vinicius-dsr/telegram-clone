import asyncio
import hashlib
import json
import os
import sys
from hydrogram import Client
from hydrogram.errors import FloodWait

api_id = int(input("API ID: "))
api_hash = input("API Hash: ").strip()

# Pasta temporária para salvar os downloads antes do upload
TEMP_DIR = "temp_telegram_clone"
os.makedirs(TEMP_DIR, exist_ok=True)

# Arquivo de checkpoint para permitir retomar de onde parou
CHECKPOINT_FILE = "checkpoint.json"




def carregar_checkpoint():
    """Carrega o checkpoint salvo, se existir."""
    checkpoint = {"last_message_id": 0, "sent_hashes": []}
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                dados = json.load(f)
            checkpoint["last_message_id"] = int(dados.get("last_message_id", 0))
            checkpoint["sent_hashes"] = list(dados.get("sent_hashes", []))
            print(f"Resumindo de onde parou... Última mensagem processada: {checkpoint['last_message_id']}")
            print(f"{len(checkpoint['sent_hashes'])} mídias já registradas no checkpoint.")
        except Exception as e:
            print(f"Não foi possível ler o checkpoint ({e}). Começando do zero.")
            checkpoint = {"last_message_id": 0, "sent_hashes": []}
    return checkpoint


def salvar_checkpoint(last_message_id, sent_hashes):
    """Salva o progresso em disco."""
    try:
        dados = {"last_message_id": int(last_message_id), "sent_hashes": sent_hashes}
        with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"  ⚠️ Falha ao salvar checkpoint: {e}")


def calcular_hash_media(mensagem):
    """Retorna um hash estável por file_unique_id para identificar mídia duplicada."""
    unicos = []
    if mensagem.video:
        unicos.append(mensagem.video.file_unique_id)
    if mensagem.photo:
        unicos.append(mensagem.photo.file_unique_id)
    if mensagem.document:
        unicos.append(mensagem.document.file_unique_id)
    if mensagem.audio:
        unicos.append(mensagem.audio.file_unique_id)
    if mensagem.voice:
        unicos.append(mensagem.voice.file_unique_id)
    if not unicos:
        return None
    combinado = "|".join(sorted(set(unicos)))
    return hashlib.sha256(combinado.encode("utf-8")).hexdigest()


def calcular_hash_texto(texto):
    """Retorna um hash para mensagens de texto."""
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


async def carregar_hashes_destino(app, destino, sent_hashes):
    """Coleta hashes das mídias já presentes no canal de destino (últimas mensagens)."""
    set_hashes = set(sent_hashes)
    print(f"Verificando mensagens do destino para detectar duplicatas...")
    qtd = 0
    added = 0
    async for mensagem in app.get_chat_history(destino.id):
        qtd += 1
        h = calcular_hash_media(mensagem)
        if h and h not in set_hashes:
            set_hashes.add(h)
            added += 1
        # Texto também é registrado para evitar envio duplicado
        ht = calcular_hash_texto(mensagem.text) if mensagem.text else None
        if ht:
            # texto não entra no set de mídia, tratado separado abaixo
            pass
    print(f"Analisadas {qtd} mensagens do destino. {added} hashes de mídia adicionados.")
    return set_hashes


# Função para exibir o progresso do Download/Upload no terminal
def progresso(current, total, status_texto):
    if total > 0:
        percentual = (current / total) * 100
        # Converte para MB para melhor leitura
        atual_mb = current / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        sys.stdout.write(f"\r   ↳ {status_texto}: {percentual:.2f}% ({atual_mb:.1f}/{total_mb:.1f} MB)")
        sys.stdout.flush()


async def main():
    checkpoint = carregar_checkpoint()
    ultimo_id = checkpoint["last_message_id"]
    hashes_registrados = checkpoint["sent_hashes"]
    hashes_midia = set(hashes_registrados)

    async with Client("minha_sessao", api_id, api_hash) as app:

        origem_link = input("Link do canal de origem: ").strip()
        destino_link = input("Link do canal de destino: ").strip()
        print("Buscando canais...")
        origem = await app.get_chat(origem_link)
        destino = await app.get_chat(destino_link)

        print(f"Conectado! Coletando histórico de '{origem.title}'...")

        hashes_midia = await carregar_hashes_destino(app, destino, hashes_midia)

        mensagens = []
        async for mensagem in app.get_chat_history(origem.id):
            mensagens.append(mensagem)

        mensagens.reverse()
        total = len(mensagens)
        print(f"Total de {total} mensagens encontradas. Iniciando clonagem com bypass de proteção...\n")

        for index, mensagem in enumerate(mensagens, start=1):
            caminho_arquivo = None
            msg_id = mensagem.id
            try:
                # Pular mensagens já processadas conforme checkpoint
                if ultimo_id and msg_id <= ultimo_id:
                    print(f"[{index}/{total}] Pulando mensagem {msg_id} (já processada).")
                    continue

                # 1. Se for apenas texto (sem mídia)
                if mensagem.text:
                    await app.send_message(chat_id=destino.id, text=mensagem.text)
                    print(f"[{index}/{total}] Texto enviado (ID da Mensagem original: {msg_id}).")
                    salvar_checkpoint(msg_id, hashes_registrados)
                    await asyncio.sleep(1.5)
                    continue

                # 2. Se a mensagem contiver mídia (Vídeo, Foto, Documento, Áudio)
                if mensagem.media:
                    legenda = mensagem.caption if mensagem.caption else ""
                    hash_media = calcular_hash_media(mensagem)

                    # Pular mídia duplicada já presente no destino
                    if hash_media and hash_media in hashes_midia:
                        print(f"[{index}/{total}] Pulando mídia {msg_id}: duplicata já existente no destino.")
                        salvar_checkpoint(msg_id, hashes_registrados)
                        continue

                    print(f"[{index}/{total}] Processando mídia da mensagem original ID {msg_id}...")

                    # Baixa a mídia exibindo a porcentagem
                    caminho_arquivo = await app.download_media(
                        mensagem,
                        file_name=f"{TEMP_DIR}/",
                        progress=progresso,
                        progress_args=("Baixando",)
                    )
                    print("")  # Quebra de linha após o término do download

                    if caminho_arquivo and os.path.exists(caminho_arquivo):
                        # Envia a mídia baseada no tipo correto exibindo a porcentagem de upload
                        if mensagem.video:
                            await app.send_video(
                                chat_id=destino.id, video=caminho_arquivo, caption=legenda,
                                progress=progresso, progress_args=("Enviando Vídeo",)
                            )
                        elif mensagem.photo:
                            await app.send_photo(
                                chat_id=destino.id, photo=caminho_arquivo, caption=legenda,
                                progress=progresso, progress_args=("Enviando Foto",)
                            )
                        elif scholarship_doc := (mensagem.document or mensagem.audio or mensagem.voice):
                            await app.send_document(
                                chat_id=destino.id, document=caminho_arquivo, caption=legenda,
                                progress=progresso, progress_args=("Enviando Arquivo/Áudio",)
                            )
                        else:
                            await app.send_document(
                                chat_id=destino.id, document=caminho_arquivo, caption=legenda,
                                progress=progresso, progress_args=("Enviando Arquivo",)
                            )

                        # Registra o hash e salva o checkpoint
                        if hash_media:
                            hashes_midia.add(hash_media)
                            hashes_registrados.append(hash_media)
                        salvar_checkpoint(msg_id, hashes_registrados)

                        print("\n   ↳ Concluído! Limpando armazenamento local...")
                        os.remove(caminho_arquivo)
                    else:
                        if legenda:
                            await app.send_message(chat_id=destino.id, text=legenda)
                            print(f"[{index}/{total}] Apenas legenda enviada (mídia indisponível).")

                    # Intervalo de segurança anti-spam para o Telegram não bloquear o envio
                    await asyncio.sleep(2.5)

            except FloodWait as e:
                print(f"\n⚠️ Limite de requisições do Telegram atingido! Aguardando {e.value} segundos antes de retomar...")
                if caminho_arquivo and os.path.exists(caminho_arquivo):
                    os.remove(caminho_arquivo)
                await asyncio.sleep(e.value)
            except Exception as e:
                print(f"\n[{index}/{total}] Erro na mensagem {msg_id}: {e}")
                if caminho_arquivo and os.path.exists(caminho_arquivo):
                    os.remove(caminho_arquivo)
                await asyncio.sleep(2.0)

        print("\n✅ Clonagem concluída!")

asyncio.run(main())
