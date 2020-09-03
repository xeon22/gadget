import yaml
import os

from gadget.tasks import utils
from pathlib import Path
from invoke import task

logger = utils.init_logging()


@task()
def load_conf(ctx, config=None):
    """ Initialize configuration with provided config or default config
    Parameter
    ================
    config: Location of config file to load
    """

    conf_locations = [
        Path("~/.tasker_conf.yaml").expanduser(),
        Path(os.path.join(Path.cwd(), 'tasker_conf.yaml')),
    ]

    if config is None:
        for location in conf_locations:
            logger.debug(location.as_posix())
            if location.exists():
                logger.debug(f"Found config file {location.as_posix()}")
                config = location.as_posix()
                break

    try:
        logger.info(f"Loading config: {config}")
        fh = open(config, 'rb')
        conf = yaml.load(fh.read(), Loader=yaml.FullLoader)
        ctx.config.main = conf
    except FileNotFoundError as e:
        logger.error(e)
        exit(1)
