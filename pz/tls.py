import json
from invoke import task
from urllib.request import Request, urlopen, ssl, socket
from urllib.error import URLError, HTTPError
from . import utils

logger = utils.init_logging()

@task()
def check_cert(ctx, hostname, port=443):
    #some site without http/https in the path

    context = ssl.create_default_context()

    with socket.create_connection((hostname, port)) as sock:
        with context.wrap_socket(sock, server_hostname=hostname) as tls_socket:
            logger.info(f"TLS version: {tls_socket.version()}")
            data = json.dumps(tls_socket.getpeercert())

    logger.info(data)