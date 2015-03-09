Gedit plugin: DBGp Debugging Client
===================================

This plugin allows you to use gedit-3 as a debugging-client using the DBGp protocol (e.g.: XDebug).

## Features

 * Using DBGp-proxies
 * Multiple profiles
 * Path mapping
 * Breakpoints
 * Inspecting and manipulating variables
 * Stepping through your code

## Licence

This plugin is licenced under the GNU General Public Licence version 3. 
If you do not know what that means, see the file 'LICENCE'.

## Minimum requirements

 * gedit-3
 * python-3
 * notify-osd (will be optional in a future release, but not yet)

This plugin is only tested in ubuntu-14.04, but others should also work (in theory).

## Download

### Clone the git-repository

Execute the following command:

```
git clone https://github.com/addiks/gedit-dbgp-plugin.git
```

### Download the zip-archive

https://github.com/addiks/gedit-dbgp-plugin/archive/master.zip

Extract the zip-archive anywhere you want.

## Installation

1. Move, copy or link the folder you downloaded to ~/.local/share/gedit/plugins/addiks-dbgp
2. Restart gedit if it is running.
3. In the menu, go to: Edit > Settings > Plugins
4. Make sure the checkbox next to "Addiks - DBGp client (XDebug)" is active.

## Configuration

First thing you should do is to set up the profiles.
  1. Open in the menu: Debugging > Manage profiles
  2. For every 'target' to debug:
    1. If the target is using a debugging-proxy, activate the checkbox "connect to DBGp" and enter the hostname (or IP) and port (usually 9001).
    2. If the target is not on your computer, click on "Configure path mapping" and set up the _absolute_ path's to map from remote (target) to local (in your workspace)
    3. (Optional) Enter the URL of the WWW-system to debug (if any).
    4. Enter the port to listen for connections (usually 9000)
    5. Define an IDE-Key for the profile. The IDE-Key must be unique among all profiles and all other IDE's using the same proxy.

## Usage

First click on the menu in: Debugging > Start listening for debugging sessions
This will open all ports from all profiles and register with all DBGp-proxies.

Also, this will add a new gutter on every open gedit-window.
(a gutter is some sidebar-thingy like the one containing the line-numbers) 
Click on the gutter where you want to add breakpoints (just above where you want to debug your code).

### HTTP over XDebug

To start the debugging-session, simple open the menu 'Debugging' and click on the "Start debugging: my-profile-name".
If everything (including the server *) is properly configured, the debug session should start right away.

(*: Make sure xdebug in apache-php is propery configured to connect either directly to gedit or to a proxy that is configured in gedit.)

If you see the session-window open and close directly afterwards, you probably have not defined any breakpoints.

When you are done debugging, click on the menu in: Debugging > Stop listening for debugging sessions


### PHP-CLI over XDebug

Execute this to start a debugging-session for a PHP-script called over CLI (command line interface):

```
php -d xdebug.remote_autostart=1 yourscript.php
```

Make sure xdebug in this cli is propery configured to connect either directly to gedit or to a proxy that is configured in gedit.

