import pathlib
from datetime import datetime
from gadget.tasks import init, utils
from invoke import task, tasks
from artifactory import ArtifactoryPath
from urllib.parse import urljoin
from rich.console import Console
from rich.table import Table
from jinja2 import Template
import requests
import _thread
import time
import logging
import os

console = Console()


def artifactory(conf, repo, path=None):
    """
    :param conf: dict, Must contain the keys for the artifactory config (server, username, password)
    :param repo: string, The artifactory repository to reference
    :param path: string, The artifact path

    :return ArtifactoryPath: ArtifactoryPath
    """

    if path is not None:
        return ArtifactoryPath(f"https://{conf.server}/artifactory/{repo}/{path}", auth=(conf.username, conf.password))
    else:
        return ArtifactoryPath(f"https://{conf.server}/artifactory/{repo}", auth=(conf.username, conf.password))


def get_url(list):
    """
    :param list: list, The list of urls
    :return url: string
    """

    base_url = "https://repo.platformzero.build"
    path = pathlib.PurePath("/artifactory")

    abs_path = path.joinpath(path.as_posix(), *list)
    url = urljoin(base_url, abs_path.as_posix())
    logging.info(url)

    return url


@task
def artifact_properties(ctx, artifact):
    logging.info(f"Adding properties to artifact: {artifact}")
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

    logging.info(metadata)
    art.properties = metadata


@task
def upload(ctx, artifact, repo, repo_path=None, server=None, properties=None):
    artifact_path = [repo]

    if repo_path is None:
        file = pathlib.Path(artifact)
        artifact_path.append(file.name)
        logging.debug(artifact_path)
        logging.info(f"Repo path not supplied, defaulting to {get_url(artifact_path)}")
    else:
        logging.info(repo_path)
        artifact_path.append(repo_path)
        logging.info(f"Uploading artifact to: {get_url(artifact_path)}")

    upload_url = get_url(artifact_path)
    logging.info(f"Uploading file with url: {upload_url}")
    art = ArtifactoryPath(upload_url, ctx.config.main.artifactory)

    try:
        art.deploy(artifact)
        # if properties:
        tasks.call(artifact_properties, kwargs={"artifact": upload_url})
        # tasks.call

    except FileNotFoundError:
        logging.error(f"No file name {artifact} found")
        exit(1)
    except RuntimeError as e:
        logging.error(f"Upload failed: {e}")
    except Exception as e:
        logging.error(e)


@task(pre=[init.load_conf])
def artifact_cleanup(ctx, repo, date, purge=False, output=False, threads=5):
    art = artifactory(ctx.config.main.artifactory, repo)

    query = Template(
        '''
        items.find(
            {
                "name":{"$match":"*"}, 
                "type":"file",
                "updated":{"$before":"{{date}}"}, 
                "repo":"{{repo}}"
            }
        )
        '''
    )

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
        logging.info("No artifacts to process")
        exit(0)

    logging.info(f"{len(results)} to process")

    for item in results:
        table.add_row(
            f"{item['repo']}:{item['path']}/{item['name']}",
            datetime.strftime(datetime.strptime(item['created'], input_datefmt), '%b %d %Y'),
            datetime.strftime(datetime.strptime(item['updated'], input_datefmt), '%b %d %Y')
        )

    if output:
        table.add_row(f"Results: {len(results)}")
        console.print(table)

    if purge:
        while len(results) > 0:
            for num in range(threads):
                try:
                    artifact = results.pop()
                    artifact_path = f"{artifact['path']}/{artifact['name']}"
                    _thread.start_new_thread(
                        delete_artifact,
                        (ctx.config.main.artifactory, repo, artifact_path, f"Thread-{num}")
                    )
                except IndexError:
                    break
            time.sleep(.500)

        # for item in results:
        #     art = artifactory(ctx.config.main.artifactory, item['repo'], path=item['path'])
        #     logging.info(f"Deleting artifact: {item['repo']}:{item['path']}/{item['name']}")
        #
        #     try:
        #         art.unlink()
        #     except FileNotFoundError:
        #         logging.info(f"File not found: {item['repo']}:{item['path']}/{item['name']}")


@task(pre=[init.load_conf])
def container_cleanup(ctx, repo, date, pathmatch='*', threads=5, purge=False, output=False):
    """
    Docker cleanup task
    :param ctx: Context, Invoke context
    :param repo: string, The artifactory docker repo to target
    :param date: string, The age of the images to target
    :param pathmatch: string, Additional path match criteria to check
    :param purge: bool, Toggle for purging containers
    :param table: bool, Toggle for printing a table of images found
    """
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
                    {"path": {"$match": "{{pathmatch}}"}},
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

    aql_query = query.render(date=date, repo=repo, pathmatch=pathmatch)

    try:
        logging.debug(aql_query)
        results = art.aql(art.create_aql_text(aql_query.replace('\n', '').replace(' ', '')))
    except requests.exceptions.HTTPError:
        logging.error("Invalid AQL query")
        exit(1)

    table = Table(
        "File",
        "Updated",
        "Downloaded",
        title="Artifacts",
    )

    input_datefmt = '%Y-%m-%dT%H:%M:%S.%fZ'

    if len(results) < 1:
        logging.info("No results to show")
        exit(0)

    for item in results:
        table.add_row(
            f"{item['repo']}:{item['path']}/{item['name']}",
            datetime.strftime(datetime.strptime(item['updated'], input_datefmt), '%b %d %Y'),
        )

    table.add_row(f"{len(results)} items")

    if output:
        console.print(table)

    logging.info(f"{len(results)} to process")

    if purge:
        while len(results) > 0:
            for num in range(threads):
                try:
                    artifact = results.pop()
                    _thread.start_new_thread(
                        delete_artifact,
                        (ctx.config.main.artifactory, repo, artifact['path'], f"Thread-{num}")
                    )
                except IndexError:
                    break
            time.sleep(.500)


@task(pre=[init.load_conf])
def folder_cleanup(ctx, repo, path, threads=5, purge=False, output=False):
    """
    Docker cleanup task
    :param ctx: Context, Invoke context
    :param repo: string, The artifactory docker repo to target
    :param date: string, The age of the images to target
    :param pathmatch: string, Additional path match criteria to check
    :param purge: bool, Toggle for purging containers
    :param table: bool, Toggle for printing a table of images found
    """
    art = artifactory(ctx.config.main.artifactory, repo)

    table = Table(
        "Path",
        "Updated",
        "Downloaded",
        title="Artifacts",
    )

    input_datefmt = '%Y-%m-%dT%H:%M:%S.%fZ'

    #
    # Get the children
    #
    for path in art:
        if path.is_dir():
            for item in path.stat().children:
                    for child in path.stat().children:
                        console.print(f"Path: {item} size: {path.stat().size}")


@task(pre=[init.load_conf])
def fix_container_metadata(ctx, repo, path):
    """
    Docker metadata fix
    :param ctx: Context, Invoke context
    :param repo: string, The artifactory docker repo to target
    :param date: string, The age of the images to target
    :param pathmatch: string, Additional path match criteria to check
    :param purge: bool, Toggle for purging containers
    :param table: bool, Toggle for printing a table of images found
    """
    art = artifactory(ctx.config.main.artifactory, repo, path=os.path.join(path, "manifest.json"))

    metadata = {
        "docker.manifest": art.path_in_repo,
        "docker.manifest.digest": f"SHA:{art.stat().sha256}",
        "docker.manifest.type": "application/vnd.docker.distribution.manifest.v2+json",
        "docker.repoName": repo,
        "sha256": art.stat().sha256
    }

    try:
        art.properties = metadata
        logging.info(f"Sucessfully updated the properties for: {art.path_in_repo}")
    except FileNotFoundError as e:
        logging.error(e)


@task(pre=[init.load_conf])
def get_container(ctx, repo, container_name, container_tag):
    art = artifactory(ctx.config.main.artifactory, repo)

    query = Template(
        '''
        items.find(
            {
                "type": "file",
                "repo": {"$match": "{{repo}}"},
                "@docker.repoName": "{{name}},
                "@docker.manifest": "{{tag}}"
            }
        )
        '''
    )

    aql_query = format_aql_query(
        query.render(repo=repo, name=container_name, tag=container_tag)
    )

    try:
        logging.debug(aql_query)
        results = art.aql(art.create_aql_text(aql_query))
        return results
    except requests.exceptions.HTTPError:
        logging.error("Invalid AQL query")
        exit(1)


def delete_artifact(conf, repo, artifact_path, thread):
    art = artifactory(conf, repo, path=artifact_path)

    try:
        art.unlink()
        logging.info(f"{thread}: Deleted artifact: {repo}:{artifact_path}")
    except FileNotFoundError as e:
        logging.info(f"{thread}: File not found: {repo}:{artifact_path}")
        logging.error(e)


def delete_docker_tag(conf, artifact, thread):
    art = artifactory(conf, artifact['repo'], path=artifact['path'])

    try:
        art.unlink()
        logging.info(f"{thread}: Deleted tag: {artifact['repo']}:{artifact['path']}")
    except FileNotFoundError:
        logging.info(f"{thread}: File not found: {artifact['repo']}:{artifact['path']}")


def format_aql_query(template):
    return template.replace('\n', '').replace(' ', '')
