import yaml
import os
import logging

from gadget.tasks import utils
from pathlib import Path
from invoke import task

GADGET_CONF = "gadget"

@task()
def load_conf(ctx, config=None):
    """ Initialize configuration with provided config or default config
    Parameter
    ================
    config: Location of config file to load
    """

    conf_locations = [
        Path(f"~/{GADGET_CONF}.yaml").expanduser(),
        Path(f"~/{GADGET_CONF}.yml").expanduser(),
        Path(os.path.join(Path.cwd(), f"{GADGET_CONF}.yaml")),
        Path(os.path.join(Path.cwd(), f"{GADGET_CONF}.yml")),
    ]

    if config is None:
        for location in conf_locations:
            logging.debug(location.as_posix())
            if location.exists():
                logging.debug(f"Found config file {location.as_posix()}")
                config = location.as_posix()
                break

    try:
        logging.info(f"Loading config: {config}")
        fh = open(config, 'rb')
        conf = yaml.load(fh.read(), Loader=yaml.FullLoader)
        ctx.config.main = conf
    except FileNotFoundError as e:
        logging.error(e)
        exit(1)
