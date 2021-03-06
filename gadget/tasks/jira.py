
import json
import logging
from invoke import task, config, call
from atlassian import Jira
from rich import print
from rich.logging import RichHandler

@task()
def init(ctx):
    ctx.config.main.jira.client = Jira(
        url='https://platformzero.atlassian.net/rest/api/3',
        username=ctx.config.main.jira.username,
        password=ctx.config.main.jira.password,
        cloud=True
    )


@task(pre=[init])
def get_issues(ctx, project):
    logging.info("Getting issues for project %s", project)
    jql = f'project = {project} AND status IN ("Open", "In Progress") ORDER BY issuekey'
    data = ctx.config.main.jira.client.get(path)
    logging.info(data)


