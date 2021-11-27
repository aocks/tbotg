"""Examples to illustrate usage of tbotg library.
"""

import typing
import logging
import click

from telegram.ext import (
    DispatcherHandlerStop, MessageHandler, Filters)

from tbotg.core import main_bot
from tbotg.core.bcmds import GenericCmd, CmdWithArgs, ClickCmd


class HiFiveCmd(GenericCmd):
    """Example of how to create a generic command for tbotg.TelegramMainBot.

You can execute this with `/hifive` after you add it to the
main telegram bot. You will need to use `/setcommands` with botfather
if you want this to show up as list of available commands, but you
can execute it regardless of that once you add it to the bot.

This just responds by saing `'Hi Five: {data}'` where `{data}` is what
the user provides as the argument to the `/hifive` command.

    """

    def __init__(self, name: typing.Optional[str] = None):
        super().__init__(name=name or 'hifive')

    def main(self, update, context):
        """Override as required by GenericCmd to implement command.

The `update` and `context` are passed in from Telegram Python API.
        """
        data = str(context.args)
        self.respond(f'Hi five: {data}', update, context)
        raise DispatcherHandlerStop()  # so no other handlers run


@click.command()
@click.option('--shout', help='What to shout')
@click.option('--count', type=int, help='How many times to repeat.')
def shoutntimes(shout, count):
    "Shout something N times."
    return 'I will shout it %i times: %s' % (
        count, ', '.join([shout.upper()] * count))


class GenericEcho(GenericCmd):
    """Echo what user says (helpful for debugging).
    """

    def main(self, update, context):
        "Example bot message handler to just echo result."
        euser = update.effective_user.name
        context.bot.send_message(
            chat_id=update.message.chat_id,
            text='echo: %s (from chat_id "%s") from %s' % (
                update.message.text,
                update.message.chat_id, euser))

    def add_to_bot(self, bot, updater):
        logging.warning(
            'Adding cmd %s to main bot %s.\n%s', self.name(), bot, """
This will echo many things unless stopped by a raise DispatcherHandlerStop.
Also, it captures all messages so it may preclude other commands.
So you should add it as the last command and only use in debug/dev not
in production.
""")
        updater.dispatcher.add_handler(MessageHandler(
            Filters.text, self.main))


class ExampleInfoCmd(CmdWithArgs):
    """Example to how illustrate how to create a Telegram bot command.

This provides an example with many differnent types of paraemters a
user can provide to a telegram command.
    """

    def _make_default_cmd_args(self):
        return [
            click.Option(['--count'], help=(
                'Example of an integer type option.'), type=int),
            click.Option(['--level'], help=(
                'Example of a floating point option.'), type=float),
            click.Option(['--height'], help=(
                'Example of an integer range which must be in [0, 10]'),
                         type=click.IntRange(0, 10)),
            click.Option(['--date'], help=(
                'Example of datetime argument'), type=click.DateTime()),
            click.Option(['--why'], help=(
                'Example choice option ("short" means short answer).'),
                         type=click.Choice(
                             ['short', 'long']), default='short'),
            click.Option(['--really'], help='Example boolean',
                         type=bool),
            click.Option(['--mode'], help=(
                'Example of a string argument'), type=str)]

    def process_command(self, update, context):
        args = self.get_data(update)
        if args['why'] == 'short':
            why = ['This library illustrates how to create a Telegram bot.']
        elif args['why'] == 'long':
            why = ['---',
                   'This is an example to illustrate how to create Telegram',
                   'bots in python using the tbotg library. You can easily',
                   'sub-class the CmdWithArgs class, specify the command',
                   'options, and how to process the command and that is it!',
                   '---']
        result = [
            'Thanks for your interest in the tbotg library.'] + why + [
                'You entered the following command options:', '---'] + [
                    '%s = %s' % (n, v) for (n, v) in list(args.items())]
        self.respond('\n'.join(result), update, context)


class SayNTimes(CmdWithArgs):
    "Example command to say something n times."

    def _make_default_cmd_args(self):
        "Setup command parameters using click.Option"
        return [click.Option(['--say'], help='What to say'),
                click.Option(['--count', '-c'],
                             help='How many times to repeat.', type=int)]

    def process_command(self, update, context):
        "Implement command"
        args = self.get_data(update)
        self.respond('I will say it %i times: %s' % (
            args['count'], ', '.join([args['say']] * args['count'])),
                     update, context)


class ExampleBot(main_bot.TelegramMainBot):
    """Example bot.
    """

    def __init__(self, name='example_tbotg_bot', cmds=(), include_echo=True):
        if not cmds:
            cmds = self.make_cmds()
            if include_echo:
                cmds.append(
                    GenericEcho(name='echo', show_help=False))  # add echo last
        super().__init__(name, cmds)

    @classmethod
    def make_cmds(cls):
        "Make commands for bot."

        logging.debug('Making default commands for %s', cls)
        result = [
            HiFiveCmd(),
            ClickCmd(shoutntimes),
            SayNTimes(name='sayntimes'),
            ExampleInfoCmd(name='example_info')]
        return result
