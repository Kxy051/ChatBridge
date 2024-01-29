from chatbridge.core.config import ClientConfig


class KoishiConfig(ClientConfig):
	ws_address: str = '127.0.0.1'
	ws_port: int = 6700
	access_token: str = ''