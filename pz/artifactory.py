
import json
import pathlib
from datetime import datetime
from . import init, utils
from invoke import task, tasks
from artifactory import ArtifactoryPath
from urllib.parse import urlparse, urljoin
from rich.console import Console
from rich.table import Table
from jinja2 import Template
import requests
import _thread
import time

logger = utils.init_logging()
console = Console()


def artifactory(conf, repo, path=None):
    """
    Parameters:
        conf<Dict>: Must contain the keys for the artifactory config (server, username, password)
        repo<String>: The artifactory repository to reference
        path<String>: The artifact path
    """

    if path is not None:
        return ArtifactoryPath(f"https://{conf.server}/artifactory/{repo}/{path}", auth=(conf.username, conf.password))
    else:
        return ArtifactoryPath(f"https://{conf.server}/artifactory/{repo}", auth=(conf.username, conf.password))


def get_url(list):
    base_url = "https://repo.platformzero.build"
    path = pathlib.PurePath("/artifactory")

    abs_path = path.joinpath(path.as_posix(), *list)
    url = urljoin(base_url, abs_path.as_posix())
    logger.info(url)

    return url


@task
def artifact_properties(ctx, artifact):
    logger.info(f"Adding properties to artifact: {artifact}")
    art = ArtifactoryPath(ctx.config.main.artifactory, artifact)

    import time
    from datetime import datetime

    metadata = {
        "testRunId": "1",
        "testRunStart": datetime.fromtimestamp(time.time()).isoformat(),
        "testRunStop": datetime.fromtimestamp(time.time()).isoformat(),
        "testRunStatus": "Successful",
        "blackduckScanResult": "Successful",
        "blackduckScanTime": datetime.fromtimestamp(time.time()).isoformat(),
        "coverityScanResult": "Successful",
        "coverityScanTime": datetime.fromtimestamp(time.time()).isoformat(),
        "sonarqubeScanResult": "Successful",
        "sonarqubeScanTime": datetime.fromtimestamp(time.time()).isoformat(),
        "gitRepo": "capcosaas/test-repo",
        "gitSha": "e55a22f",
        "environment": ["nint111", "int111"],
        "zones": ["1", "2"],
    }

    logger.info(metadata)
    art.properties = metadata

@task
def upload(ctx, artifact, repo, repo_path=None, server=None, properties=None):
    artifact_path = [repo]

    if repo_path is None:
        file = pathlib.Path(artifact)
        artifact_path.append(file.name)
        logger.debug(artifact_path)
        logger.info(f"Repo path not supplied, defaulting to {get_url(artifact_path)}")
    else:
        logger.info(repo_path)
        artifact_path.append(repo_path)
        logger.info(f"Uploading artifact to: {get_url(artifact_path)}")

    upload_url = get_url(artifact_path)
    logger.info(f"Uploading file with url: {upload_url}")
    art = ArtifactoryPath(upload_url, ctx.config.main.artifactory)

    try:
        art.deploy(artifact)
        # if properties:
        tasks.call(artifact_properties, kwargs={"artifact": upload_url})
        # tasks.call

    except FileNotFoundError:
        logger.error(f"No file name {artifact} found")
        exit(1)
    except RuntimeError as e:
        logger.error(f"Upload failed: {e}")
    except Exception as e:
        logger.error(e)


@task(pre=[init.load_conf])
def artifact_cleanup(ctx, repo, date, delete=False, table=False):
    art = artifactory(repo, ctx.config.main.artifactory)

    query = Template('''
        items.find(
            {
                "name":{"$match":"*"}, 
                "type":"file",
                "updated":{"$before":"{{date}}"}, 
                "repo":"{{repo}}"
            }
        )
    ''')

    aql_query = query.render(date=date, repo=repo)
    results = art.aql(art.create_aql_text(aql_query.replace('\n', '').replace(' ', '')))

    table = Table(
        "File",
        "Created",
        "Updated",
        title="Artifacts",
    )

    input_datefmt = '%Y-%m-%dT%H:%M:%S.%fZ'

    if len(results) < 1:
        logger.info("No artifacts to process")
        exit(0)

    logger.debug(results[0])

    for item in results:
        table.add_row(
            f"{item['repo']}:{item['path']}/{item['name']}",
            datetime.strftime(datetime.strptime(item['created'], input_datefmt), '%b %d %Y'),
            datetime.strftime(datetime.strptime(item['updated'], input_datefmt), '%b %d %Y')
        )

    if table:
        table.add_row(f"Results: {len(results)}")
        console.print(table)

    if delete:
        while len(results) > 0:
            for num in range(8):
                try:
                    artifact = results.pop()
                    _thread.start_new_thread(delete_docker_tag, (artifact, f"Thread-{num}", ))
                except IndexError:
                    break
            time.sleep(.500)

        # for item in results:
        #     art_path = artifactory(item['repo'], path=item['path'])
        #     logger.info(f"Deleting artifact: {item['repo']}:{item['path']}/{item['name']}")
        #
        #     try:
        #         art_path.unlink()
        #     except FileNotFoundError:
        #         logger.info(f"File not found: {item['repo']}:{item['path']}/{item['name']}")


@task(pre=[init.load_conf])
def docker_container_cleanup(ctx, repo, date, delete=False, table=False):
    art = artifactory(ctx.config.main.artifactory, repo)

    query = Template(
        '''
        items.find(
            {
                "type": "file",
                "repo": "{{repo}}",
                "$and": [
                    {"name": {"$match": "manifest.json"}},
                    {"updated": {"$before": "{{date}}"}}, 
                    {
                        "$msp": [
                            {"path": {"$nmatch": "gradle*"}},
                            {"path": {"$nmatch": "node*"}}
                        ]
                    }
                ]
            }
        )
        '''
    )

    aql_query = query.render(date=date, repo=repo)

    try:
        results = art.aql(art.create_aql_text(aql_query.replace('\n', '').replace(' ', '')))
    except requests.exceptions.HTTPError:
        logger.error("Invalid AQL query")
        exit(1)

    table = Table(
        "File",
        "Updated",
        "Downloaded",
        title="Artifacts",
    )

    input_datefmt = '%Y-%m-%dT%H:%M:%S.%fZ'

    if len(results) < 1:
        logger.info("No results to show")
        exit(0)

    logger.debug(len(results))
    logger.debug(results[0])

    for item in results:
        table.add_row(
            f"{item['repo']}:{item['path']}/{item['name']}",
            datetime.strftime(datetime.strptime(item['updated'], input_datefmt), '%b %d %Y'),
            # datetime.strftime(datetime.strptime(item['stat'][0]['downloaded'], input_datefmt), '%b %d %Y')
        )

    table.add_row(f"{len(results)} items")

    if table:
        console.print(table)

    logger.info(f"{len(results)} to process")

    if delete:
        while len(results) > 0:
            for num in range(8):
                try:
                    artifact = results.pop()
                    _thread.start_new_thread(delete_docker_tag, (ctx.config.main.artifactory, artifact, f"Thread-{num}", ))
                except IndexError:
                    break
            time.sleep(.500)


def delete_docker_tag(conf, artifact, thread):
    art = artifactory(conf, artifact['repo'], path=artifact['path'])

    try:
        art.unlink()
        logger.info(f"{thread}: Deleted tag: {artifact['repo']}:{artifact['path']}")
    except FileNotFoundError:
        logger.info(f"{thread}: File not found: {artifact['repo']}:{artifact['path']}")
