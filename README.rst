=======
Vbet
=======

Vbet is a lightweight server that provides an online betting bot targeting virtual games
on various providers.It offers unlimited uptime with upto 24hours live play.It is highly customizable and different
algorithms and patterns are easily configured.

*NOTE*:
    *The documentation is work in progress and will be available in the coming weeks*.


Getting Started
---------------

Before getting started, make sure you have an existing account with one of our supported providers.

Supported providers:
    - Betika
    - Mozart

Install
=======


Clone the repository with the default being the
stable release `Link <https://github.com/updatedennismwangi/vbet.git>`_.

Instructions on how to clone can be
found `How to clone <https://docs.github.com/en/github/creating-cloning-and-archiving-repositories/cloning-a-repository>`_.


Starting the server
===================

To start the server navigate to the *bin* directory and execute the **run** script. It supports
multiple arguments which can be shown using the  **--help** or **-h** flags.

    ``run -a betika -p 9000 -vv``

Above, the **-a** flag specifies an api name from the list of providers. Refer to Providers above.
The **-p** flag is used to specify the port where the websocket server listens.The **-vv** flag specifies the highest level of verbosity.

    *Note*
        Choose a port above 1000 to prevent root privilege issues Default 9000.

        By default the server binds to the localhost.

Vshell
======
The main controller to the server is the **vshell** located in the *bin* directory.To get an
instance of the shell run :

    ``vs --port 9000``

The shell is interactive and takes in a *uri* which is a command and arguments if any and executes them asynchronously.
The shell is always running only if the server instance is running. If the server goes offline
then the shell immediately terminates.Any commands that are sent to the websocket server and have
any response output are flushed to the shell ounce the response is available.The payload being sent is also
displayed on the shell on each command if it involves a server call. e.g *add*, *login*

The shell supports multiple commands which are accessible using the **help** command:

    ``help``

Live Users
==========

*Login*

To get started with adding live users to the system involves using the **login** command.
It requires two arguments, *username* and *password*.

    ``login 0712345678 1234``

The above command will trigger a login call to the api name backend and request for an access
token that is stored for a specified duration of time per api backend. The access tokens are
stored in redis and are persistent across restarts. Ounce the user is cached
on the server then the **add** command is used to add a user to a live session.

    *Note*
            You cannot add a user unless the user is already cached. Always run the login comand
            ounce for every new user.

*Add*

It requires two arguments, *username*, *demo*. The *demo* argument uses the integer
1 for **live account** and 0 for **demo account**

    + live account

        ``add 0712345678 1``

    + demo account

        ``add 0712345678 0``

Shutdown
========
* Using the shell :
    To gracefully shutdown the server and exit all sessions use the **exit** command.

        ``exit``
* While running :
    Pressing *Ctrl + C* on the Keyboard performs a *warm shutdown*. A second press will cause a cold
    shutdown.


Advanced
--------
The default settings file is the *vbet.core.settings*.

The shell runs by default on localhost and can be specified in shell connection options using **--host**.

These directories are created automatically in the running directory
    cache
         Contains directory per Competition used to cache virtual events.
    data
         Stores file per user configuration data for game play.
    logs
         Default log directory. Default log file *vbet.log*

Different providers have different expiry durations for the access tokens. Make sure not to perform an *add* operation using an expired token.

    *Note*
        - Future versions will correctly invalidate access tokens using validated expiry durations.
