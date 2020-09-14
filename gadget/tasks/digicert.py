
from gadget.tasks import init, utils, confluence
from invoke import task, Collection, Executor
from invoke.main import program
# from fabric.main import program

from rich.console import Console
from jinja2 import Template
from rich.table import Table
from simple_rest_client.api import API
from simple_rest_client.resource import Resource


console = Console()


class OrdersResource(Resource):
    actions = {
        'list': {'method': 'GET', 'url': '/order/certificate'},
        'info': {'method': 'GET', 'url': '/order/certificate/{}'},
    }


class CertResource(Resource):
    actions = {
        'download': {'method': 'GET', 'url': '/certificate/download/order/{}/format/{}'}
    }


@task(pre=[init.load_conf])
def init(ctx, headers=dict(), params=dict()):
    default_headers = {
        'X-DC-DEVKEY': ctx.config.main.digicert.api_key
    }

    default_params = dict()

    headers.update(**default_headers)
    params.update(**default_params)

    api = API(
        api_root_url='https://www.digicert.com/services/v2',
        params=params,
        headers=headers,
        json_encode_body=True
    )

    api.add_resource(resource_name='orders', resource_class=OrdersResource)
    api.add_resource(resource_name='cert', resource_class=CertResource)

    ctx.config.main.digicert.api = api


@task(pre=[init])
def list_orders(ctx):
    api = ctx.config.main.digicert.api
    orders = api.orders.list(body=None)

    console.print(orders.body)
    columns = [
        "OrderId",
        "CommonName",
        "ValidFrom",
        "ValidUntil",
        "DaysLeft"
    ]

    rows = []

    table = Table(*columns, title="Certificate Catalog")
    orders_list = orders.body.get('orders')

    for item in orders.body.get('orders'):
        if item['status'] == 'rejected':
            continue

        row = [
            str(item['id']),
            item['certificate']['common_name'],
            item['certificate']['valid_from'],
            item['certificate']['valid_till'],
            str(item['certificate']['days_remaining'])
        ]

        table.add_row(*row)
        rows.append(row)

    console.print(table)

    template = Template(
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
          {% for item in data %}
          <tr style="background-color:{{ loop.cycle('#ffffff', '#f2f2f2') }}">
            {% for num in range(fields) %}
            <td style="white-space:nowrap">{{ item[num] }}</td>
            {% endfor %}
          </tr>
          {% endfor %}
        </table>
        """
    )

    output = template.render(fields=len(columns), columns=columns, data=sorted(rows, key=lambda k: k[3]))
    confluence.publish_page(
        ctx,
        page_id=ctx.config.main.digicert.confluence_page,
        title=table.title,
        content=output
    )

    # res = Executor(Collection(confluence), config=ctx.config, core=program.core).execute(
    #     [
    #         ("publish_page", {"template": template, "page_id": ctx.config.main.digicert.confluence_page, "columns": columns})
    #     ]
    # )
    

@task(pre=[init])
def order(ctx, id):
    api = ctx.config.main.digicert.api
    order = api.orders.info(id).body

    console.log(order)

    table = Table(
        "OrderId",
        "CommonName",
        "ValidFrom",
        "ValidUntil",
        "Created",
        "DnsNames",
        "Product",
        title="Orders",
    )

    grid = Table.grid()

    grid.add_column(width=20, overflow="fold", style="frame")
    grid.add_row("OrderId", str(order['id']), style="frame")
    grid.add_row("CommonName", order['certificate']['common_name'])
    grid.add_row("Valid From", order['certificate']['valid_from'])
    grid.add_row("Valid Until", order['certificate']['valid_till'])
    grid.add_row("Created", order['certificate']['date_created'])
    grid.add_row("Dns Names", str(order['certificate']['dns_names']))
    grid.add_row("Product", str(order['product']))
    grid.add_row("Key Size", str(order['certificate']['key_size']))
    grid.add_row("Organization", str(order['organization']))
    grid.add_row("Product", str(order['product']))


    console.log(grid)
    # console.log(dir(grid))


@task(pre=[init])
def download(ctx, id, format="pem_nointermediate", output=None):
    api = ctx.config.main.digicert.api
    cert = api.cert.download(id, format).body
    print(cert.decode('utf-8'))

    if output:
        with open(output, 'w') as f:
            f.write(cert.decode('utf-8'))
