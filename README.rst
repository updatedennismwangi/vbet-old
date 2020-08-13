****
Vbet
****

Vbet is a lightweight server that provides an online betting bot targeting virtual games
on various betting providers globally.

*Note*
    * Always make sure to run the latest version of our server as new players and quick patches are released very often.

=======
Install
=======
Install latest stable version :

* using pip

    ``pip install vbet``


* github clone

    Clone the repository with the default being the
    stable release `Link <https://github.com/updatedennismwangi/vbet.git>`_.

    Instructions on how to clone can be
    found `How to clone <https://docs.github.com/en/github/creating-cloning-and-archiving-repositories/cloning-a-repository>`_.

Starting the server
-------------------

* Git clone
    Navigate to the *bin* directory and execute the **vrun** script.

    It supports multiple arguments which can be shown using the  **--help** or **-h** flags.

        ``./vrun -a betika -p 9000 -vv``

* Pip
    *Installation via pip will add **vrun** to your path*.

        ``vrun -a betika -p 9000 -vv``

Above, the **-a** flag specifies an api name from the list of providers. Refer to Providers below.
The **-p** flag is used to specify the port where the websocket server listens.The **-vv** flag specifies the highest level of verbosity.

    *Note:*
        Choose a port above 1000 to prevent root privilege issues Default 9000.

        By default the server binds to the localhost.


Vshell
------
The vshell provides the interface to our server. We can use it to perform critical calls to the server.
The shell connects to the server using websockets to the websocket server.

To get started with the shell:


* Git clone
    Navigate to the *bin* directory and run:

        ``./vshell --port 9000``

* Pip
    * Installation via pip will add **vshell** to your path*.

        `vshell --port 9000`

The shell supports multiple commands which are accessible using the **help** command:

    ``help``

The shell is interactive and takes in a *uri* which is a command and arguments if any and executes them asynchronously.
The shell is always running only if the server instance is running. If the server goes offline
then the shell immediately terminates.

Any commands that are sent to the websocket server and have
any response output are flushed to the shell ounce the response is available.The payload being sent is also
displayed on the shell on each command if it involves a server call. e.g *add*, *login*

===============
Getting Started
===============

Before getting started, make sure you have an existing account with one of our supported providers.

Supported providers:
    - Betika
    - Mozart

Open two terminals.

    On the first on make sure the server is up and running:

        ``vrun -a betika -vv``

    On the second to add users and interact with our server we launch the vshell using:

        ``vshell``


Live Users
----------

* Login

    To get started with adding live users to the system involves using the **login** command.
    It requires two arguments, *username* and *password*.

        ``login 0712345678 1234``

    The above command will trigger a login call to the api name backend and request for an access
    token that is stored for a specified duration of time per api backend. The access tokens are
    stored in redis and are persistent across restarts. Ounce the user is cached
    on the server then the **add** command is used to add a user to a live session.

    Different providers have different expiry durations for the access tokens. Make sure not
    to perform an *add* operation using an expired token.

    *Note:*
         1. You cannot add a user unless the user is already cached. Always run the login command ounce for every new
            user.
         2. Future versions will correctly invalidate access tokens using validated expiry durations


* Add

    It requires two arguments, *username*, *demo*. The *demo* argument uses the integer
    1 for **live account** and 0 for **demo account**

        + live account

            ``add 0712345678 1``

        + demo account

            ``add 0712345678 0``

Shutdown
--------
* Using the shell :
    To gracefully shutdown the server and exit all sessions use the **exit** command.

        ``exit``

* While running :
    Pressing *Ctrl + C* on the Keyboard performs a *warm shutdown*. A second press will cause a cold
    shutdown.

========
Advanced
========
The default settings file is the *vbet.core.settings*. It can be used to configure major
changes like log directory, live games and default api name.


These directories are created automatically in the running directory:
    + *cache* - contains directory per competition used to cache virtual events.
    + *data* - stores file per user configuration data for game play.
    + *logs* - default log directory. Default log file *vbet.log*

Competition
-----------
A **competition** features a single football league that can be simulated. Every provider has
a list of supported competitions on their website. We support all **On Demand** virtual football
games.

    *Supported competitions*:
        - EPL Premier - 14045
        - Spain Laliga  - 14036
        - Italy Calcio  - 14035
        - Germany Bundesliga - 41047
        - Kenya KPL - 14050

By default all supported competitions are started which can be changed in the **add** command by
providing a space separated list of code values for each competition.

    ``add 0712345678 0 14036 14045``

Players
-------

For the dedicated users. We provide a way to select the current active **player**.
A player is an algorithm that produces tickets and there is a number of preinstalled
players. They are named using symbolic football player names.

You can enable a new player by tweaking **line: 100** of **vbet.game.competition** and provide a list of
optional players you would like to enable. Note that each player will be installed for each competition.
Multiple players can also play at the same time.

More information will be available later on the details of each player.

More detailed information will be available in the coming weeks to guide on creating custom players.

    *Installed Players:*
        - dybala - *recommended*
        - ozil  - *recommended*
        - fati
        - ronaldo
        - xavi
        - puig
        - salah
        - rooney
        - messi
        - neymar
        - hazard
        - mbape

Default installed player is **ozil**.

Account Managers
----------------

The main account manager controls the user account balance.It ensures the balance is upto date
when using live mode and takes care of simulating tickets in demo mode.It also synchronizes all
account managers in all players in every competition.

Every player has an account manager. The manager acts as a money
management scheme to regulate the algorithm.

    *Account managers:*
        - FixedStakeAccount - *recommended*
        - FixedProfitAccount - *recommended*
        - RecoverAccount - **high risk**
        - TokenAccount
        - RecoverShareAccount

**Note:**
    The default stake for demo account  is **Ksh 100,000**.


More information will be available later on the details of each account manager.
