import logging
import json
import os

from gadget.tasks import init, utils
from datetime import datetime
from invoke import task
from rich.console import Console
from rich.table import Table
from urllib.parse import urlparse
from contextlib import closing
from terrasnek.api import TFC

console = Console()

print("Hello from Terraform")

@task(pre=[init.load_conf])
def init(ctx):
    client = TFC(
        ctx.config.main.terraform.token,
        url='https://app.terraform.io'
    )

    client.set_org('platformzero')

    ctx.run_state.tfc = client
    return client


@task(pre=[init])
def list_workspaces(ctx):
    api = init(ctx)

    workspaces = api.workspaces.list_all()

    # console.print(workspaces)

    with open('output.json', 'w') as fh:
        fh.write(json.dumps(workspaces, indent=2))

    columns = [
        "Name",
        "Repo",
        "OAuthToken",
        "TFVersion",
        "WorkingDir",
        "ExecMode",
    ]

    # rows = []

    table = Table(*columns, title="Workspaces")

    for item in sorted(workspaces, key = lambda i: i['attributes']['name']):
        try:
            table.add_row(
                item['attributes']['name'],
                item['attributes']['vcs-repo'].get('identifier', None),
                item['attributes']['vcs-repo'].get('oauth-token-id', None),
                item['attributes']['terraform-version'],
                item['attributes']['working-directory'],
                item['attributes']['execution-mode'],

            )
        except AttributeError:
            table.add_row(
                item['attributes']['name'],
                item['attributes']['vcs-repo'],
                item['attributes']['vcs-repo'],
                item['attributes']['terraform-version'],
                item['attributes']['working-directory'],
                item['attributes']['execution-mode'],
            )

    console.print(table)