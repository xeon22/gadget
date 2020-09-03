
from invoke import Collection

from pz import (
    init,
    azure,
    bitbucket,
    jira,
    servicedesk,
    artifactory,
    utils,
    tls,
    kubernetes
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

