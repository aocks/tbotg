Introduction
============

This repository provides a python library to make it easy to create
telegram bots using the python telegram API.

The basic idea is that you can define a function similar to the way you
would with the `click framework <https://click.palletsprojects.com>`__
and then automatically convert that into a form suitable for telegram.

Ideally, creating commands in a telegram bot should but just as easy as
writing a python function.

Getting Started
===============

The following describes how to get started as quickly as possible.

Install via pip
---------------

Do the usual ``pip install tbotg``.

Use BotFather to create a bot
-----------------------------

First, use the botfather to create a bot:

#. Go to ``BotFather`` in a Telegram chat.
#. Type ``/newbot`` to request a new bot.
#. Type the desired name when ``BotFather`` asks you for it.
#. Save the token ``BotFather`` gives you in ``~/.ox_secrets.csv`` as

.. code:: example

    name,category,values,notes
    token,YOUR_BOT_NAME,YOUR_TOKEN

-  The ``~/.ox_secrets.csv`` file is a simple CSV file used to manage
   secret information such as your telegram bot token.

Create a python file for your command
-------------------------------------

Next, create a python file for your bot. For example, you could create a
python file named ``mybot.py`` as shown below:

.. code:: python

    "Example to show how to use tbotg"

    import click

    from tbotg.core.main_bot import TelegramMainBot
    from tbotg.core.bcmds import ClickCmd


    @click.command()
    @click.option('--say', help='What to say')
    @click.option('--count', type=int, help='How many times to repeat.')
    def repeatntimes(say, count):
        "Repeat something N times."
        return 'I will repeat it %i times: %s' % (
            count, ', '.join([say.upper()] * count))


    class MyBot(TelegramMainBot):
        """Example bot.
        """

        @classmethod
        def make_cmds(cls):
            "Make commands for bot."

            return [ClickCmd(repeatntimes)]

Start the server
----------------

Run the serve using the ``tcli`` script provided by ``tbotg`` via the
following command line:

.. code:: bash

    tcli serve --bot_cls MyBot --module 'mybot' --with_name ${YOUR_BOT_NAME}

where ``${YOUR_BOT_NAME}`` is the name of the bot you created with
``BotFather``

Note that you will need your ``PYTHONPATH`` set properly for python to
find your ``mybot.py`` module. For example, you could do something like

::

    export PYTHONPATH=${PYTHONPATH}:`dirname /path/to/mybot.py`

Test the command on telegram
----------------------------

To test your command,

#. Start a chat with your bot on telegram.
#. Do ``/help`` to see available commands.
#. Do ``/repeatntimes`` to run your command
#. Click on the parameter buttons to set the values of ``say`` and
   ``count``.
#. Click the ``confirm`` button to run the command.
