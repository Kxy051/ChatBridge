import html
import json
from typing import Optional

import websocket

from chatbridge.common.logger import ChatBridgeLogger
from chatbridge.core.client import ChatBridgeClient
from chatbridge.core.network.protocol import ChatPayload
from chatbridge.impl import utils
from chatbridge.impl.koishi.config import KoishiConfig

ConfigFile = 'ChatBridge_Koishi.json'
koishi_bot: Optional['KoiBot'] = None
chatClient: Optional['KoishiChatBridgeClient'] = None


class KoiBot:
    def __init__(self, config: KoishiConfig):
        self.config = config
        self.logger = ChatBridgeLogger('Bot', file_handler=chatClient.logger.file_handler)
        websocket.enableTrace(True)
        self.logger.info(f'Connecting to ws://{self.config.ws_address}:{self.config.ws_port}')
        self.ws = websocket.WebSocketApp(
            f'ws://{self.config.ws_address}:{self.config.ws_port}',
            on_message=self.on_message,
            on_close=self.on_close
        )
        if self.config.access_token:
            self.ws.url += f'?access_token={self.config.access_token}'

    def start(self):
        self.ws.run_forever()

    def on_message(self, _, message: str):
        try:
            data = json.loads(message)
            self.logger.info('QQ chat message: {}'.format(data))
            sender = data['sender']
            text = html.unescape(data['message'])
            chatClient.broadcast_chat(text, sender)
            print('Received:', data)

        except Exception as e:
            self.logger.exception(f'Error in on_message(): {e}')

    def on_close(self, *args):
        self.logger.info("Close connection")

    def send_text(self, text):
        data = {
            "message": text
        }
        self.ws.send(json.dumps(data))

    def send_message(self, sender: str, message: str):
        self.send_text('[{}] {}'.format(sender, message))


class KoishiChatBridgeClient(ChatBridgeClient):
    def on_chat(self, sender: str, payload: ChatPayload):
        global koishi_bot
        if koishi_bot is None:
            return
        try:
            koishi_bot.send_message(sender, payload.formatted_str())
        except Exception as e:
            self.logger.error(f"Error processing chat event: {e}")


def main():
    global chatClient, koishi_bot
    config = utils.load_config(ConfigFile, KoishiConfig)
    chatClient = KoishiChatBridgeClient.create(config)
    utils.start_guardian(chatClient)
    utils.register_exit_on_termination()
    print('Starting KoiBot')
    koishi_bot = KoiBot(config)
    koishi_bot.start()
    print('Bye~')


if __name__ == '__main__':
    main()
