
import json
import logging
from invoke import task, config, call
from atlassian import ServiceDesk
from rich import print
from rich.logging import RichHandler
from rich.console import Console
from rich.table import Table

# table = Table(title="Star Wars Movies")
# table.add_column("Released", justify="right", style="cyan", no_wrap=True)
# table.add_column("Title", style="magenta")
# table.add_column("Box Office", justify="right", style="green")
# table.add_row("Dec 20, 2019", "Star Wars: The Rise of Skywalker", "$952,110,690")
# table.add_row("May 25, 2018", "Solo: A Star Wars Story", "$393,151,347")
# table.add_row("Dec 15, 2017", "Star Wars Ep. V111: The Last Jedi", "$1,332,539,889")
# table.add_row("Dec 16, 2016", "Rouge One: A Star Wars Story", "$1,332,439,889")

console = Console()
logger = logging.getLogger("rich")

@task()
def init(ctx):
    ctx.config.main.servicedesk.client = ServiceDesk(
        url='https://platformzero.atlassian.net',
        username=ctx.config.main.servicedesk.username,
        password=ctx.config.main.servicedesk.password,
        cloud=True
    )

@task
def list_queue(ctx, project):
    table = Table(
        "Id",
        "Summary",
        "Type",
        "Status",
        title="Cloud Service Requests",
    )

    logger.info("Getting issues for project %s", project)
    data = ctx.config.main.servicedesk.client.get_issues_in_queue(service_desk_id='CLOUD', queue_id=65)

    for request in data['values']:
        table.add_row(
            request['key'],
            request['fields']['summary'],
            request['fields']['issuetype']['name'],
            request['fields']['status']['name']
        )

    console.print(table)

@task()
def get_request(ctx, id):
    request = ctx.config.main.servicedesk.client.get_customer_request(issue_id_or_key=id)

    table = Table(
        "Id",
        "Created",
        "Reporter Name",
        "Reporter Email",
        "Summary",
        "Status",
        title="Cloud Service Requests",
    )

    table.add_row(
        request['issueKey'],
        request['createdDate']['friendly'],
        request['reporter']['displayName'],
        request['reporter']['emailAddress'],
        request['requestFieldValues'][0]['value'],
        request['currentStatus']['status']
    )

    console.print(table)

    console.print("Id:", request['issueKey'],)
    console.print("Created:", request['createdDate']['friendly'])
    console.print("Reporter Name:", request['reporter']['displayName'])
    console.print("Reporter Email:", request['reporter']['emailAddress'])
    console.print("Summary:", request['requestFieldValues'][0]['value'])
    console.print("Status:", request['currentStatus']['status'])
