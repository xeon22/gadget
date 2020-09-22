import types
import random, string, logging, os
import json
import yaml

from invoke import task, config


def objectify(hash):
    return types.SimpleNamespace(**hash)


def print_json(data):
    # jdata = json.loads(data)
    return json.dumps(data, indent=2, sort_keys=True)


@task()
def gen_client_name(ctx):
    alpha = random.choices(string.ascii_letters, k=1)
    num = random.choices(string.digits, k=3)

    id = ''.join(alpha + num).lower()

    logging.info(id)


@task()
def format_yaml(ctx, input, output=None):
    fh_in = open(input, 'rb')
    yaml_input = yaml.load(fh_in.read(), Loader=yaml.FullLoader)
    fh_in.close()

    if output is None:
        input_basedir = os.path.basename(input)
        input_basename = "foo"
        output = os.path.join(input_basedir, )
    with open(output, 'w') as fh:
        print()



