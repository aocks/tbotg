"""Generic bot commands.
"""

import weakref
import datetime
import shlex
import copy
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


from tbotg.core.callback_tools import CallbackData


class GenericCmd:
    """Generic command that the bot can handle.

You can sub-class this and override the `main` method to create a simple
command. See also CmdWithArgs for a more sophisticated structure.
    """


    def __init__(self, name: typing.Optional[str] = None,
                 show_help: bool = True, in_menu: bool = True):
        """Initializer.

        :param name=None:   String name. Must be provided.

        :param show_help=True:  Whether to include class docstring in help.

        :param in_menu=True:  Whether to show command in Telegram menu.

        """
        if not name:
            raise ValueError('Must provide name.')
        self._name = name
        self._in_menu = in_menu
        self._main_bot_ref = None
        self.show_help = show_help
        self.validate()

    @property
    def in_menu(self):
        "Whether the bot should be included in the menu"
        return self._in_menu

    def set_bot_ref(self, bot):
        """Set weak reference to main telegram bot.
        """
        self._main_bot_ref = weakref.ref(bot)

    def get_bot_ref(self):
        """Get reference to main telegram bot.
        """
        return self._main_bot_ref()

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
    def create_callback_data(key: str = 'callback', cmd: str = None,
                             action: str = 'invoke', **kwargs) -> str:
        """Create string callback data for telegram bot in canonical way.

        See docs for CallbackData, CallbackData.__init__, CallbackData.to_string
        """
        return CallbackData(key, cmd, action, **kwargs).to_string()

    @staticmethod
    def parse_callback_data(data: str):
        """Decode string callback data.

        See docs for CallbackData and CallbackData.from_string.
        """
        cb_data = CallbackData.from_string(data)
        return cb_data.key, cb_data.cmd, cb_data.action, cb_data.values

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
    def respond(cls, msg: str, update, context, **kwargs):
        """Respond to the user with a message.

        :param msg:    String message to respond with.

        :param update, context: From telegram API.

        :param **kwargs:  Passed to context.bot.send_message. For example,
                          you could include parse_mode='MarkdownV2'.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:  Result of calling context.bot.send_message(...)

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Easy way to respond.

        """
        main_msg = cls.get_message(update)
        # pytype: disable=attribute-error
        kwargs = dict(kwargs)
        kwargs.update(chat_id=main_msg.chat_id, text=msg)
        try:
            result = context.bot.send_message(**kwargs)
        except Exception as problem:
            logging.warning('Unable to send_message(**%s) because %s',
                            kwargs, problem)
            raise
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
                 cmd_args: typing.Sequence[click.Option] = (),
                 group_force_pm: bool = True):
        """Initializer.

        :param name=None:    String name of command.

        :param cmd_args:  Sequence of click.Option instances representing
                          command arguments. Can be None or [] if you want
                          to use `_make_default_cmd_args` instead.

        :param group_force_pm=True:  If True, then the bot will tell the
                                     user to do the command in private chat
                                     instead of group.
        """
        self._info = {}  # see store_data, get_data, clear_data methods
        self.group_force_pm = group_force_pm
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
                  different commands don't clobber each other. This also
                  calls self.clean_str and self.clean_generic_data so
                  sub-classes can override those to clean parameter values
                  if desired.

                  *IMPORTANT*: Do *NOT* access `self._info` directly.
                               Use store_data, get_data, and clear_data.

        """
        message = self.get_message(update)
        chat_id = message.chat_id
        record = self._info.get((self.name(), chat_id), {})
        if not record:
            self._info[(self.name(), chat_id)] = record
        clean_data = {k: (self.clean_str(k, v) if isinstance(v, str)
                          else self.clean_generic_data(k, v))
                      for k,v in data.items()}
        record.update(**clean_data)
        return record

    @classmethod
    def clean_str(cls, key: str, value: str) -> str:
        """Clean string value in key/value pair used in store_data.

        :param key:    Key or name for parameter.

        :param value:  Parameter value.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:  Cleaned version of value with weird characters replaced.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Replace weird characters with '_'.  Sub-classes can override
                  this if desired to clean or not clean certain parameters.
        """
        logging.debug('Ignoring key %s, but sub-classes can use it.', key)
        return re.sub('[^a-zA-Z0-9 \n.]', '_', value)

    @staticmethod
    def clean_generic_data(key: str, value):
        """Clean parameter value in key/value pair used in store_data.

        :param key:    Key or name for parameter.

        :param value:  Parameter value.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:  Cleaned version of value.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Clean parameter value.  Does nothing by default but
                  sub-classes can override this if desired to clean or
                  not clean certain parameters.

        """
        logging.debug('Ignoring key %s, but sub-classes can use it.', key)
        return value

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
        """Main entry point for command.

First sets defaults and then calls self.review.
        """
        msg = self.get_message(update)
        logging.info('Starting main for %s of chat.type %s',
                     self.name(), msg.chat.type)
        if self.group_force_pm and msg.chat.type != 'private':
            my_name = context.bot.get_me()['username']
            self.respond('@' + msg.from_user.username + ' : ' + (
                'please run command /%s in private chat: %s' % (
                    self.name(),
                    f'https://telegram.me/{my_name}?start=start')),
                         update, context, disable_notification=True)
            return ConversationHandler.END
        self._prep_args(update, context)
        return self.review(update, context)

    def end_without_review(self, update, context):
        """Sub-classes can override to end without showing review options.

        By default we allow the user to review the command until they
        either hit confirm or cancel. But sometimes commands may be able
        to decide they have enough information to short circuit the review
        process. In that case, a sub-class should override this method to

          1. Decide if no review should happen.
          2. Send any messages to the user (e.g., by calling process_command).
          3. Return False to cause the conversation to end before review.
        """
        _ = update, context
        return False

    def review(self, update, context):
        """Handler for when user is reviewing parameters for command.
        """
        if self.end_without_review(update, context):
            return ConversationHandler.END

        reply_markup = self._make_main_reply_markup(update)
        update_message = self.get_message(update)
        update_message.reply_text(text=f'Preparing command: {self.name()}',
                                  reply_markup=reply_markup)

        return self.STATE_REVIEW

    @staticmethod
    def _fake_callback(*args, **kwargs):
        """Fake callback for use by _prep_args in click parsing.
        """
        logging.info('Called _fake_callback with args: %s, kwargs: %s',
                     args, kwargs)

    def _prep_args(self, update, context):
        """Helper method to prepare arguments from data.

This helper is intended to be called by the main method to try and
prepare arguments (e.g., default arguments or command line arguments).
        """
        pcmd = click.Command(
            name=self.name(), callback=self._fake_callback, params=[
                copy.deepcopy(c) for c in self.cmd_args])
        # pytype: disable=attribute-error
        with click.Context(pcmd, resilient_parsing=True) as ctx:
            # pytype: enable=attribute-error
            if context.args is not None:
                split_args = shlex.split(' '.join(context.args))
                pcmd.parse_args(ctx,               # make a copy of split_args
                                list(split_args))  # since parse_args changes it
                logging.info('For %s, parsed command line: %s',
                             self.name(), split_args)
            if ctx.params:
                logging.info('Storing parsed args: %s', ctx.params)
                self.store_data(update, ctx.params)
        data = self.get_data(update)
        for opt in self.cmd_args:
            value = data.get(opt.name, None)
            if value in (None, '') and opt.default not in (None, ''):
                logging.debug('Setting default of "%s" for "%s"',
                              opt.default, opt.name)
                self.store_data(update, {opt.name: opt.default})

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
        msg, name, action, values = self.parse_callback_data(data)
        if msg == 'do':
            assert name == self.name(), (
                f'Invalid callback data {data} for cmd {self.name()}')
            main_msg = self.get_message(update)
            context.bot.edit_message_reply_markup(      # removes old
                main_msg.chat_id, main_msg.message_id)  # inline keyboard
            return self.do_action_callback(
                action, data, values, update, context)
        raise ValueError(f'Invalid {msg=} in {data=}')

    def _tg_callback_for_start(self, update, context):
        data = update.callback_query.data
        msg, name, action, values = self.parse_callback_data(data)
        assert msg == 'start' and name == self.name() and action == 'prepare', (
            f'Invalid callback data {data} for cmd {self.name()}')
        self._fill_data_from_update(update, values)
        return self.review(update, context)

    def _fill_data_from_update(self, update, values=None):
        if values:
            vdict = CallbackData.param_list_to_dict(values)
            self.store_data(update, vdict)

    def do_invoke(self, update, context, name: str, values):
        """Invoke a command directly (e.g., via callback from inline kbd).

        :param update:   The update from telegram bot.

        :param context:  The context from telegram bot.

        :param name:     String name of command to execute.

        :param values:   List of strings representing a dictionary that
                         we can parse via CallbackData.param_list_to_dict.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  This method allows you to setup a callback for an inline
                  keyboard button to invoke a command. Basically you first
                  create callback data using something like

                    create_callback_data('callback', name, 'invoke', *values)

                  and use that as callback_data for an InlineKeyboardButton.
                  Then when the user clicks the button, the CallbackQueryHandler
                  that gets setup via _setup_callback_handler_for_cmd will see
                  the callback, call generic_callback_query, and that will
                  see the 'invoke' action and call this method.
        """
        main_bot = self.get_bot_ref()
        cmd = main_bot.cmds_dict.get(name)
        if not cmd:
            raise ValueError(f'Could not invoke command {name}.')
        kwargs = dict(zip(values[::2], values[1::2]))
        cmd.store_data(update, kwargs)
        cmd.process_command(update, context)

    def do_action_callback(self, action: str, data, values, update, context):
        """Helper to process a callback from the conversation handler.

Mean to be called by _tg_callback to respond to an action from the user
clicking an inline keyboard button and triggering a callback.
        """
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

        try:
            self.respond_success(update, context)
        except Exception as problem:  # pylint: disable=broad-except
            logging.exception('Exception from respond_sucess: %s', problem)
        finally:
            self.clear_data(update)
        return ConversationHandler.END

    def respond_success(self, update, context):
        """Respond to user after we have succesfully processed a command.

        By default this will call self.respond with a simple message.
        Sometimes you may want to customize the response by overriding this
        method.
        """
        self.respond(f'Successfully finished {self.name()}', update, context)

    def cancel(self, update, context):
        """When user hits cancel on inline keyboard, cancel command.
        """
        self.respond('cancelled', update, context)
        return ConversationHandler.END

    def generic_callback_query(self, update, context):
        """Helper to serve as a generic callback query

The _setup_callback_handler_for_cmd will setup a Telegram callback
to trigger this method for callback data that starts with something like
^callback#{self.name()}#.  This makes it so that when you create
callbacks using callback_tools.CallbackData that have key='callback'
and action='invoke', they get processed correctly.

        """
        data = update.callback_query.data
        msg, name, action, values = self.parse_callback_data(data)
        assert msg == 'callback' and name == self.name()
        if action == 'invoke':
            return self.do_invoke(update, context, name, values)
        raise ValueError(
            f'Unexpected action {action} in callback data {data}')

    def _setup_callback_handler_for_cmd(self, updater):
        """Helper to setup a callback for the '^callback#' pattern.

See also generic_callback_query.
        """
        updater.dispatcher.add_handler(CallbackQueryHandler(
            self.generic_callback_query, pattern=f'^callback#{self.name()}#.*'))

    def add_to_bot(self, bot, updater):
        logging.info('Adding cmd %s to main bot %s', self.name(), bot)
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler(self.name(), self.main),
                          CallbackQueryHandler(
                              self._tg_callback_for_start,
                              pattern=f'^start#{self.name()}#.*')
            ],
            states={
                self.STATE_REVIEW: [
                    CallbackQueryHandler(
                        self._tg_callback, pattern=f'^do#{self.name()}#.*'),
                    MessageHandler(Filters.text, self.edit)],
                self.STATE_EDIT: [
                    MessageHandler(Filters.text, self.edit)],
                },
            fallbacks=[
                CommandHandler('cancel', self.cancel)])
        self._setup_callback_handler_for_cmd(updater)
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

    def __init__(self, click_cmd, name=None,
                 result_parse_mode=None):
        self.click_cmd = click_cmd
        self.result_parse_mode = result_parse_mode
        super().__init__(name=name or click_cmd.name)

    def get_help_docs(self):
        return self.click_cmd.help

    def _make_default_cmd_args(self):
        return self.click_cmd.params

    def process_command(self, update, context):
        logging.info('Processing command %s from user %s at %s UTC',
                     self.name(), self.get_message(update).chat.username,
                     datetime.datetime.utcnow())
        params = self.get_data(update)
        for opt in self.click_cmd.params:
            value = params.get(opt.name, None)
            if value is not None:
                params[opt.name] = opt.process_value(None, value)
        result = self.invoke_click_callback(params, update, context)
        logging.info('Responding with result command %s from user %s:\n%s',
                     self.name(), self.get_message(update).chat.username,
                     result)
        self.clear_data(update)
        self.send_process_command_response(result, update, context)

    def send_process_command_response(self, result: str, update, context,
                                      **kwargs):
        """Hook to respond to user after running command.

        :param result:   String result message to send to user via self.respond

        :param update:   The update from telegram bot.

        :param context:  The context from telegram bot.

        :param **kwargs: Passed to self.respond

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  This method is called with the result of running a command
                  to send that result to the user. It is mainly intended as
                  something sub-classes can override if they want to tweak
                  the response to the user.

        """
        self.respond(result, update, context,
                     parse_mode=self.result_parse_mode, **kwargs)

    def invoke_click_callback(self, params: typing.Dict[str, typing.Any],
                              update, context):
        """Invoke the click callback function to process a command.

        :param params:  Dictionary of options for the command.

        :param update:   The update from telegram bot.

        :param context:  The context from telegram bot.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:  Result of running click command.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  This method takes the params the user supplied, calls
                  self.click_cmd.callback to actually run the command, and
                  then returns the result. Sub-classes can override this
                  to invoke the command differently if desired (e.g., if
                  they want to add additional information to params).
        """
        logging.debug('Ignoring update %s and context %s', update, context)
        result = self.click_cmd.callback(**params)
        return result
