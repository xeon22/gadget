from kubernetes import client, config
from invoke import task
from gadget.tasks import init, utils
from atlassian import Confluence
from rich.console import Console
from rich.table import Table
from jinja2 import Template

logger = utils.init_logging()

console = Console()

zones = {
    "1": {
        "pageid": "624001182",
        "name": "Zone1 [Development]",
        "cluster": "saas-dev-product-aks-admin"
    },
    "2": {
        "pageid": "624001191",
        "name": "Zone2 [Non-Prod]",
        "cluster": "saas-np-product-aks-admin"
    },
    "3": {
        "pageid": "624132257",
        "name": "Zone3 [Prod1]",
        "cluster": "saas-prod1-product-aks-admin"
    },
    "4": {
        "pageid": "624033949",
        "name": "Zone4 [Prod2]",
        "cluster": "saas-prod2-product-aks-admin"
    },
}


@task(pre=[init.load_conf])
def init(ctx):
    ctx.config.main.confluence.client = Confluence(
        url='https://platformzero.atlassian.net/wiki',
        username=ctx.config.main.confluence.username,
        password=ctx.config.main.confluence.password,
    )


@task()
def get_contexts(ctx):
    logger.info(utils.print_json(config.list_kube_config_contexts()))


@task(pre=[init])
def get_pods(ctx, zone):
    config.load_kube_config(context=zones[zone]['cluster'])
    kube = client.CoreV1Api()
    k8s = kube.list_pod_for_all_namespaces()

    columns = ["PodName", "Created", "ContainerName", "Image", "Status"]
    table = Table(*columns, title="Active Pods")
    pods = []

    for item in k8s.items:
        client_id, work_stream, service_class = None, None, None

        if len(item.spec.containers) == 1:
            table.add_row(
                item.metadata.name,
                item.metadata.creation_timestamp.strftime("%b %d %Y"),
                item.spec.containers[0].name,
                item.spec.containers[0].image,
                item.status.phase
            )
        else:
            for container in item.spec.containers:
                table.add_row(
                    item.metadata.name,
                    item.metadata.creation_timestamp.strftime("%b %d %Y"),
                    container.name,
                    container.image,
                    item.status.phase
                )

        # pods.append(row)

    console.print(table)


@task(pre=[init])
def audit_namespaces(ctx, zone, table=False, publish=False):
    config.load_kube_config(context=zones[zone]['cluster'])
    kube = client.CoreV1Api()
    ns = kube.list_namespace()
    columns = ["Name", "Created", "ClientId", "WorkStream", "ServiceClass", "Pods"]
    namespaces = []
    console_table = Table(*columns, title="Active Namespaces")

    logger.info(f"Found {len(ns.items)} namespaces to process")

    for item in ns.items:
        client_id, work_stream, service_class = None, None, None

        if type(item.metadata.labels) is dict:
            client_id = item.metadata.labels.get("client-id")
            work_stream = item.metadata.labels.get("work-stream")
            service_class = item.metadata.labels.get("service-class")

        row = [
            item.metadata.name,
            item.metadata.creation_timestamp.strftime("%b %d %Y"),
            client_id, work_stream, service_class,
            str(len(kube.list_namespaced_pod(item.metadata.name).items))
        ]

        console_table.add_row(*row)
        namespaces.append(row)

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

    if table:
        console.print(console_table)

    if publish:
        ctx.config.main.confluence.client.update_existing_page(
            zones.get(zone).get("pageid"),
            zones.get(zone).get("name"),
            content.render(fields=len(columns), columns=columns, namespaces=namespaces),
        )
