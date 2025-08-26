import json
import os
import socket
import sys
import time

import arrow
import requests
import tornado.web
import yaml
from cachetools import TTLCache
from packaging import version

def load_game_configs():
    """Load game configurations from YAML file"""
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'game_configs.yaml')
    try:
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
            return config_data['games'], config_data.get('settings', {})
    except FileNotFoundError:
        print(f"Error: Configuration file not found at {config_path}")
        print("Please ensure the config/game_configs.yaml file exists.")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error: Invalid YAML in configuration file: {e}")
        sys.exit(1)
    except KeyError as e:
        print(f"Error: Missing required key in configuration file: {e}")
        sys.exit(1)

GAME_CONFIGS, SETTINGS = load_game_configs()

class WebServer(tornado.web.Application):
    def __init__(self):
        self.serverCache = TTLCache(maxsize=500, ttl=10)
        self.lastPFData = None
        self.maxServerVersion = "0.0"
        self.fullStatsData = {}
        self.allServerData = {}
        settings = {
            'debug': True,
            "static_path": "public",
        }
        handlers = [(r'/', MainHandler, {"path": settings['static_path']}),
                    (r"/api", APIRequestHandler)
                    ]
        super().__init__(handlers, **settings)

    def get_config_for_request(self, request):
        """Get configuration based on the request's host header"""
        host = request.headers.get('Host', '').lower()
        
        # Check for exact match in domain lists
        for config in GAME_CONFIGS:
            if host in [domain.lower() for domain in config['domains']]:
                return config
                
        # Default to first config if no match found
        return GAME_CONFIGS[0]

    def run(self):
        port = 5555
        self.listen(port)
        url = f"http://localhost:{port}"
        print(f"Running a web server at {url}")
        tornado.ioloop.IOLoop.instance().start()


class MainHandler(tornado.web.RequestHandler):
    # pylint: disable=arguments-differ

    def initialize(self, path):
        self.path = path

    def get(self):
        clientIP = self.request.headers.get("X-Real-IP") or \
            self.request.headers.get("X-Forwarded-For") or \
            self.request.remote_ip
        
        # Get server configuration based on domain
        config = self.application.get_config_for_request(self.request)
        clientPort = config['default_port']
        args = self.request.arguments

        if 'url' in args:
            url = (args['url'][0]).split(b":")
            if len(url) > 0:
                clientIP = url[0]
            if len(url) > 1 and url[1] != b'':
                clientPort = url[1]
        else:
            if 'ip' in args:
                clientIP = (args['ip'][0])
            if 'port' in args:
                clientPort = (args['port'][0])

        # pprint(list(self.request.headers.get_all()))
        print(f"Webpage opened at: {self.request.headers.get('X-Real-IP')}")
        
        server_name = config['name']
        
        # Get other server checkers (exclude current domain) if enabled
        other_servers = []
        if SETTINGS.get('show_other_servers', False):
            current_host = self.request.headers.get('Host', '').lower()
            for cfg in GAME_CONFIGS:
                first_domain = cfg['domains'][0]
                if first_domain.lower() != current_host:
                    other_servers.append({
                        'name': cfg['name'],
                        'url': f"https://{first_domain}"
                    })
        
        self.render(os.path.join(self.path, 'index.html'),
                    clientIP=clientIP, clientPort=clientPort, serverName=server_name, 
                    defaultPort=config['default_port'], otherServers=other_servers)


class APIRequestHandler(tornado.web.RequestHandler):
    def post(self):
        UDP_IP_PORT = self.get_argument("ip_port")
        UDP_IP = None
        UDP_PORT = None
        splitIPP = UDP_IP_PORT.split(":")
        if len(splitIPP) > 0:
            UDP_IP = splitIPP[0]
            if(len(splitIPP) > 1) and splitIPP[1] != b'':
                UDP_PORT = splitIPP[1]
            else:
                # Get default port based on domain
                config = self.application.get_config_for_request(self.request)
                UDP_PORT = config['default_port']
            UDP_IP_PORT = UDP_IP+":"+UDP_PORT
            UDP_PORT = int(UDP_PORT)
            ipPortCombo = f"{UDP_IP_PORT}"
            data = {
                "Server": False,
                "Fresh": True,
            }

            if ipPortCombo not in self.application.serverCache:
                # Get server configuration based on domain
                config = self.application.get_config_for_request(self.request)
                byteArray = config['byte_array']
                res = sendPacket(bytes(byteArray), UDP_IP, UDP_PORT)
                data['Server'] = res

                data['Fresh'] = True
                self.application.serverCache[ipPortCombo] = data

            else:
                data = self.application.serverCache[ipPortCombo]
                data['Fresh'] = False

            self.write(data)
        else:
            self.write({"status": "Error"})

def sendPacket(MESSAGE, IP, Port):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5)
        # Send message to UDP port
        print(f'sending message to {IP}:{Port}')
        sock.sendto(MESSAGE, (IP, Port))

        # Receive response
        print('waiting to receive')
        sock.settimeout(5)
        data, _server = sock.recvfrom(4096)
        print('received "%s"' % data)
        return True
    except:
        print(f"Timeout for {IP}:{Port}")
        return False


def start_WebServer():
    try:
        print("Starting Web Server...")
        ws = WebServer()

        ws.run()
    except Exception as err:
        print(
            f"{('SWS Error on line {}'.format(sys.exc_info()[-1].tb_lineno), type(err).__name__, err)}"
        )


if __name__ == "__main__":
    try:
        start_WebServer()
    except KeyboardInterrupt:
        print("WebServer was killed by CTRL+C")
    except Exception as err:
        print(
            f"{('MAIN Error on line {}'.format(sys.exc_info()[-1].tb_lineno), type(err).__name__, err)}"
        )
