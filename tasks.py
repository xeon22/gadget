
import logging
from invoke import Collection
from rich.logging import RichHandler
# import gadget.tasks

from gadget.tasks import (
    init,
    artifactory,
    servicedesk,
    azure,
    tls,
    jira,
    kubernetes,
    utils,
    bitbucket
)


ns = Collection()
# ns.from_module(gadget)

ns.add_collection(init)
ns.add_collection(bitbucket)
ns.add_collection(jira)
ns.add_collection(servicedesk)
ns.add_collection(utils)
ns.add_collection(artifactory)
ns.add_collection(tls)
ns.add_collection(kubernetes)
ns.add_collection(azure)

logging.basicConfig(
    level=logging.INFO,
    format='[%(module).19s:%(lineno)s] %(message)s',
    datefmt="[%X]",
    handlers=[RichHandler()]
)
