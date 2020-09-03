import types
import random, string, logging, sys
import json

from invoke import task, config
from rich.logging import RichHandler

def objectify(hash):
    return types.SimpleNamespace(**hash)

def init_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='[%(module).19s:%(lineno)s] %(message)s',
        datefmt="[%X]",
        handlers=[RichHandler()]
    )

    return logging.getLogger("rich")

@task
def gen_client_name(ctx):
    alpha = random.choices(string.ascii_letters, k=1)
    num = random.choices(string.digits, k=3)

    id = ''.join(alpha + num).lower()

    logging.info(id)

def print_json(data):
    # jdata = json.loads(data)
    return json.dumps(data, indent=2, sort_keys=True)
