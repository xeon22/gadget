import json
import logging
from invoke import task
from urllib.request import ssl, socket
from gadget.tasks import init, utils


@task()
def check_cert(ctx, hostname, port=443):
    #some site without http/https in the path

    context = ssl.create_default_context()

    with socket.create_connection((hostname, port)) as sock:
        with context.wrap_socket(sock, server_hostname=hostname) as tls_socket:
            logging.info(f"TLS version: {tls_socket.version()}")
            data = json.dumps(tls_socket.getpeercert())

    logging.info(data)