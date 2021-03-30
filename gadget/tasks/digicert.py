import base64
import logging

from gadget.tasks import init, utils, confluence
from invoke import task, Collection, Executor
from azure.identity import AzureCliCredential, DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from rich.console import Console
from jinja2 import Template
from rich.table import Table
from simple_rest_client.api import API
from simple_rest_client.resource import Resource
from OpenSSL import crypto


console = Console()


class OrdersResource(Resource):
    actions = {
        'list': {'method': 'GET', 'url': '/order/certificate'},
        'info': {'method': 'GET', 'url': '/order/certificate/{}'},
        'renew': {'method': 'POST', 'url': '/order/certificate/ssl_basic'},
    }


class CertResource(Resource):
    actions = {
        'download': {'method': 'GET', 'url': '/certificate/download/order/{}/format/{}'},
        'email': {'method': 'PUT', 'url': '/certificate/{}/sendemail'}
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
def init_vault(ctx, vault=None):
    if vault is None:
        vault = ctx.config.main.digicert.keyvault

    try:
        credential = AzureCliCredential()
        # logging.info(credential)
    except Exception as e:
        credential = DefaultAzureCredential()
    
    client = SecretClient(vault_url=f"https://{vault}.vault.azure.net/", credential=credential)

    ctx.run_state.vault_client = client

    return client


@task(pre=[init])
def list_orders(ctx):
    api = ctx.config.main.digicert.api
    orders = api.orders.list(body=None, params={'filters[status]': 'issued'})

    columns = [
        "Order Id",
        "Cert Id",
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
            str(item['certificate']['id']),
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
def order(ctx, id, output=True):
    api = ctx.config.main.digicert.api
    order = api.orders.info(id).body

    if output:
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

    return order


@task(pre=[init])
def download(ctx, id, format="pem_nointermediate", output=False):
    api = ctx.config.main.digicert.api
    cert = api.cert.download(id, format).body

    if output:
        console.print(cert.decode('utf-8'))
        with open(output, 'w') as f:
            f.write(cert.decode('utf-8'))

    return cert


@task(pre=[init_vault])
def renew(ctx, order, vault, csrName, certName=None):
    api = ctx.config.main.digicert.api
    order_data = api.orders.info(order).body
    vault_client = ctx.run_state.vault_client

    console.log(order_data)

    if certName is None:
        certName = csrName.replace('-key', '-crt')

    # vault_client = SecretClient(vault_url=f"https://{vault}.vault.azure.net/", credential=credential)
    csr_key_name = vault_client.get_secret(csrName)
    tls_order_csr = base64.b64decode(csr_key_name.value).decode('utf-8')

    console.log("Loading the CSR")

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
        'order_validity': {'years': order_data['validity_years']},
        'organization': {'id': order_data['organization']['id']},
        'payment_method': 'balance',
        'renewal_of_order_id': order_data['id'],
    }

    order = api.orders.renew(body=payload).body

    sleep(10)
    email_cert(ctx, order['cerificate_id'])


@task(pre=[init])
def upload_cert(ctx, order, vault=None):
    if vault is None:
        vault = init_vault(ctx, vault=ctx.config.main.digicert.keyvault)
    else:
        vault = init_vault(ctx, vault=vault)

    cert_data = download(ctx, order, output=False)
    cert_name = get_cert_data(cert_data)

    secret_value = base64.b64encode(cert_data).decode('utf-8')

    vault_secret_name = f"{cert_name}-crt"
    secret = vault.set_secret(vault_secret_name, secret_value, content_type='certificate')

    logging.info(f"Successfully updated cert: f{secret.id}")


@task(pre=[init, init_vault])
def upload_keystore(ctx, basename):
    vault = init_vault(ctx, vault=ctx.config.main.digicert.keyvault)
    keystore_name = f"{basename}-pfx"

    state = {
        'passphrase': vault.get_secret(f"{basename}-passphrase").value
    }

    for item in ["key", "crt"]:
        object_name = f"{basename}-{item}"

        try:
            raw_data = vault.get_secret(object_name)

            data = base64.b64decode(raw_data.value).decode('utf-8')

            logging.info(f"Fetched {object_name} from keyvault")
        except Exception as e:
            logging.error(e)

        state.update({item: data})

    certificate = crypto.load_certificate(crypto.FILETYPE_PEM, state.get('crt'))
    private_key = crypto.load_privatekey(crypto.FILETYPE_PEM, state.get('key'))

    p12 = crypto.PKCS12()
    p12.set_privatekey(private_key)
    p12.set_certificate(certificate)
    p12data = p12.export(state['passphrase'])

    vault.set_secret(keystore_name, base64.b64encode(p12data).decode('utf-8'))
    logging.info(f"Uploaded keystore {keystore_name} to {vault}")


@task(pre=[init])
def email_cert(ctx, orderid, emails=None, msg=None):
    api = ctx.config.main.digicert.api

    if emails is None:
        emails = ctx.config.main.digicert.emails

    order_detail = order(ctx, orderid, output=False)

    payload = {
        "emails": emails,
        "certificate_collect_format": "downloadlink",
        "custom_message": msg
    }

    result = api.cert.email(order_detail['certificate']['id'], body=payload)
    console.log(result)


def get_cert_data(cert):
    certobj = crypto.load_certificate(crypto.FILETYPE_PEM, cert)
    subject = certobj.get_subject()
    common_name = subject.get_components()[-1]
    name = common_name[-1].decode('utf-8')
    return name.replace('.', '-').replace('*', 'wildcard')
