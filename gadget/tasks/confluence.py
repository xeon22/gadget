
from gadget.tasks import init, utils
from invoke import task
from atlassian import Confluence
from rich.console import Console
from jinja2 import Template

console = Console()


@task(pre=[init.load_conf])
def init(ctx):
    ctx.config.main.confluence.client = Confluence(
        url='https://platformzero.atlassian.net/wiki',
        username=ctx.config.main.confluence.username,
        password=ctx.config.main.confluence.password,
    )


@task(pre=[init])
def publish_page(ctx, page_id, title, content):
    try:
        ctx.config.main.confluence.client.update_existing_page(page_id, title, content)
    except AttributeError:
        client = init(ctx)
        ctx.config.main.confluence.client.update_existing_page(page_id, title, content)


    import os
    with open(os.path.join(os.getcwd(), 'table.html'), 'w') as f:
        f.write(content)


