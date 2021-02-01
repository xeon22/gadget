
from gadget.tasks import init, utils
from datetime import datetime
from invoke import task
from atlassian import Bitbucket
from rich.console import Console
from rich.table import Table
from urllib.parse import urlparse
from contextlib import closing
import requests
import logging
import json
import sqlite3
import os
import re

console = Console()

def language_code(lang):
    languages = {
        "java": "java",
        "javascript": "node"
    }

    return languages.get(lang)

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
        url='https://api.bitbucket.org',
        username=ctx.config.main.bitbucket.username,
        password=ctx.config.main.bitbucket.password,
        cloud=True,
        api_root='',
        api_version='2.0'
    )


@task(pre=[init])
def get_repo(ctx, repo):
    workspace, _repo = repo_check(repo)
    url_path = f"/2.0/repositories/{workspace}/{_repo}"

    try:
        data = ctx.config.main.bitbucket.client.get(path=url_path)
        console.print(data)
    except requests.exceptions.HTTPError as e:
        logging.error(e)


@task(pre=[init])
def get_all_repos(ctx, workspace):
    # workspace, _repo = repo_check(repo)
    url_path = f"/2.0/repositories/{workspace}?sort=name"
    results = list()

    try:
        data = ctx.config.main.bitbucket.client.get(path=url_path)
        results.extend(data['values'])

        if 'next' in data.keys():
            has_next = True

        while has_next:
            u = urlparse(data['next'])
            logging.info(f"Fetching results page: {data['page']}")

            url_path = f"{u.path}?{u.query}"
            data = ctx.config.main.bitbucket.client.get(path=url_path)
            results.extend(data['values'])

            has_next = data.get('next')

        # console.print(data)
    except requests.exceptions.HTTPError as e:
        logging.error(e)

    table = Table(
        "Name",
        "Project",
        "Language",
        "Created",
        title=f"Repositories({data['size']})"
    )

    for item in results:
        create_time = datetime.fromisoformat(item['created_on'])
        from datetime import timezone

        table.add_row(
            item['name'],
            item['project']['key'],
            item['language'],
            datetime.strftime(create_time, '%b %m %Y'),
        )

    console.print(table)



@task(pre=[init])
def get_branch_checks(ctx, repo):
    workspace, _repo = repo_check(repo)
    data = ctx.config.main.bitbucket.client.get_branch_restrictions(workspace, _repo)
    # data = ctx.config.main.bitbucket.client.get(path=f"/repositories/{workspace}/{_repo}/branch-restrictions")
    console.print(data)


@task(pre=[init])
def add_repo(ctx, repo, project, description=None, wiki=False, issues=False, branch='develop', language=None, init=False):
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
        # ctx.config.main.bitbucket.client.create_repo(project, repository, forkable=False, is_private=True)
    except requests.exceptions.HTTPError as e:
        logging.error(e)
        exit(1)

    console.print(output)

    if init:
        add_branches(ctx, output)

    add_branch_checks(ctx, repo)


# @task(pre=[init])
def add_branches(ctx, repo):
    clone_url = [item for item in repo['links']['clone'] if item['name'] == 'ssh'][0].get('href')
    lang_code = language_code(repo['language'])

    console.print(clone_url)

    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmpdirname:
        console.print('Created temporary directory', tmpdirname)
        os.chdir(tmpdirname)
        console.print(os.path.abspath(os.curdir))

        try:
            ctx.run(f"git clone {clone_url} .")
            ctx.run("git checkout -b master")
            url = f"https://gitignore.io/api/{lang_code}"
            r = requests.get(url)

            with open('.gitignore', 'wb') as fh:
                fh.write(r.content)

            ctx.run(f"git add .gitignore")
            ctx.run('git commit -m "Initial commit"')
            ctx.run('git checkout -b develop')
            ctx.run('git push --all origin')

        except Exception as e:
            console.print(e)


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
        ctx.config.main.bitbucket.client.delete(path=f'/2.0/repositories/{workspace}/{_repo}')
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


@task(pre=[init])
def get_projects(ctx, workspace):
    # projects = ctx.config.main.bitbucket.client.put(f"/2.0/workspaces")
    projects = ctx.config.main.bitbucket.client.repo_list('capcosaas', limit=1000)

    console.print(projects)
    console.print(dir(projects))

    breakpoint()

    # for project in projects:
    #     console.print(project)


@task(pre=[init])
def get_users(ctx, workspace):
    data = ctx.config.main.bitbucket.client.get(f"/2.0/workspaces/{workspace}/permissions")
    console.print(data['values'][0])

    try:
        results = data['values']

        if 'next' in data.keys():
            has_next = True

        while has_next:
            u = urlparse(data['next'])
            logging.info(f"Fetching results page: {data['page']}")

            url_path = f"{u.path}?{u.query}"
            data = ctx.config.main.bitbucket.client.get(path=url_path)
            results.extend(data['values'])

            has_next = data.get('next')

        # console.print(data)
    except requests.exceptions.HTTPError as e:
        logging.error(e)

    table = Table(
        "DisplayName",
        "NickName",
        "Permission",
        "Created",
        title=f"Repositories({data['size']})"
    )

    for item in sorted(results, key=lambda i: i['user']['display_name']):
        # create_time = datetime.fromisoformat(item['added_on'])
        from datetime import timezone

        table.add_row(
            item['user']['display_name'],
            item['user']['nickname'],
            item['permission'],
            # datetime.strftime(create_time, '%b %m %Y'),
        )

    console.print(table)


def init_db(ctx, db="bitbucket.db"):
    schema = [
        """
        CREATE TABLE user (
            uuid TEXT,
            display_name TEXT,
            nickname TEXT,
            account_id TEXT
        );
        """,

        """
        CREATE TABLE repo (
            uuid TEXT,
            name TEXT,
            full_name TEXT
        );
        """,

        """
        CREATE TABLE permission (
            user_id TEXT,
            repo_id TEXT,
            permission TEXT
        );
        """
    ]

    if not os.path.exists("bitbucket.db"):
        connection = sqlite3.connect(db)
        cursor = connection.cursor()
        for q in schema:
            cursor.execute(q)

        connection.commit()
        connection.close()


def insert_user(conn, data):
    """
    Create a new task
    :param conn:
    :param task:
    :return:
    """

    sql = """
        INSERT INTO user(uuid, display_name, nickname, account_id)
        VALUES(?,?,??)
    """

    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()

    return cur.lastrowid


@task(pre=[init])
def get_permissions(ctx, workspace, table=False):
    data = ctx.config.main.bitbucket.client.get(f"/2.0/workspaces/{workspace}/permissions/repositories?sort=user.nickname")
    console.print(data['values'][0])

    try:
        results = data['values']

        if 'next' in data.keys():
            has_next = True

        while has_next:
            u = urlparse(data['next'])
            logging.info(f"Fetching results page: {data['page']}")

            url_path = f"{u.path}?{u.query}"
            data = ctx.config.main.bitbucket.client.get(path=url_path)
            results.extend(data['values'])

            has_next = data.get('next')

        # console.print(data)
    except requests.exceptions.HTTPError as e:
        logging.error(e)

    with open('results.json', 'w') as fh:
        fh.write(json.dumps(results, indent=2))

    table = Table(
        "DisplayName",
        "NickName",
        "Repository",
        "Permission",
        title=f"Permissions({data['size']})"
    )

    # uuid = re.sub(r'{|}', '', data['user']['uuid'])

    for item in results:
        for item in sorted(results, key=lambda i: i['user']['display_name']):
        # create_time = datetime.fromisoformat(item['added_on'])
        # from datetime import timezone

            if table:
                table.add_row(
                    item['user']['display_name'],
                    item['user']['nickname'],
                    item['repository']['full_name'],
                    item['permission'],
                    # datetime.strftime(create_time, '%b %m %Y'),
                )

    # console.print(table)


@task()
def load_permissions(ctx, input="results.json", db="bitbucket.db"):
    init_db(ctx)

    raw = json.load(open(input, 'r'))
    logging.info(f"Loaded input file {input} with {len(raw)} records")

    with open('bitbucket_report.csv', 'w') as fh:
        fh.write("Name,Repo,Permission\n")
        current_user = ""

        for item in raw:
            if current_user == item['user']['uuid']:
                data = [
                    "",
                    item['repository']['full_name'],
                    item['permission']
                ]
            else:
                data = [
                    item['user']['display_name'],
                    item['repository']['full_name'],
                    item['permission']
                ]

            fh.write(f"{','.join(data)}\n")
            current_user = item['user']['uuid']

    with closing(sqlite3.connect(db)) as connection:
        with closing(connection.cursor()) as cursor:
            for item in raw:

                # user_uuid = re.sub(r'{|}', '', item['user']['uuid'])

                user = f"""
                    INSERT INTO 
                        user (uuid, display_name, nickname, account_id)
                    VALUES(
                        "{item['user']['uuid']}",
                        "{item['user']['display_name']}",
                        "{item['user']['nickname']}",
                        "{item['user']['account_id']}"
                    )
                """
                cursor.execute(user)

                repo = f"""
                    INSERT INTO 
                        repo (uuid, name, full_name)
                    VALUES(
                        "{item['repository']['uuid']}",
                        "{item['repository']['name']}",
                        "{item['repository']['full_name']}"
                    )
                """
                cursor.execute(repo)

                perm = f"""
                    INSERT INTO 
                        permission (user_id, repo_id, permission)
                    VALUES(
                        "{item['user']['uuid']}",
                        "{item['repository']['uuid']}",
                        "{item['permission']}"
                    )
                """
                cursor.execute(perm)



        connection.commit()

