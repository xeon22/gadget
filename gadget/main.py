
from invoke import Program, Argument, Collection
from gadget import tasks
from gadget import __version__ as gadget_version

import logging

LOGGING_FORMAT = '[%(module)s:%(funcName)s:%(lineno)d] %(levelname)s: %(message)s'


class Gadget(Program):
    def core_args(self):
        core_args = super(Gadget, self).core_args()
        extra_args = [
            Argument(
                names=('bootstrap', 'bs'), help="Bootstrap a project from a remote manifest resource"
            ),
            Argument(
                names=('filter', 'fl'), help="Apply a filter to a list of resources in a project"
            ),
        ]
        return core_args + extra_args


program = Gadget(
    name="Gadget",
    binary="gadget",
    binary_names=["gadget"],
    version=gadget_version.__version__,
    namespace=Collection.from_module(tasks)
)

logging.basicConfig(
    format=LOGGING_FORMAT,
    level=logging.INFO
)
