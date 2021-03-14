import socket
from urllib.parse import urlparse
import pickle
import logging
import argparse

# settings
filename: str = 'http_proxy_request.pickle'


class ProxyServer:
    """
    Proxy-server is a class to proxy an http-requests.
    Example: > curl -x http://127.0.0.1:8841 http://mail.ru
    """
    def __init__(self, host: str = '127.0.0.1', port: int = 8841):                  # default host:port
        self.logger = logging.getLogger('proxy_server')
        self.logger.setLevel(logging.INFO)

        self.logger.info(f"Proxy-server is starting on {host}:{port}...")
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)      # create TCP socket
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)    # set socket flags
        self.server_socket.bind((host, port))                                       # bind to (h:p)
        self.server_socket.listen(1)                                                # max queue size

    def serve_forever(self):
        """
        Proxying client-requests:
        1. Accept clients socket and read request.
        2. Parse request.
        3. Save request as a pickle.
        3. Open proxying socket, send request.
        4. Get response, send to client.
        """
        while True:
            self.logger.info(f"Proxy-server is ready to accept connections")
            client_connection, _ = self.server_socket.accept()

            self.logger.info(f"Client {client_connection.getpeername()} connected")
            request = client_connection.recv(1024).decode()

            h, p, r = self.parse_request(request)
            self.logger.info(f"Proxying to {h}")

            pickle_request = {
                "host": h,
                "port": p,
                "request": r
            }
            try:
                self.save_pickle(filename, pickle_request)
                self.logger.info("Request successfully saved on disk")
            except Exception as exc:
                self.logger.error(f"Failed save on disk, exc: {exc}")
                return

            proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            proxy_socket.connect((h, p))
            proxy_socket.sendall(r.encode())
            response = proxy_socket.recv(1024).decode()
            proxy_socket.close()
            
            client_connection.sendall(response.encode())
            client_connection.close()

    def __del__(self):
        """
        Shutting down proxy-server, closing clients socket.
        """
        self.logger.info("Proxy-server is shutting down...")
        self.server_socket.close()

    @staticmethod
    def parse_request(request: str):
        """
        Parsing http-request for proxying.
        1. Getting end-point host and port.
        2. Creating proxy request.
        """
        req_lines = request.splitlines(True)

        proxy_address = urlparse(req_lines[1])
        host = proxy_address.path.strip()
        port = 80 if not proxy_address.port else proxy_address.port
        method, _, version = req_lines[0].split()

        url = '/'
        proxy_first_line = method + ' ' + url + ' ' + version + '\r\n'
        req_lines[0] = proxy_first_line
        for idx, line in enumerate(req_lines):
            if line.startswith('Proxy-Connection'):
                del req_lines[idx]
        proxy_request = ''.join(req_lines)

        return host, port, proxy_request

    @staticmethod
    def save_pickle(picklename: str, dump: dict):
        with open(picklename, 'wb') as f:
            pickle.dump(dump, f)


class Repeater:
    """
    Re-send last http request, that has been sent from proxy-server.
    """
    def __init__(self, host: str = '127.0.0.1', port: int = 8842):                  # default host:port
        """
        Initialize TCP-socket for client's request.
        """
        self.logger = logging.getLogger('repeater')
        self.logger.setLevel(logging.INFO)

        self.logger.info(f"Repeater is starting on {host}:{port}...")

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)      # create TCP socket
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)    # set socket flags
        self.server_socket.bind((host, port))                                       # bind to (h:p)
        self.server_socket.listen(1)                                                # max queue size

    def serve_forever(self):
        while True:
            self.logger.info("Repeater started")
            client_connection, _ = self.server_socket.accept()
            self.logger.info(f"Client {client_connection} repeater request")

            try:
                current_request = self.load_pickle(filename)
                h, p, req = current_request['host'], int(current_request['port']), current_request['request']
                self.logger.info(f"Request to {h, p} successfully loaded")
            except Exception as exc:
                self.logger.error(f"Failed load repeating request, exc: {exc}")
                return

            repeater_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            repeater_socket.connect((h, p))
            repeater_socket.sendall(req.encode())
            self.logger.info("Request send")

            response = repeater_socket.recv(1024).decode()
            repeater_socket.close()
            
            client_connection.sendall(response.encode())
            client_connection.close()

    def __del__(self):
        """
        Shutting down repeater, closing clients socket.
        """
        self.logger.info("Repeater is shutting down...")
        self.server_socket.close()

    @staticmethod
    def load_pickle(picklename: str):
        with open(picklename, 'rb') as f:
            return pickle.load(f)


def run(server_port: int):
    proxy = ProxyServer('127.0.0.1', int(server_port))
    repeater = Repeater('127.0.0.1', int(server_port) + 1)
    try:
        proxy.serve_forever()
        repeater.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)-15s %(name)-12s %(levelname)-8s %(message)s')

    parser = argparse.ArgumentParser(description="Proxy server and requests repeater")
    parser.add_argument(
        "-p",
        "--port",
        help="Set the port of proxy-server. Repeater will be open on proxy-server port + 1",
        default=8841
    )
    args = parser.parse_args()

    run(args.port)
