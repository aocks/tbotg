"""Tools used in telegram bot callbacks.
"""

import threading
import logging
import typing


class DataHashManager:
    """Intern string data into a hash table.

This class allows you to store a string and remember it via an integer ID.
This is helpful if you have callback data strings which are long that
you use a lot. You can save those strings into the DataHashManager and
get back a small integer id that can later be used to lookup the data.

The following illustrates example usage:

>>> from tbotg.core import callback_tools
>>> data = 'my_really_long_data_string_to_save_more_efficiently'
>>> hid = callback_tools.DataHashManager.data_to_hid(data)   # save and get ID
>>> float(len(str(hid))) / float(len(data)) < 0.10  # which takes less space
True
>>> data == callback_tools.DataHashManager.hid_to_data(hid)
True
    """

    _hid_lock = threading.Lock()
    _hid_counter = 0
    _to_hid = {}
    _from_hid = {}

    @classmethod
    def data_to_hid(cls, data: str) -> int:
        """Convert string data into an integer ID.

Use hid_to_data to convert result back into data.
        """
        with cls._hid_lock:
            hid = cls._to_hid.get(data)
            if hid is None:
                cls._hid_counter += 1
                hid = cls._hid_counter
                cls._to_hid[data] = hid
                cls._from_hid[hid] = data
            return hid

    @classmethod
    def hid_to_data(cls, hid: int) -> typing.Optional[str]:
        """Convert hid returned by data_to_hid into original string data.
        """
        with cls._hid_lock:
            return cls._from_hid.get(hid)


class CallbackData:
    """Efficient representation of Telegram callback data.

PURPOSE: The telegram API allows arbitrary callback data for inline
         keyboard buttons. This is *VERY* useful but because there is
         a limit of only 64 bytes, we use CallbackData(...).to_string()
         to encode callback data and CallbackData.from_string(...) to
         decode the callback data.

         These method encode/ecode the key, cmd, and action along with
         the key value pairs in a consistent, efficient way which can
         be decoded by parse_callback_data. See also the docs for
         DataHashManager for our own string interning method.
    """

    def __init__(self, key: str, cmd: str, action: str, *values, **kwargs):
        """Create string callback data for telegram bot in canonical way.

        :param ke:  String key for the type of callback we are doing. Some
                    examples which are used include:

           - callback:  Generic callback indicator.
           - start:  Start a command triggered by a keyboard button.
           - do:  Do a step in the conversation handler.

        :param cmd:  String name of callback command to execute.

        :param action:  String action for callback (e.g., 'invoke').

        :param *values:  List of additional string data.

        :param **kwargs:  Key value parameters for callback.
        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        """
        assert key in ('do', 'start', 'callback')
        self.validate_action(action)
        assert cmd, 'Must provide something for cmd in create_callback_data.'
        self.key = key
        self.action = action
        self.cmd = cmd
        self.values = list(values) + list(sum(kwargs.items(), ()))

    @classmethod
    def validate_action(cls, action: str):
        """Verify the action looks right or raise a ValueError.
        """
        if action not in ('prepare', 'invoke', 'confirm', 'edit', 'helparg',
                          'cancel', 'confirm', 'help'):
            raise ValueError(f'Unexpected {action=} for {cls.__name__}')

    def to_string(self) -> str:
        """Convert self into a string representation.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:  An encoded string for the callback. Since the telegram
                  API requires this to be less than 64 bytes, we use the
                  DataHashManager to intern some strings to reduce space.
        """
        result = [self.key, self.cmd, self.action]
        for value in self.values:
            if isinstance(value, str):
                if len(value) < 5:
                    pass
                else:
                    value = f'/{DataHashManager.data_to_hid(value)}'
            elif isinstance(value, int):
                value = str(value)
            else:
                raise TypeError(
                    f'Bad type {type(value)} for callback data {value}')
            result.append(value)
        result = '#'.join(result)
        if len(result) > 64:
            logging.error(
                'callback data %s too long; see %s', result, ''.join([
                    'https://docs.python-telegram-bot.org',
                    '/en/stable/telegram.inlinekeyboardbutton.html']))
        return result

    @classmethod
    def from_string(cls, callback_data: str):
        """Convert str representing callback data into CallbackData instance.

        :param callback_data:   String produced by CallbackData.to_string.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:  Instance of CallbackData class.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  This decodes the CallbackData instance that was encoded
                  into a string using to_string.

        """
        msg, name, action, values = cls.info_tuple_from_string(callback_data)
        return cls(msg, name, action, *values)

    @staticmethod
    def info_tuple_from_string(callback_data: str):
        """Helper method to turn callback_data into parsed tuple of data.

Meant to be used by from_string and generally should not be called directly.
        """
        msg, name, action, *orig_values = callback_data.split('#')
        values = []
        for item in orig_values:
            if item and item[0] == '/':
                try:
                    hid = int(item[1:])
                    item = DataHashManager.hid_to_data(hid)
                except ValueError:
                    logging.warning('Unable to parse %s as hid', item)
            values.append(item)
        return msg, name, action, values

    @staticmethod
    def param_list_to_dict(param_list: typing.List[str]) -> typing.Dict[
            str, str]:
        """Convert list of key/value parameters into a dict.

The following illustrates example usage:

>>> from tbotg.core import callback_tools
>>> callback_tools.CallbackData.param_list_to_dict(['one', '1', 'two', '2'])
{'one': '1', 'two': '2'}

        """
        if not param_list:
            return {}
        vdict = {param_list[i]: param_list[i+1] for i in range(
            0, len(param_list), 2)}
        return vdict

    def __str__(self):
        """Convert to a string; see docs for to_string method.
        """
        return self.to_string()
