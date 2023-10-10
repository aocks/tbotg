"""Main bot implementation.
"""

import logging
import typing

import telegram
from telegram import BotCommand
from telegram.ext import (
    Updater, DispatcherHandlerStop, CommandHandler)

from ox_secrets import server

from tbotg.core.bcmds import GenericCmd


class TelegramMainBot:
    """Telegram bot.
    """

    def __init__(self, name: str, cmds: typing.Optional[typing.Sequence[
            GenericCmd]] = None, webhook: typing.Optional[str] = None):
        self.bot_name = name
        self.cmds_dict = {c.name(): c for c in (cmds or [])}
        if not self.cmds_dict:
            self.cmds_dict = {c.name(): c for c in self.make_cmds()}
        for cmd_name, item in self.cmds_dict.items():
            logging.info('Creating command %s', cmd_name)
            item.set_bot_ref(self)
        self.validate()
        if webhook and webhook.lower() not in ('n', 'no', 'false'):
            logging.warning('Not starting polling since using webhook')
            self.run(start_polling=False)
        else:
            self.start_polling()

    def validate(self):
        """Validate bot setup correctly.
        """
        if not self.bot_name:
            raise ValueError('No name provided for bot.')
        if not self.cmds_dict:
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

    def run(self, updater=None, start_polling=True):
        """Run the bot.
        """
        self.docstrings = {}
        bot_name = self.get_bot_name()
        token = self.get_bot_token()
        self.bot = telegram.Bot(token=token)
        updater = Updater(token=token, use_context=True)
        self._add_handlers(updater)
        # The following will set commands for the bot in the menu.
        self.bot.set_my_commands([BotCommand(name, cmd.get_help_docs())
                                  for name, cmd in self.cmds_dict.items()
                                  if cmd.in_menu])
        self.updater = updater        
        if start_polling:
            logging.warning('start polling')
            updater.start_polling()

    def get_bot_token(self):
        """Retrive bot token.

        Sub-classes can override if they want a different way to
        obtain the secret bot token.
        """
        bot_name = self.get_bot_name()
        token = server.get_secret('token', category=bot_name)
        return token

    def handle_webhook_json(self, wh_json):
        update = telegram.Update.de_json(wh_json, self.bot)
        return self.updater.dispatcher.process_update(update)            

    def _add_handlers(self, updater):
        dispatcher = updater.dispatcher
        dispatcher.add_handler(CommandHandler('help', self.help_command))
        for name, cmd in self.cmds_dict.items():
            assert name == cmd.name(), (
                f'Mismatch in command name for {name} != {cmd.name()}.')
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
