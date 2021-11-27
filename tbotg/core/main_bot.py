"""Main bot implementation.
"""

import logging
import typing

import telegram
from telegram.ext import (
    Updater, DispatcherHandlerStop, CommandHandler)

from ox_secrets import server

from tbotg.core.bcmds import GenericCmd


class TelegramMainBot:
    """Telegram bot.
    """

    def __init__(self, name: str, cmds: typing.Optional[typing.Sequence[
            GenericCmd]] = None):
        self.bot_name = name
        self.cmds = cmds
        if not self.cmds:
            self.cmds = self.make_cmds()
        self.validate()
        self.run()

    def validate(self):
        """Validate bot setup correctly.
        """
        if not self.bot_name:
            raise ValueError('No name provided for bot.')
        if not self.cmds:
            raise ValueError('No commands provided for bot.')

    @classmethod
    def make_cmds(cls) -> typing.Sequence[GenericCmd]:
        """Return sequence of GenericCmd.

Intended for sub-classes to override to make `cmds` if `cmds` not
provided in `__init__`.
        """
        logging.warning('Making default commands for %s; %s', cls,
                        'did you forget to add commands?')
        return []

    def get_bot_name(self):
        "Reutrn bot name"
        return self.bot_name

    def run(self, updater=None):
        """Run the bot.
        """
        self.docstrings = {}
        bot_name = self.get_bot_name()
        token = server.get_secret('token', category=bot_name)
        self.bot = telegram.Bot(token=token)
        updater = Updater(token=token, use_context=True)
        self._add_handlers(updater)
        logging.warning('start polling')
        updater.start_polling()

    def _add_handlers(self, updater):
        dispatcher = updater.dispatcher
        dispatcher.add_handler(CommandHandler('help', self.help_command))
        for cmd in self.cmds:
            name = cmd.name()
            if cmd.show_help:
                self.docstrings[name] = cmd.get_help_docs()
                assert isinstance(self.docstrings[name], str), (
                    'Bad docs for %s' % (name))
            logging.warning('Registering command: %s', name)
            cmd.add_to_bot(self.bot, updater)

    def help_command(self, update, context):
        """Provide documentation for telegram commands.
        """
        _ = update, context
        if len(context.args) == 1:
            name = context.args[0].strip().lstrip('/')
            if name in self.docstrings:
                result = 'Help for command %s:\n%s' % (
                    name, self.docstrings[name])
            else:
                result = 'No help available for "%s":' % (str(name))
        elif not context.args:
            result = '\n'.join([
                'Help is available for the following commands:\n'] + [
                    '/%s : %s' % (n.ljust(10),
                                  self.docstrings[n].split('\n')[0])
                    for n in sorted(self.docstrings)] + [
                        '',
                        'Type "/help NAME" for one of the topics above.'])
        else:
            result = 'Wrong arguments: %s' % (
                'try either "/help NAME" or just "/help".')

        context.bot.send_message(
            chat_id=update.message.chat_id, text=result,
            reply_to_message_id=update.message.message_id)
        raise DispatcherHandlerStop()  # so no other handlers run

    @staticmethod
    def start_command(update, context):
        """Start the telegram bot in the current conversation.

You only need to use this command the first time you invite the bot to
a conversation or group. It does basic initialization and setup (e.g.,
creating the database to track things).

        """
        if context.args:
            result = 'No args allowed; not starting'
        else:
            result = 'Started'
        context.bot.send_message(
            chat_id=update.message.chat_id, text=result)
        raise DispatcherHandlerStop()  # so no other handlers run

    def send_message(self, text, **kwargs):
        """Send message to the bot.

        :param text:        String text to send.

        :param **kwargs:    Passed to self.bot.send_message.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Send given text to bot channel.

        """
        self.bot.send_message(text=text, **kwargs)
