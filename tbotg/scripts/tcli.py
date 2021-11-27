"""Tbotg command line interface.
"""

import logging
import importlib

import click
from click.exceptions import BadParameter


# Will hold information about bots
MY_BOT_INFO = {}


@click.group()
def cli():
    "Tbotg command line interface."


@cli.command()
@click.option('--bot_cls', default='ExampleBot', help=(
    'Name of bot class to load from --module.'))
@click.option('--module', default='tbotg.core.examples',
              help='String path to module for bot_cls to serve.')
@click.option('--package', default=None)
@click.option('--with_name', default=None, help=(
    'If provided, passed as name parameter to bot_cls to override default.'))
def serve(bot_cls, module, package, with_name):
    "Run the server to listen and respond to Telegram messages."

    if with_name in MY_BOT_INFO:
        raise ValueError('Refusing to serve already running bot %s' % (
            str(with_name)))
    my_mod = importlib.import_module(module, package=package)
    klass = getattr(my_mod, bot_cls, None)
    if not klass:
        raise BadParameter(
            'Unable to find bot named %s in module %s' % (bot_cls, my_mod))
    logging.warning('Running task bot until killed')
    bkwargs = {}
    if with_name:
        bkwargs['name'] = with_name
    MY_BOT_INFO[with_name] = klass(**bkwargs)
    logging.warning('Telegram %s bot now running as thread',
                    MY_BOT_INFO[with_name].get_bot_name())


@cli.group()
def info():
    "Commands related to info about the system"


@cli.group()
def tasks():
    "Commands related to tasks"


def prep_cmd_line():
    """Prepare command line by adding more sub-command lines.
    """


def main(**kwargs):
    "Run cmd line"
    prep_cmd_line()
    cli(**kwargs)


if __name__ == '__main__':
    main(auto_envvar_prefix='TBOTG')
