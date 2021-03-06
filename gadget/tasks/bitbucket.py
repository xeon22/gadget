
from gadget.tasks import init, utils
from datetime import datetime
from invoke import task, call
from atlassian import Bitbucket
from rich.console import Console
from rich.table import Table
from urllib.parse import urlparse
from contextlib import closing
from datetime import timezone

import requests
import logging
import json
import sqlite3
import tempfile
import os
import re
import sys

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
        return _workspace, _repo
    except ValueError:
        console.print(f"Invalid repo value: {repo}", style="red")
        console.print("Repo is not a path-like value (eg: workspace/repoName)", style="red")
        exit(1)


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


def profiles(profile):
    profiles = {
        'cloud': {
            'pz-cloud-eng': 'write',
            'pz-cloud-sre': 'read'
        },

        'sre': {
            'pz-cloud-eng': 'write',
            'pz-cloud-sre': 'write'
        },

        'coredev': {
            'pz-coredev-rw': 'write',
            'pz-coredev-ro': 'read',
        },

        'pzs': {
            'pz-coredev-rw': 'write',
            'pz-coredev-ro': 'read',
        },

        'coop': {
            'pz-coredev-rw': 'write',
            'cl-coop-rw': 'write',
            'cl-coop-ro': 'read',
        },

        'igm': {
            'pz-coredev-rw': 'write',
            'cl-igm-rw': 'write',
            'cl-igm-ro': 'read',
        }
    }

    try:
        return profiles[profile.lower()]
    except KeyError:
        logging.error(f"Invalid profile {profile} specified")
        logging.error(f"Valid profiles are {profiles.keys()}")
        sys.exit(1)


@task(pre=[init.load_conf])
def init(ctx):
    client = Bitbucket(
        url='https://api.bitbucket.org',
        username=ctx.config.main.bitbucket.username,
        password=ctx.config.main.bitbucket.password,
        cloud=True,
        api_root='',
        api_version='2.0'
    )

    ctx.run_state.bb = client
    return client


@task(pre=[init])
def get_repo(ctx, repo):
    workspace, _repo = repo_check(repo)
    url_path = f"/2.0/repositories/{workspace}/{_repo}"

    try:
        data = ctx.run_state.bb.get(path=url_path)
        console.print(data)

        return data
    except requests.exceptions.HTTPError as e:
        logging.error(e)


@task(pre=[init])
def list_repos(ctx, workspace, project=None, repos=None, output=True):
    # workspace, _repo = repo_check(repo)
    url_path = f"/2.0/repositories/{workspace}"
    results = list()
    has_next = False
    query = {'role': 'member', 'sort': 'name', 'limit': 1000}

    if project:
        query.update({'q': f'project.key="{project}"'})
    if repos:
        query.update({'q': f'name~"{repos}"'})

    try:
        data = ctx.run_state.bb.get(path=url_path, params=query)
        results.extend(data['values'])

        if 'next' in data.keys():
            has_next = True

        while has_next:
            u = urlparse(data['next'])
            logging.info(f"Fetching results page: {data['page']}")

            url_path = f"{u.path}?{u.query}"
            data = ctx.run_state.bb.get(path=url_path)
            results.extend(data['values'])

            has_next = data.get('next')

        # console.print(data)
    except requests.exceptions.HTTPError as e:
        logging.error(e)

    if output:
        table = Table(
            "Name",
            "Project",
            "Language",
            "Created",
            title=f"Repositories({len(results)})"
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
    else:
        return results


@task(pre=[init])
def add_branches(ctx, repo, init=False):
    clone_url = [item for item in repo['links']['clone'] if item['name'] == 'ssh'][0].get('href')
    lang_code = language_code(repo['language'])

    console.print(clone_url)

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

            with open('Jenkinsfile', 'w') as fh:
                fh.write("PLZPipeline {}\n")

            ctx.run(f"git add .")
            ctx.run('git commit -m "Initial commit"')
            ctx.run('git checkout -b develop')
            ctx.run('git push --all origin')

        except Exception as e:
            console.print(e)


@task(pre=[init])
def list_restrictions(ctx, repo):
    workspace, _repo = repo_check(repo)
    data = ctx.run_state.bb.get_branch_restrictions(workspace, _repo)
    console.print(data)


@task(pre=[init])
def add_branch_checks(ctx, repo, init=False):
    workspace, _repo = repo_check(repo)

    checks = [
        {'kind': 'require_approvals_to_merge', 'value': 1},
        {'kind': 'require_passing_builds_to_merge', 'value': 1},
        {'kind': 'require_tasks_to_be_completed'},
        {'kind': 'push', 'groups': [{'name': 'Administrators', 'slug': 'Administrators'}]},
        {'kind': 'force'},
        {'kind': 'delete'}
    ]

    branches = ['master', 'develop']

    for branch in branches:
        for check in checks:
            try:
                data = ctx.run_state.bb.add_branch_restriction(
                    workspace, _repo, check['kind'],
                    branch_match_kind='glob',
                    branch_pattern=branch,
                    value=check.get('value'),
                    groups=check.get('groups'),
                )
                logging.debug(data)
                logging.info(f"Successfully applied check of kind: {check.get('kind')}")
            except requests.exceptions.HTTPError as e:
                logging.error(f"{e.response.status_code}: {e.response.text}")


@task(pre=[init])
def add_repo(ctx, repo, project, profile, description=None, wiki=False, issues=False, branch='develop', language=None, init=False):
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
        output = ctx.run_state.bb.put(path=f'/2.0/repositories/{workspace}/{_repo}', data=repo_data)
        # ctx.config.main.bitbucket.client.create_repo(project, repository, forkable=False, is_private=True)
    except requests.exceptions.HTTPError as e:
        logging.error(e)
        exit(1)

    console.print(output)

    if init:
        add_branches(ctx, output)
        # ctx.run_state.bb.create_branch(output['workspace']['slug'], output['slug'], output['slug'], '', "Init branch")

    set_repo_groups(ctx, repo, profile, project=project, repos=_repo)
    add_branch_checks(ctx, repo)


@task(pre=[init])
def fork_repo(ctx, repo, target):
    src_workspace, src_repo = repo_check(repo)
    target_workspace, target_repo = repo_check(repo)

    fork_data = {
        "name": target_repo,
        "workspace": {
            "slug": target_workspace
        }
    }

    try:
        output = ctx.run_state.bb.post(path=f'/2.0/repositories/{src_workspace}/{src_repo}/forks', data=fork_data)
    except requests.exceptions.HTTPError as e:
        logging.error(e)
        exit(1)

    console.print(output)


@task(pre=[init])
def invite_user(ctx, workspace, email, group):
    url = f"/1.0/users/{workspace}/invitations"

    payload = {
        "email": email,
        "group_slug": group
    }

    try:
        response = ctx.run_state.bb.put(
            url, data=payload,
            headers={'Content-Type': 'application/json'},
            # auth=(ctx.run_state.bb.username, ctx.run_state.bb.password)
        )

        console.print(response)
        logging.info(f"Invited user: {email} as memberOf {group} -> {response.reason}")

    except Exception as e:
        logging.error(e)
        sys.exit(1)


@task(pre=[init])
def delete_repo(ctx, repo):
    workspace, _repo = repo_check(repo)

    try:
        ctx.run_state.bb.delete(path=f'/2.0/repositories/{workspace}/{_repo}')
        console.print(f"Deleted repo: {repo}", style="green")
    except requests.exceptions.HTTPError as e:
        console.print(e, style="red")


@task(pre=[init])
def get_pull_requests(ctx, workspace, repo):
    data = ctx.run_state.bb.get(path=f"/repositories/{workspace}/{repo}/pullrequests")
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
    data = ctx.run_state.bb.get(path=f"/workspaces/{workspace}/members")
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
def get_branches(ctx, repo, output=True):
    workspace, _repo = repo_check(repo)
    # data = ctx.run_state.bb.get_branches(workspace, _repo, filter='', limit=99999, details=True)
    data = ctx.run_state.bb.get(path=f"/2.0/repositories/{workspace}/{_repo}/refs/branches")

    table = Table(
        "Branch",
        "Author",
        "Created",
        title="Branches"
    )

    table.add_column("Age(Days)", justify="right")

    try:
        results = data['values']

        if 'next' in data.keys():
            has_next = True

        while has_next:
            u = urlparse(data['next'])
            logging.info(f"Fetching results page: {data['page']}")

            url_path = f"{u.path}?{u.query}"
            data = ctx.run_state.bb.get(path=url_path)
            results.extend(data['values'])

            has_next = data.get('next')

        # console.print(data)
    except requests.exceptions.HTTPError as e:
        logging.error(e)

    if output:
        for item in sorted(results, key=lambda i: i['target']['date']):
            create_time = datetime.fromisoformat(item['target']['date'])
            now = datetime.now(timezone.utc)
            time_difference = create_time - now

            table.add_row(
                item['name'],
                item['target']['author']['raw'],
                datetime.strftime(create_time, '%b %m %Y'),
                str(time_difference.days)

            )

        console.print(table)

    return results


@task(pre=[init])
def delete_branches(ctx, repo, age):
    workspace, _repo = repo_check(repo)

    repo_data = get_repo(ctx, repo)
    clone_url = [item for item in repo_data['links']['clone'] if item['name'] == 'ssh'][0].get('href')
    console.print(clone_url)

    branches = get_branches(ctx, repo, output=False)

    with tempfile.TemporaryDirectory() as tmpdirname:
        console.print('Created temporary directory', tmpdirname)
        os.chdir(tmpdirname)
        console.print(os.path.abspath(os.curdir))

        try:
            ctx.run(f"git clone {clone_url} .")

            for branch in sorted(branches, key=lambda i: i['target']['date']):
                create_time = datetime.fromisoformat(branch['target']['date'])

                now = datetime.now(timezone.utc)
                time_difference = create_time - now

                if -(int(time_difference.days)) > int(age):
                    logging.info(f"Deleting branch: {branch['name']} of age: {-(time_difference.days)}")
                    ctx.run(f"git push origin --delete {branch['name']}")

        except Exception as e:
            console.print(e)


@task(pre=[init])
def list_projects(ctx, workspace):
    projects = ctx.run_state.bb.put(f"/2.0/workspaces")
    # projects = ctx.run_state.bb.repo_list('capcosaas', limit=1000)

    console.print(projects)

    for project in projects:
        console.print(project)


@task(pre=[init])
def get_users(ctx, workspace):

    data = ctx.run_state.bb.get(f"/2.0/workspaces/{workspace}/permissions")
    console.print(data['values'][0])

    try:
        results = data['values']

        if 'next' in data.keys():
            has_next = True

        while has_next:
            u = urlparse(data['next'])
            logging.info(f"Fetching results page: {data['page']}")

            url_path = f"{u.path}?{u.query}"
            data = ctx.run_state.bb.get(path=url_path)
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
    """
    Initializes a sqlite db for the permissions load:

    :param db:

    :return:
    """

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


@task(pre=[init])
def get_permissions(ctx, workspace, table=False):
    data = ctx.run_state.bb.get(f"/2.0/workspaces/{workspace}/permissions/repositories?sort=user.nickname")
    console.print(data['values'][0])

    try:
        results = data['values']

        if 'next' in data.keys():
            has_next = True

        while has_next:
            u = urlparse(data['next'])
            logging.info(f"Fetching results page: {data['page']}")

            url_path = f"{u.path}?{u.query}"
            data = ctx.run_state.bb.get(path=url_path)
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


@task(pre=[init])
def get_repo_groups(ctx, repo, table=False):
    workspace, _repo = repo_check(repo)
    data = ctx.run_state.bb.get(f"/1.0/group-privileges/{workspace}/{_repo}")

    table = Table(
        "Repo",
        "Group",
        "Permission",
        title=f"Permissions({len(data)})"
    )

    for item in sorted(data, key=lambda i: i['group']['name']):
        table.add_row(
            item['repo'],
            item['group']['name'],
            item['privilege'],
        )

    console.print(table)


@task(pre=[init])
def set_repo_groups(ctx, workspace, profile, project=None, repos=None):
    _workspace, _repo = repo_check(workspace)

    if _repo == '*':
        repo_list = list_repos(ctx, _workspace, project=project, repos=repos, output=False)
        logging.info(f"Processing {len(repo_list)} repositories")
    else:
        repo_list = [dict(name=_repo)]

    try:
        group_profile = profiles(profile)
        logging.info(group_profile)
    except KeyError:
        logging.error(f"Invalid profile {profile} supplied")
        sys.exit(1)

    for group,permission in group_profile.items():
        headers = {
            'Accept': 'application/json',
            'Content-Type': "text/plain",
        }

        if project or repos:
            for repo in repo_list:
                url = f"{ctx.run_state.bb.url}/1.0/group-privileges/{_workspace}/{repo['name']}/{_workspace}/{group}"

                try:
                    response = requests.put(url, data=permission, headers=headers, auth=(ctx.run_state.bb.username, ctx.run_state.bb.password))
                    logging.info(f"Repo: {repo['name']}\tGroup: {group}:{permission} -> {response.reason}")
                except Exception:
                    logging.error(f"Repo: {repo['name']}\tGroup: {group}:{permission} -> {response.reason} :: {response.text}")
                    sys.exit(1)
        else:
            url = f"{ctx.run_state.bb.url}/1.0/group-privileges/{_workspace}/{_repo}/{_workspace}/{group}"

            try:
                response = requests.put(url, data=permission, headers=headers,
                                        auth=(ctx.run_state.bb.username, ctx.run_state.bb.password))
                logging.info(f"Repo: {_repo}\tGroup: {group}:{permission} -> {response.reason}")
            except Exception:
                logging.error(f"Repo: {_repo}\tGroup: {group}:{permission} -> {response.reason} :: {response.text}")
                sys.exit(1)


@task(pre=[init])
def set_repo_project(ctx, workspace, project, repos=None):
    repo_list = list_repos(ctx, workspace, project=None, repos=repos, output=False)
    logging.info(f"Processing {len(repo_list)} repositories")

    for repo in repo_list:
        repo['project']['key'] = project

        try:
            response = ctx.run_state.bb.put(f"/2.0/repositories/{workspace}/{repo['slug']}", data=repo)
            logging.info(f"Repo: {repo['name']}\tGroup: {group}:{permission} -> {response.reason}")
        except Exception:
            logging.error(f"Repo: {repo['name']}\tGroup: {group}:{permission} -> {response.reason} :: {response.text}")
            sys.exit(1)
    else:
        url = f"{ctx.run_state.bb.url}/1.0/group-privileges/{workspace}/{_repo}/{workspace}/{group}"

        try:
            response = requests.put(url, data=permission, headers=headers,
                                    auth=(ctx.run_state.bb.username, ctx.run_state.bb.password))
            logging.info(f"Repo: {_repo}\tGroup: {group}:{permission} -> {response.reason}")
        except Exception:
            logging.error(f"Repo: {_repo}\tGroup: {group}:{permission} -> {response.reason} :: {response.text}")
            sys.exit(1)


@task()
def load_permissions(ctx, input="results.json", db="bitbucket.db"):
    """
    Loads the permissions json output from get_permissons task:

    :param input:
    :param db:

    :return:
    """

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

