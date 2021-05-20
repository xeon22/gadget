import json
import logging
import os
import locale


from invoke import task
from gadget.tasks import init, utils
from rich.console import Console
from rich.table import Table, Column

locale.setlocale(locale.LC_ALL, 'en_US')
console = Console()


@task(pre=[init.load_conf])
def init(ctx):
    pass


@task()
def process_usage(ctx, input):
    console.log(f"Loading input file {input}")
    raw_data = json.load(open(input, 'r'))

    table = Table(
        "AppName",
        Column(1, header="Lines Total", justify='right'),
        Column(2, header="Lines Percent", justify='right'),
        Column(3, header="Avg Flow Rate", justify='right'),
        title="Applications"
    )

    for item in raw_data['hosts']:
        table.add_row(
            item['name'],
            locale.format_string('%d', item['current_total'], grouping=True),
            f"{str(round(item['percentage_of_total'], 2))}%",
            f"{str(round(item['flow_rate_avg']))} l/s"
        )

    console.print(table)
