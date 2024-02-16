import html
import json
import signal
import sys
import threading
import time
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
        self.websocket_thread = None
        self.config = config
        self.logger = ChatBridgeLogger('Bot', file_handler=chatClient.logger.file_handler)
        self.current_retry = 0
        self.websocket_ready = threading.Event()  # Event to indicate WebSocket is ready
        websocket.enableTrace(True)
        self.logger.info(f'Connecting to ws://{self.config.ws_address}:{self.config.ws_port}')

    def start(self):
        self.websocket_thread = threading.Thread(target=self._start_websocket)
        self.websocket_thread.start()

    def _start_websocket(self):
        self.ws = websocket.WebSocketApp(
            f'ws://{self.config.ws_address}:{self.config.ws_port}',
            on_open=self.on_open,
            on_message=self.on_message,
            on_close=self.on_close
        )
        if self.config.access_token:
            self.ws.url += f'?access_token={self.config.access_token}'
        self.ws.run_forever()

    def stop(self, *args):
        if hasattr(self, 'ws') and self.ws:
            self.current_retry = 233
            self.ws.close()

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

    def on_open(self, *args):
        self.current_retry = 0
        self.websocket_ready.set()  # Set the event to indicate WebSocket is ready

    def on_close(self, *args):
        self.logger.info("Close connection")
        while self.current_retry < 6:
            try:
                self.ws.close()
                self.logger.info("Retrying in 5 seconds...")
                time.sleep(5)
                self.current_retry += 1
                self._start_websocket()
            except Exception as e:
                self.logger.error(f"Connection failed: {e}")
        else:
            if self.current_retry == 6:
                self.logger.info(f"Maximum retries (6) reached. Exiting...")

    def send_text(self, text):
        if hasattr(self, 'ws') and self.ws:
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


def exit_gracefully(signum, frame):
    global koishi_bot
    if koishi_bot:
        koishi_bot.stop()
    print('Bye~')
    sys.exit(0)


def main():
    global chatClient, koishi_bot
    config = utils.load_config(ConfigFile, KoishiConfig)
    chatClient = KoishiChatBridgeClient.create(config)
    utils.start_guardian(chatClient)
    signal.signal(signal.SIGINT, exit_gracefully)  # Register exit handler for SIGINT
    print('Starting KoiBot')
    koishi_bot = KoiBot(config)
    koishi_bot.start()
    koishi_bot.websocket_ready.wait()  # Wait for WebSocket to be ready
    print("Type 'stop' or press Ctrl+C to exit.")

    # Wait for user input to stop
    while True:
        user_input = input()
        if user_input.strip().lower() == "stop":
            exit_gracefully(signal.SIGINT, None)


if __name__ == '__main__':
    main()
