
import json
import requests

from datetime import datetime
from invoke import task, config, call
from rich.table import Table
from rich.console import Console

from gadget.tasks import init

from azure.graphrbac import GraphRbacManagementClient
from azure.common.client_factory import get_client_from_cli_profile
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient


console = Console()


@task(pre=[init.load_conf])
def init(ctx):
    print()


@task(default=True, optional=['debug'])
def list_users(ctx, manifest=None, debug=False, role='contributor'):
    """ Initialize configuration using local* or remote project manifest file
    Parameter
    ================
    manifest: remote location for the remote project manifest file. default is None which will use local manifest if avaliable
    """

    table = Table(
        "Email",
        "DisplayName",
        "Enabled",
        "UserState",
        "Created",
        "LastLogin",
        "Type",
        title="Artifacts",
    )

    client = get_client_from_cli_profile(GraphRbacManagementClient)

    for user in client.users.list():
        # [ 'account_enabled', 'additional_properties', 'as_dict', 'deletion_timestamp', 'deserialize', 'display_name', 'enable_additional_properties_sending', 'from_dict', 'given_name', 'immutable_id', 'is_xml_model', 'mail', 'mail_nickname', 'object_id', 'object_type', 'serialize', 'sign_in_names', 'surname', 'usage_location', 'user_principal_name', 'user_type', 'validate']

        # console.print(dir(user))
        # console.print(user.additional_properties)

        input_datefmt = '%Y-%m-%dT%H:%M:%SZ'
        output_datefmt = '%b %d %Y'

        table.add_row(
            user.mail,
            user.display_name,
            str(user.account_enabled),
            user.as_dict().get('userState'),
            datetime.strftime(datetime.strptime(user.as_dict().get('createdDateTime'), input_datefmt), output_datefmt),
            datetime.strftime(datetime.strptime(user.as_dict().get('refreshTokensValidFromDateTime'), input_datefmt), output_datefmt),
            user.user_type,
        )

    console.print(table)

    # ucp = UserCreateParameters(
    #     user_principal_name="catodevopsteam_capco.com#EXT#@catosaasdev.onmicrosoft.com",
    #     account_enabled=True,
    #     display_name='Capco Digital Bot',
    #     ##I test in my lab, if I use this line, I will get error log and could not create a user.
    #     #additional_properties={
    #     #    "signInNames": [{"type": "emailAddress", "value": ""}]
    #     #},
    #     ##user_type only support Member or Guest, see this link https://docs.microsoft.com/en-us/python/api/azure.graphrbac.models.usercreateparameters?view=azure-python
    #     user_type="Guest",
    #     mail_nickname = 'catodevopsteam_capco.com#EXT#',
    #     password_profile=PasswordProfile(
    #         password='',
    #         force_change_password_next_login=False
    #     )
    # )

    # user = client.users.create(ucp)

@task
def add_user(ctx):

    params = {
        "invitedUserDisplayName": "Capco Digital Bot",
        "invitedUserEmailAddress": "catodevopsteam@capco.com",
    }

    #
    #  Get the bearer token for authentication
    #
    client = get_client_from_cli_profile(GraphRbacManagementClient)
    # token = client.objects.config.credentials.signed_session().headers.get('Authorization')
    token = 'Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsIng1dCI6IkN0VHVoTUptRDVNN0RMZHpEMnYyeDNRS1NSWSIsImtpZCI6IkN0VHVoTUptRDVNN0RMZHpEMnYyeDNRS1NSWSJ9.eyJhdWQiOiJodHRwczovL2dyYXBoLndpbmRvd3MubmV0LyIsImlzcyI6Imh0dHBzOi8vc3RzLndpbmRvd3MubmV0LzM1NTgzOWVlLWZhMWYtNDRkOS1iN2RlLWY4Mzk1NTYwOWI1Mi8iLCJpYXQiOjE1ODg3NzI2NjEsIm5iZiI6MTU4ODc3MjY2MSwiZXhwIjoxNTg4Nzc2NTYxLCJhY3IiOiIxIiwiYWlvIjoiQVhRQWkvOFBBQUFBNmNLb3hJQ0l4S05maENNMHdrZVE5Wi9jVURlVFJxenh1d21MSU8zUjlPR3hCbkFwcUo0dGFlVFRCU0N6aC8za0VhcHl5aXREckE3dHRMRW1sTFR6OG5pWjRWeEt3dXJjc2N4ZGpuU1hpM2wyMHQ3ZithTGJMQ2lkRTlWOGVKQ3hVZ2FrL0pMV21TdVZGNVdGcUlpbU53PT0iLCJhbHRzZWNpZCI6IjU6OjEwMDMwMDAwQTY1ODZCNDkiLCJhbXIiOlsicHdkIl0sImFwcGlkIjoiMDRiMDc3OTUtOGRkYi00NjFhLWJiZWUtMDJmOWUxYmY3YjQ2IiwiYXBwaWRhY3IiOiIwIiwiZW1haWwiOiJtYXJrLnBpbWVudGVsQGNhcGNvLmNvbSIsImZhbWlseV9uYW1lIjoiUGltZW50ZWwiLCJnaXZlbl9uYW1lIjoiTWFyayIsImlkcCI6Imh0dHBzOi8vc3RzLndpbmRvd3MubmV0LzliYWMzOWRjLWE3YWItNGEyMC05YThiLTg4NWM2MjM1YjZjNS8iLCJpcGFkZHIiOiIyNC41My4xMDUuMjE5IiwibmFtZSI6IlBpbWVudGVsLCBNYXJrIiwib2lkIjoiYWVmYWM2M2YtNDM5OC00NDIxLTk4ZmUtMjRiODUyZTUxMGRlIiwicHVpZCI6IjEwMDMyMDAwNEZFMDZCOUIiLCJyaCI6IjAuQVRjQTdqbFlOUl82MlVTMzN2ZzVWV0NiVXBWM3NBVGJqUnBHdS00Qy1lR19lMFkzQU9vLiIsInNjcCI6IjYyZTkwMzk0LTY5ZjUtNDIzNy05MTkwLTAxMjE3NzE0NWUxMCIsInN1YiI6ImxxZW4xZTM5Vkx3SWJVcFNNcGtDUUU2YTdTSDh4cGNMbmpkVk01QkxCZDgiLCJ0ZW5hbnRfcmVnaW9uX3Njb3BlIjoiTkEiLCJ0aWQiOiIzNTU4MzllZS1mYTFmLTQ0ZDktYjdkZS1mODM5NTU2MDliNTIiLCJ1bmlxdWVfbmFtZSI6Im1hcmsucGltZW50ZWxAY2FwY28uY29tIiwidXRpIjoiOTE3OGNqaU43VTZOV3dRZVFhVzhBQSIsInZlciI6IjEuMCJ9.B-cYWFaBS3B8tFXrYunBWGMTMAIFlwGeLrOc7YZjG52dhRiTktWKx5SBrPJxJ0qIp67BBGYL-k2awG_TcHjKfN9zztMvpOa5sKqTwHIgpMrqnsGSHpgJG9FUXfrA1iPhbja5XCKcMGHWQH3DOi2nCBP6RXC0ToYkXVjYTFXHAqXvxXGFij1mMbsnLyWLt2HwA_paE09qlyuhW6j9kzxDEHJ6XMpMt1MGXS9vLuXo25VUnL0DLxRBEyIuBNZDWicutgJT6rTrALJyG_7er1clqn9gqDhCxDft9eRLWD8QQxEHh0FPzL858HfK2XiXlp3cQ1vrs8edCP0b7hPG3QPtxQ'

    my_headers = {
        'Authorization': token,
        'Content-Type': 'application/json'
    }

    r = requests.post(
        'https://graph.microsoft.com/v1.0/invitations', 
        headers=my_headers,
        json=json.dumps(params)
    )

    print(json.dumps(r.json(), indent=2))

    from requests import Request, Session

    s = Session()

    req = Request('POST', 'https://graph.microsoft.com/v1.0/invitations', json=json.dumps(params), headers=my_headers)
    prepped = req.prepare()

    resp = s.send(prepped)

    print(resp.status_code)

    print(f'curl -X GET -H "Authorization: {token}" -H "Content-Type: application/json" https://graph.microsoft.com/v1.0/invitations -d \'{json.dumps(params)}\'')


@task()
def get_secret(ctx, keyvault, secret):
    credential = DefaultAzureCredential()

    secret_client = SecretClient(vault_url="https://my-key-vault.vault.azure.net/", credential=credential)
    secret = secret_client.get_secret("secret-name")

    print(secret.name)
    print(secret.value)