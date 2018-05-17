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
requirements, set configuration options, set up the database, and add an
initial user:

```bash
# To use a virtual environment (recommended):
python3 -m venv .venv
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Configure
cp instance/fastdl.cfg.sample instance/fastdl.cfg
vi instance/fastdl.cfg

# Set up database
export FLASK_APP=fastdl
flask db create

# Add an initial user
flask user create <your customurl> --admin
```

You can then deploy it as a wsgi app using your method of choice
(see http://flask.pocoo.org/docs/1.0/deploying/).

[fastdl]: https://developer.valvesoftware.com/wiki/Sv_downloadurl
[Flask]: https://flask.pocoo.org
