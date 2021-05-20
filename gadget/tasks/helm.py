import logging
import os
import yaml
import semver

# from kubernetes import client, config
from invoke import task
from gadget.tasks import init, utils
from rich.console import Console


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
    ctx.run_state = {}
    pass


@task()
def promote(ctx, chart):
    with open(os.path.join(chart, 'Chart.yaml'), 'r') as fh:
        manifest = yaml.safe_load(fh)

        console.log(manifest)

        version = semver.VersionInfo.parse(manifest['version'])

        console.log(f"Current version: {version}")
        next_version = version.bump_patch()

        console.log(f"Next version: {next_version}")
        manifest['version'] = str(next_version)
        fh.close()

    with open(os.path.join(chart, 'Chart.yaml'), 'w') as fh:
        yaml.dump(manifest, fh)
        fh.close()

    try:
        os.chdir(chart)
        ctx.run(f"helm-docs")
        ctx.run(f"git add -u")
        ctx.run(f'git commit -m "Bumped chart version: {str(next_version)}"')
        ctx.run(f'git tag {str(next_version)}')
        ctx.run(f'git push --tags origin master')

    except Exception as e:
        console.log(e)

# @task(pre=[init], iterable=['values'])
# def render(ctx, zone, name, path=os.path.curdir, namespace, values):
#     config.load_kube_config(context=zones[zone]['cluster'])
#
#     ctx.run(f"helm template {name} {path} {namespace}")
#


