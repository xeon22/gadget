
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
def publish_page(ctx, zone, print_table=False):
    content = Template(
        """
        <style>
        tr:nth-child(even) {background-color: #f2f2f2;}
        </style>

        <table style="width:100%">
          <tr>
            {% for col in columns %}
            <th><b>{{ col }}</b></th>
            {% endfor %}
          </tr>
          {% for item in namespaces %}
          <tr style="background-color:{{ loop.cycle('#ffffff', '#f2f2f2') }}">
            {% for num in range(fields) %}
            <td style="white-space:nowrap">{{ item[num] }}</td>
            {% endfor %}
          </tr>
          {% endfor %}
        </table>
        """
    )

    ctx.config.main.confluence.client.update_existing_page(
        zones.get(zone).get("pageid"),
        zones.get(zone).get("name"),
        content.render(fields=len(columns), columns=columns, namespaces=namespaces),
    )
