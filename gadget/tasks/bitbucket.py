
from gadget.tasks import init, utils
from datetime import datetime
from invoke import task
from atlassian import Bitbucket
from rich.console import Console
from rich.table import Table
import requests
import logging

console = Console()


def repo_check(repo):
    try:
        _workspace, _repo = repo.split('/')
    except ValueError:
        console.print(f"Invalid repo value: {repo}", style="red")
        console.print("Repo is not a path-like value (eg: workspace/repoName)", style="red")
        exit(1)
    else:
        return _workspace, _repo


def branch_permission(**overrides):
    defaults = {
        'type': 'branchrestriction',
        'branch_match_kind': 'glob',
        'pattern': 'master',
        # 'groups': [],
        # 'users': [],
        'value': None
    }

    defaults.update(**overrides)
    return defaults


@task(pre=[init.load_conf])
def init(ctx):
    ctx.config.main.bitbucket.client = Bitbucket(
        url='https://api.bitbucket.org/2.0',
        username=ctx.config.main.bitbucket.username,
        password=ctx.config.main.bitbucket.password,
        cloud=True,
        api_root='',
        api_version='2.0'
    )


@task(pre=[init])
def get_repo(ctx, repo):
    workspace, _repo = repo_check(repo)
    url_path = f"/repositories/{workspace}/{_repo}"

    # if _repo.find('*', len(repo) - 1, len(repo)) < 1:
    #     params = {'q': {'full_name': f"{workspace}/{_repo}"}}
    #     url_path=f"/repositories/{workspace}?{params}"

    try:
        data = ctx.config.main.bitbucket.client.get(path=parse.quote(url_path))
        console.print(data)
        # ctx.update({'cache': {'repositories': data}})
    except requests.exceptions.HTTPError as e:
        logging.error(e)


@task(pre=[init])
def get_branch_checks(ctx, repo):
    workspace, _repo = repo_check(repo)
    data = ctx.config.main.bitbucket.client.get_branch_restrictions(workspace, _repo)
    # data = ctx.config.main.bitbucket.client.get(path=f"/repositories/{workspace}/{_repo}/branch-restrictions")
    console.print(data)


@task(pre=[init])
def add_repo(ctx, repo, project, description=None, wiki=False, issues=False, branch='master', language=None):
    workspace, _repo = repo_check(repo)

    repo_data = {
        "scm": "git",
        "has_wiki": wiki,
        "fork_policy": "no_public_forks",
        "language": language,
        "mainbranch": {
            "type": "branch",
            "name": branch
        },
        "project": {
            "type": "project",
            "name": project,
            "key": project,
        },
        "has_issues": issues,
        "type": "repository",
        "slug": _repo,
        "is_private": True,
        "description": description
    }

    try:
        output = ctx.config.main.bitbucket.client.put(path=f'/2.0/repositories/{workspace}/{_repo}', data=repo_data)
    except requests.exceptions.HTTPError as e:
        logging.error(e)
        exit(1)

    console.print(output)

    add_branch_checks(ctx, repo)


@task(pre=[init])
def fork_repo(ctx, repo, target):
    workspace, _repo = repo_check(repo)

    fork_data = {
        "name": target,
        "workspace": {
            "slug": workspace
        }
    }

    try:
        output = ctx.config.main.bitbucket.client.post(path=f'/repositories/{workspace}/{_repo}/forks', data=fork_data)
    except requests.exceptions.HTTPError as e:
        logging.error(e)
        exit(1)

    console.print(output)


@task(pre=[init])
def delete_repo(ctx, repo):
    workspace, _repo = repo_check(repo)

    try:
        ctx.config.main.bitbucket.client.delete(path=f'/repositories/{workspace}/{_repo}')
        console.print(f"Deleted repo: {repo}", style="green")
    except requests.exceptions.HTTPError as e:
        console.print(e, style="red")


@task(pre=[init])
def add_branch_checks(ctx, repo):
    workspace, _repo = repo_check(repo)

    checks = [
        {'kind': 'require_approvals_to_merge', 'value': 1},
        {'kind': 'require_passing_builds_to_merge', 'value': 1},
        {'kind': 'require_tasks_to_be_completed'},
        {'kind': 'push'},
        {'kind': 'force'},
        {'kind': 'delete'}
    ]

    branches = ['master', 'develop']

    for branch in branches:
        for check in checks:
            try:
                data = ctx.config.main.bitbucket.client.add_branch_restriction(
                    workspace, _repo, check['kind'],
                    branch_match_kind='glob',
                    branch_pattern=branch,
                    value=check.get('value')
                )
                logging.debug(data)
                logging.info(f"Successfully applied check of kind: {check.get('kind')}")
            except requests.exceptions.HTTPError as e:
                logging.error(e)


@task(pre=[init])
def get_pull_requests(ctx, workspace, repo):
    data = ctx.config.main.bitbucket.client.get(path=f"/repositories/{workspace}/{repo}/pullrequests")
    console.print(data)

    table = Table(title="Pull Requests")
    # table.add_column("Released", justify="right", style="cyan", no_wrap=True)
    # table.add_column("Title", style="magenta")
    # table.add_column("Box Office", justify="right", style="green")
    # table.add_row("Dec 20, 2019", "Star Wars: The Rise of Skywalker", "$952,110,690")
    # table.add_row("May 25, 2018", "Solo: A Star Wars Story", "$393,151,347")
    # table.add_row("Dec 15, 2017", "Star Wars Ep. V111: The Last Jedi", "$1,332,539,889")
    # table.add_row("Dec 16, 2016", "Rouge One: A Star Wars Story", "$1,332,439,889")


@task(pre=[init])
def get_members(ctx, workspace):
    data = ctx.config.main.bitbucket.client.get(path=f"/workspaces/{workspace}/members")
    console.print(data)

    table = Table(
        "Name",
        "Id",
        title="Members"
    )

    for user in sorted(data['values'], key=lambda i: i['user']['display_name']):
        table.add_row(
            user['user']['display_name'],
            user['user']['account_id']
        )

    console.print(table)


@task(pre=[init])
def get_branches(ctx, repo):
    workspace, _repo = repo_check(repo)
    # data = ctx.config.main.bitbucket.client.get_branches(workspace, _repo, filter='', limit=99999, details=True)
    data = ctx.config.main.bitbucket.client.get(path=f"/2.0/repositories/{workspace}/{_repo}/refs/branches")

    table = Table(
        "Branch",
        "Author",
        "Created",
        title="Branches"
    )

    table.add_column("Age(Days)", justify="right")

    for item in sorted(data['values'], key=lambda i: i['target']['date']):
        create_time = datetime.fromisoformat(item['target']['date'])
        from datetime import timezone
        now = datetime.now(timezone.utc)
        time_difference = create_time - now

        table.add_row(
            item['name'],
            item['target']['author']['raw'],
            datetime.strftime(create_time, '%b %m %Y'),
            str(time_difference.days)

        )

    console.print(table)

    console.print(data['values'][-1])

