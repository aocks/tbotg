"""Generic bot commands.
"""

import re
import logging
import typing
import collections

import click
from click import Option
from click.exceptions import BadParameter

from telegram import (InlineKeyboardMarkup, InlineKeyboardButton)
from telegram.ext import (
    MessageHandler, CommandHandler, Filters,
    CallbackQueryHandler, ConversationHandler)


class GenericCmd:
    """Generic command that the bot can handle.

You can sub-class this and override the `main` method to create a simple
command. See also CmdWithArgs for a more sophisticated structure.
    """

    def __init__(self, name: typing.Optional[str] = None,
                 show_help: bool = True):
        """Initializer.

        :param name=None:   String name. Must be provided.

        :param show_help=True:  Whether to include class docstring in help.

        """
        if not name:
            raise ValueError('Must provide name.')
        self._name = name
        self.show_help = show_help
        self.validate()

    def validate(self):
        """Do basic validation of parameters.
        """
        if not self._name:
            raise ValueError('No name provided')

    def name(self) -> str:
        "Return name of the command."
        return self._name

    def get_help_docs(self):
        "Show docstring for this command to user."
        return self.__doc__ or ''

    @staticmethod
    def get_message(update):
        """Find the message in an update.

This is helpful so you can have a simple way to pull out the message
object whether the update is from a callback_query or regular message.
        """
        main_message = None
        if update.message:
            main_message = update.message
        elif update.callback_query:
            main_message = update.callback_query.message
        return main_message

    @classmethod
    def respond(cls, msg: str, update, context):
        """Respond to the user with a message.

        :param msg:    String message to respond with.

        :param update, context: From telegram API.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:  Result of calling context.bot.send_message(...)

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Easy way to respond.

        """
        main_msg = cls.get_message(update)
        # pytype: disable=attribute-error
        result = context.bot.send_message(
            chat_id=main_msg.chat_id,
            text=msg)
        # pytype: enable=attribute-error
        return result

    def add_to_bot(self, bot, updater):
        """Example of how to enable a new command on the bot class.

By default, this will add a telegram `CommandHandler` so that when
the user does `/{self.name()}`, then `self.main()` will be called.

Sub-classes can override if they want to do fancier things.

For example, see the CmdWithArgs class which implements a conversation
handler to deal with parameters/arguments.
        """
        logging.info('Adding cmd %s to main bot %s', self.name(), bot)
        updater.dispatcher.add_handler(CommandHandler(
            self.name(), self.main))

    def main(self, update, context):
        """Main method to handle command, sub-classes must override.

        :param update, context:   From Telegram.

        """
        raise NotImplementedError


class CmdWithArgs(GenericCmd):
    """Generic command with arguments.

This provides a sophisticated way to let the user fill out the parameters
for a command, provide help, and so on without the programmer having to
write a lot of boilerplate code.

Basically, you just create a class like the example below which defines
the desired parameters and a main method and then CmdWithArgs will
handle interactions with the user to fill out the parameters (note: you
will still need to add the command to the main bot as described in
the docs for tbotg.core.main_bot.TelegramMainBot).

    class SayNTimes(CmdWithArgs):
        "Example command to say something n times."

        def _make_default_cmd_args(self):
            "Setup command parameters using Option"
            return [Option(['--say'], help='What to say'),
                    Option(['--count', '-c'],
                                 help='How many times to repeat.', type=int)]

        def process_command(self, update, context):
            "Implement command"
            args = self.get_data(update)
            self.respond('I will say it %i times: %s' % (
                args['count'], ', '.join([args['say']] * args['count'])),
                         update, context)

    """

    STATE_REVIEW = 0
    STATE_EDIT = 1

    VALID_OPT_NAME_RE = re.compile('^[_a-zA-z0-9]+$')

    def __init__(self, name: typing.Optional[str] = None,
                 cmd_args: typing.Sequence[
            click.Option] = ()):
        """Initializer.

        :param name=None:    String name of command.

        :param cmd_args:  Sequence of click.Option instances representing
                          command arguments. Can be None or [] if you want
                          to use `_make_default_cmd_args` instead.

        """
        self._info = {}  # see store_data, get_data, clear_data methods
        self.cmd_args = cmd_args or self._make_default_cmd_args()
        self.cmd_args_map = collections.OrderedDict([
            (item.name, item) for item in self.cmd_args])
        super().__init__(name=name)

    def process_command(self, update, context) -> typing.Union[None, str]:
        """Sub-classes should override to process user submitted command.

Use `self.get_data(update)` to get the user supplied values for parameters
in self.cmd_args and then process the command.

On success, process_command should return `None`. If an error occurs,
it should return a string to show the user. It can also use send_message
or other Telegram features to report the error to the user as well.
        """
        raise NotImplementedError

    def _make_default_cmd_args(self) -> typing.List[Option]:
        """Make default list of command arguments.

This is called by `__init__` if `cmd_args` is empty. Sub-classes should
override if desired to make the desires parameters.

All elements of returned list must be click.Option instances (e.g.,
not click.Argument or other click parametes) because click.Option is
easiest to standardize and work with for this framework.
        """
        logging.debug('Calling %s._make_default_cmd_args',
                      self.__class__.__name__)
        return []

    def validate(self):
        """Do basic validation of things in self.
        """
        super().validate()
        if not self.cmd_args:
            raise ValueError('No cmd_args')
        my_re = re.compile(self.VALID_OPT_NAME_RE)
        for item in self.cmd_args:
            if not my_re.match(item.name):
                raise ValueError(
                    'Invalid option name "%s" does not match regexp %s' % (
                        item.name, self.VALID_OPT_NAME_RE))

    def convert_value(self, opt_name: str, text: str):
        """Convert user supplied value using click.Option.

        :param opt_name:    String name of option value is for.

        :param text:        Value provided by user.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:   Converted value (or raise an exception).

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:   Convert user supplied value to desired type using click.

        """
        opt = self.cmd_args_map[opt_name]
        result = opt.type.convert(value=text, param=None, ctx=None)
        return result

    def store_data(self, update, data: typing.Dict[
            str, typing.Any]) -> typing.Dict[str, typing.Any]:
        """Store data user has provided for command arguments.

        :param update:    Passed from Telegram API.

        :param data:      Dictionary where keys are string names in
                          self.cmd_args_map (i.e., the names of valid
                          arguments user can provide) and values are
                          what the user has provided for those arguments.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:  Data stored so far.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Store data we are collecting from the user for the
                  command in a smart way so that different users or
                  different commands don't clobber each other.

                  *IMPORTANT*: Do *NOT* access `self._info` directly.
                               Use store_data, get_data, and clear_data.

        """
        message = self.get_message(update)
        chat_id = message.chat_id
        record = self._info.get((self.name(), chat_id), {})
        if not record:
            self._info[(self.name(), chat_id)] = record
        record.update(**data)
        return record

    def clear_data(self, update):
        """Like store_data except clears all data for the command from user.

        :param update:    Passed from Telegram API.
        """
        message = self.get_message(update)
        chat_id = message.chat_id
        key = (self.name(), chat_id)
        dead = self._info.pop(key, None)
        logging.debug('for key %s, cleared data %s', key, dead)

    def get_data(self, update) -> typing.Dict[str, typing.Any]:
        """Like store_data except gets all data for the command from user.

        :param update:    Passed from Telegram API.
        """

        message = self.get_message(update)
        chat_id = message.chat_id
        return self._info.get((self.name(), chat_id), {})

    def main(self, update, context):
        """Main entry point for command; just calls self.review.
        """
        return self.review(update, context)

    def review(self, update, context):
        """Handler for when user is reviewing parameters for command.
        """
        _ = context
        reply_markup = self._make_main_reply_markup(update)
        update_message = self.get_message(update)
        update_message.reply_text(text=f'Preparing command: {self.name()}',
                                  reply_markup=reply_markup)
        return self.STATE_REVIEW

    def _make_main_reply_markup(self, update):
        """Helper to make reply markup to show user main menu.

This method puts together an inline keyboard showing current parameters
user has provided along with buttons to edit each parameter, see help,
cancel, or confirm.
        """
        data = self.get_data(update)
        cur = [(opt.name, data.get(opt.name, '')) for opt in self.cmd_args]
        reply_markup = (InlineKeyboardMarkup([
            [InlineKeyboardButton(f'{name} = "{value}" (Edit)', callback_data=(
                f'do#{self.name()}#edit#{name}')),
             InlineKeyboardButton('(?)', callback_data=(
                 f'do#{self.name()}#helparg#{name}'))]
            for name, value in cur] + [[InlineKeyboardButton(
                f'help on command {self.name()}',
                callback_data=f'do#{self.name()}#help')]] + [[
                    InlineKeyboardButton(name, callback_data=(
                        f'do#{self.name()}#{name}'))
                    for name in ['cancel', 'confirm']]]))
        return reply_markup

    def _tg_callback(self, update, context):
        """Helper to handle telegram callback.

This handles what to do when the user pushes a button on the inline keyboard
created by _make_main_reply_markup.

Basically, the _make_main_reply_markup creates an inline keyboard
with callback data of the form `'do#{name}#{action}#{values}'` and
here we parse apart that data and handle the action.
        """
        data = update.callback_query.data
        msg, name, action, *values = data.split('#')
        assert msg == 'do' and name == self.name(), (
            f'Invalid callback data {data}')
        main_msg = self.get_message(update)
        context.bot.edit_message_reply_markup(      # removes old
            main_msg.chat_id, main_msg.message_id)  # inline keyboard
        if action == 'edit':
            return self._handle_edit_button(data, values, update, context)
        if action == 'helparg':
            return self._handle_helparg_button(data, values, update, context)
        if action == 'cancel':
            return self.cancel(update, context)
        if action == 'confirm':
            return self.confirm(update, context)
        if action == 'help':
            return self.help(update, context)
        raise ValueError('Unexpected action "%s"' % str(action))

    def _handle_edit_button(self, data, values, update, context):
        """Helper to handle case when user clicks edit on inline keyboard.

We enter the STATE_EDIT conversation state and then interpret whatever
the usesr types as the desired parameter value.

So that we can keep track of what parameter the user is editing, we put
the parameter name into context.user_data.
        """
        if len(values) != 1:
            raise ValueError(
                'Wrong number of values (%i) in %s for data %s' % (
                    len(values), values, data))
        my_opt = self.cmd_args_map.get(values[0], None)
        if not my_opt:
            raise ValueError(
                'Unknown option to edit "%s"' % str(values[0]))
        kbd_info = None  # force new keyboard since that is nicer
        if kbd_info is None:  # can't reuse keyboard; make new one
            logging.debug('making new keyboard')
            resp = self.respond(
                'Enter desired value for "%s" (type %s):' % (
                    my_opt.name, my_opt.type), update, context)
            kbd_info = (values[0], resp.message_id)
        context.user_data[f'#do#edit#{self.name()}'] = kbd_info
        return self.STATE_EDIT

    def _handle_helparg_button(self, data, values, update, context):
        """Handle case when user clicks help for param on inline keyboard.
        """
        if len(values) != 1:
            raise ValueError(
                'Wrong number of values (%i) in %s for data %s' % (
                    len(values), values, data))
        my_opt = self.cmd_args_map.get(values[0], None)
        if my_opt is None:
            raise ValueError(
                'Unknown option to help arg "%s"' % str(values[0]))
        if my_opt.help:
            text = f'Help for parameter "{my_opt.name}": {my_opt.help}'
        else:
            text = f'No help available for {my_opt.name}.'
        result = self.review(update, context)
        self.respond(text, update, context)
        return result

    def edit(self, update, context):
        """Telegram handler for when user is editing a parameter value.

Once we enter the STATE_EDIT conversation state when the user clicks
on a parmeter to edit in the inline keyboard, we use this method to
process whatever the user provides as the parameter value.

We need to look at context.user_data to get the name of the parameter
that the use was editing. Then we try to call self.convert_value to
convert the text to the right type and then save it with self.store_data.

Then we go back into STATE_REVIEW and
        """
        msg = self.get_message(update)
        opt_name, msg_id = context.user_data.pop(
            f'#do#edit#{self.name()}', (None, None))
        if opt_name is None:  # can get here if user types before choosing
            result = self.review(update, context)
            self.respond('I did not understand.\n'
                         'Please make a selection from above menu.',
                         update, context)
            return result
        try:
            value = self.convert_value(opt_name, msg.text)
        except Exception as problem:  # pylint: disable=broad-except
            if not isinstance(problem, (ValueError, KeyError,
                                        BadParameter)):
                logging.exception(problem)  # log it since it looks weird
            result = self.review(update, context)
            self.respond('Problem with value "%s": %s.\n%s' % (
                msg.text, problem, 'Please fix and try again.'),
                         update, context)
            return result

        self.store_data(update, {opt_name: value})
        context.bot.edit_message_reply_markup(
            msg.chat_id, message_id=msg_id,
            reply_markup=self._make_main_reply_markup(update))

        return self.STATE_REVIEW

    def help(self, update, context):
        """Provide help to the user when they click help on inline keyboard.
        """
        my_docs = self.get_help_docs()
        if not my_docs:
            text = 'No documentation available for command.'
        else:
            text = 'Instructions for command %s:\n\n%s' % (
                self.name(), my_docs)
        text += '\n------\nParameters:\n\n' + '\n'.join([
            '%s: %s' % (opt.name, opt.help) for opt in self.cmd_args])
        result = self.review(update, context)
        self.respond(text, update, context)
        return result

    def confirm(self, update, context):
        """Try to call `process_command` when user hits confirm on inline kbd.
        """
        problem = 'unknown error'
        try:
            problem = self.process_command(update, context)
        except KeyError as bad:
            if str(bad).strip("'") in self.cmd_args_map:
                problem = 'Error with %s; %s' % (
                    str(bad), 'did you provide that parameter?')
            else:
                problem = str(bad)
        except Exception as bad:  # pylint: disable=broad-except
            if not isinstance(bad, (ValueError, BadParameter)):
                logging.exception(bad)  # log weird looking error
            problem = str(bad)
        if problem:
            result = self.review(update, context)
            self.respond('problem: %s\n\nPlease retry.' % str(problem),
                         update, context)
            return result

        self.respond(f'Successfully finished {self.name()}', update, context)
        self.clear_data(update)
        return ConversationHandler.END

    def cancel(self, update, context):
        """When user hits cancel on inline keyboard, cancel command.
        """
        self.respond('cancelled', update, context)
        return ConversationHandler.END

    def add_to_bot(self, bot, updater):
        logging.info('Adding cmd %s to main bot %s', self.name(), bot)
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler(self.name(), self.main)],
            states={
                self.STATE_REVIEW: [
                    CallbackQueryHandler(
                        self._tg_callback, '^do#{self.name()}#.*'),
                    MessageHandler(Filters.text, self.edit)],
                self.STATE_EDIT: [
                    MessageHandler(Filters.text, self.edit)],
                },
            fallbacks=[
                CommandHandler('cancel', self.cancel)])
        updater.dispatcher.add_handler(conv_handler)
        updater.dispatcher.add_handler(CommandHandler('cancel', self.cancel))


class ClickCmd(CmdWithArgs):
    """Convet a click command to a CmdWithArgs.

Simply do something like `ClickCmd(YOUR_CLICK_COMMAND)` to turn a click
command line object into a Telegram command.

For example, if you define a click command called `shoutntimes` via:

    @click.command()
    @click.option('--shout', help='What to shout')
    @click.option('--count', type=int, help='How many times to repeat.')
    def shoutntimes(shout, count):
        "Shout something N times."
        return 'I will shout it %i times: %s' % (
            count, ', '.join([shout.upper()] * count))

You could turn this into a telegram command via `ClickCmd(shoutntimes)`.

See the `ExampleBot` in `tbotg.core.examples` for a full example.
    """

    def __init__(self, click_cmd, name=None):
        self.click_cmd = click_cmd
        super().__init__(name=name or click_cmd.name)

    def get_help_docs(self):
        return self.click_cmd.help

    def _make_default_cmd_args(self):
        return self.click_cmd.params

    def process_command(self, update, context):
        args = self.get_data(update)
        result = self.click_cmd.callback(**args)
        self.respond(result, update, context)
