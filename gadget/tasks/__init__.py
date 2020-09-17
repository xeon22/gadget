
import logging
from invoke import config, Collection
from rich.logging import RichHandler

from gadget.tasks import (
    init,
    artifactory,
    servicedesk,
    azure,
    tls,
    jira,
    kubernetes,
    utils,
    bitbucket,
    hvault,
    digicert
)

ns = Collection()
ns.add_collection(init)
ns.add_collection(bitbucket)
ns.add_collection(jira)
ns.add_collection(servicedesk)
ns.add_collection(utils)
ns.add_collection(artifactory)
ns.add_collection(tls)
ns.add_collection(kubernetes)
ns.add_collection(azure)
ns.add_collection(hvault)
ns.add_collection(digicert)

LOGGING_FORMAT = '[%(module)s:%(funcName)s:%(lineno)d] %(levelname)s: %(message)s'
# format='[%(module).19s:%(lineno)s] %(message)s',

from rich.console import Console

console = Console()

# console.print(config.__dict__)
console.log(logging.getLevelName(config.debug))
console.log(dir(config.debug))

if logging.getLevelName(config.debug) == logging.getLevelName(logging.DEBUG):
    console.print("We have debug")

exit(1)


logging.basicConfig(
    level=config.debug,
    format=LOGGING_FORMAT,
    datefmt="[%X]",
    handlers=[RichHandler()]
)
