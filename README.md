# Fastdl

This is a web app that acts as a [fastdl] with basic access
control for source engine games. Users can upload maps and add server
addresses to a whitelist, which is then used to determine which clients are
allowed to download maps.

## How it works

All unmodified source clients set Referer to `hl2://address:port`, which
allows fastdl to check the address against a known whitelist of servers and
prevent access if necessary to save bandwidth. While this is not much of a
form of authentication, it does prevent unauthorized servers from mooching off
of your bandwidth just by setting `sv_downloadurl`.

## Setup

fastdl is written in Python 3 using [Flask]. To use it, install the
requirements:

    pip install -r requirements.txt

Then, copy `instance/fastdl.cfg.sample` to `instance/fastdl.cfg` and edit it
as necessary. You can then deploy it as a wsgi app using your method of choice
(see http://flask.pocoo.org/docs/1.0/deploying/)

[fastdl]: https://developer.valvesoftware.com/wiki/Sv_downloadurl
[Flask]: https://flask.pocoo.org
