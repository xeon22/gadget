import base64
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
        'download': {'method': 'GET', 'url': '/certificate/download/order/{}/format/{}'},
        'renew': {'method': 'POST', 'url': '/order/certificate/ssl_basic'}
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
    orders = api.orders.list(body=None, params={'filters[status]': 'issued'})

    columns = [
        "OrderId",
        "CommonName",
        "Valid From",
        "Valid Until",
        "Days Left",
    ]

    rows = []

    table = Table(*columns, title="Certificate Catalog")
    orders_list = orders.body.get('orders')

    for item in orders_list:
        console.print(item)

        if item['status'] != 'issued':
            continue

        row = [
            str(item['id']),
            item['certificate']['common_name'],
            item['certificate']['valid_from'],
            item['certificate']['valid_till'],
            str(item['certificate']['days_remaining']),
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


@task(pre=[init])
def order(ctx, id):
    api = ctx.config.main.digicert.api
    order = api.orders.info(id).body

    grid = Table.grid()

    grid.add_column(width=20, overflow="fold", style="frame")
    grid.add_row("OrderId", str(order['id']), style="frame")
    grid.add_row("CommonName", order['certificate']['common_name'])
    grid.add_row("Valid From", order['certificate']['valid_from'])
    grid.add_row("Valid Until", order['certificate']['valid_till'])
    grid.add_row("Created", order['certificate']['date_created'])
    grid.add_row("Dns Names", str(order['certificate']['dns_names']))
    grid.add_row("Product", order['product']['name'])
    grid.add_row("Key Size", str(order['certificate']['key_size']))
    grid.add_row(
        "Organization",
        "\n".join(
            [
                order['organization']['name'],
                order['organization']['assumed_name'],
                order['organization']['display_name'],
                order['organization']['city'],
                order['organization']['state'],
                order['organization']['country'].upper(),
                order['organization']['telephone'],
            ]
        )
    )

    console.print(grid)


@task(pre=[init])
def download(ctx, id, format="pem_nointermediate", output=None):
    api = ctx.config.main.digicert.api
    cert = api.cert.download(id, format).body
    console.print(cert.decode('utf-8'))

    if output:
        with open(output, 'w') as f:
            f.write(cert.decode('utf-8'))


@task(pre=[init])
def renew(ctx, order, vault, keyName, csrName=None, certName=None):
    from azure.identity import AzureCliCredential, DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient

    import OpenSSL.crypto
    from OpenSSL.crypto import load_certificate_request, FILETYPE_PEM

    api = ctx.config.main.digicert.api
    order_data = api.orders.info(order).body

    console.log(order_data)

    if csrName is None:
        csrName = keyName.replace('-key', '-csr')

    if certName is None:
        certName = keyName.replace('-key', '-cert')

    try:
        credential = AzureCliCredential()
    except Exception as e:
        credential = DefaultAzureCredential()

    vault_client = SecretClient(vault_url=f"https://{vault}.vault.azure.net/", credential=credential)
    
    vault_key_name = vault_client.get_secret(keyName)
    csr_key_name = vault_client.get_secret(csrName)

    tls_private_key = base64.b64decode(vault_key_name.value).decode('utf-8')
    tls_order_csr = base64.b64decode(csr_key_name.value).decode('utf-8')

    print(tls_private_key)
    print(tls_order_csr)

    console.log("Loading the CSR")
    req = load_certificate_request(FILETYPE_PEM, tls_order_csr)
    subject = dict(req.get_subject().get_components())

    payload = {
        'certificate': {
            'common_name': order_data['certificate']['common_name'],
            'dns_names': order_data['certificate']['dns_names'],
            'csr': tls_order_csr,
            'signature_hash': order_data['certificate']['signature_hash'],
            'server_platform': {'id': order_data['certificate']['server_platform']['id']},
        },
        'container': order_data['container']['id'],
        'auto_renew': 0,
        'organization': {'id': order_data['organization']['id']},
        'order_validity': order_data['validity_years'],
        'validity_years': order_data['validity_years'],
        'payment_method': 'card',
        'additional_emails': [
            'mark.pimentel@capco.com',
            'catodevopsteam@capco.com',
        ]
    }

    console.log(payload)

    # order = api.orders.renew

    # print(response.body)