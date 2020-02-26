# Captiveportal
# This is the web API the portal website speaks to and requests new clients
# to be added by running jobs in rq.

import json
from pprint import pprint as pp
from uuid import UUID
from importlib import import_module
from logging import Formatter, getLogger, DEBUG, INFO, WARN
from logging.handlers import SysLogHandler, RotatingFileHandler

# Until pyvenv-3.4 is fixed on centos 7 support python 2.
try:
    from configparser import RawConfigParser
except ImportError:
    from ConfigParser import RawConfigParser

from redis import Redis
from rq import Queue
from bottle import Bottle, default_app, debug
from bottle import request, response, template, static_file

config = RawConfigParser()
config.readfp(open('./portal.cfg'))
config.read(['/etc/captiveportal/portal.cfg', './portal_local.cfg'])

# Plugins configuration is separate so plugins can be disabled by having
# their section removed/commented from the config file.
plugin_defaults = {
    'enabled': 'False',
    'mandatory': 'True',
    'debug': 'False'
}
plugin_config = RawConfigParser(defaults=plugin_defaults)
plugin_config.readfp(open('./plugins.cfg'))
plugin_config.read(['/etc/captiveportal/plugins.cfg', './plugins_local.cfg'])

# Setup logging
logFormatter = Formatter(config.get('logging', 'log_format'))
l = getLogger('captiveportal')
if config.get('logging', 'log_handler') == 'syslog':
    syslog_address = config.get('logging', 'syslog_address')

    if syslog_address.startswith('/'):
        logHandler = SysLogHandler(
            address=syslog_address,
            facility=SysLogHandler.LOG_LOCAL0
        )
    else:
        logHandler = SysLogHandler(
            address=(
                config.get('logging', 'syslog_address'),
                config.getint('logging', 'syslog_port')
            ),
            facility=SysLogHandler.LOG_LOCAL0
        )
else:
    logHandler = RotatingFileHandler(
        config.get('logging', 'log_file'),
        maxBytes=config.getint('logging', 'log_max_bytes'),
        backupCount=config.getint('logging', 'log_max_copies')
    )
logHandler.setFormatter(logFormatter)
l.addHandler(logHandler)

if config.get('logging', 'log_debug'):
    l.setLevel(DEBUG)
else:
    l.setLevel(WARN)

# Redis Queue
R = Redis(
    host=config.get('portal', 'redis_host'),
    port=config.getint('portal', 'redis_port')
)


# Custom UUID route filter for bottle.py
def uuid_filter(config):
    # Should catch UUIDv4 type strings
    regexp = r'[a-f0-9]{8}-?[a-f0-9]{4}-?4[a-f0-9]{3}-?[89ab][a-f0-9]{3}-?[a-f0-9]{12}'

    def to_python(match):
        return UUID(match, version=4)

    def to_url(uuid):
        return str(uuid)

    return regexp, to_python, to_url


# Add plugins to job queue
def dispatch_plugins():
    Q = Queue(connection=R)
    jobs = {}

    for plugin in plugin_config.sections():
        l.debug('Loading plugin {plugin}'.format(
            plugin=plugin
        ))

        arg = {}

        # Import some values from WSGI environ
        arg['environ'] = {}
        for key in request.environ:
            value = request.environ.get(key)
            if isinstance(value, (int, str, float, dict, set, tuple)):
                arg['environ'][key] = value

        # Import all the plugin configuration values as OrderedDict
        config_sections = plugin_config._sections
        arg['config'] = config_sections[plugin]

        # Is plugin enabled?
        if not plugin_config.getboolean(plugin, 'enabled'):
            l.debug('{plugin}: Not enabled, skipping'.format(
                plugin=plugin
            ))
            continue

        # Import the plugin
        try:
            plugin_module = import_module('plugins.'+plugin)
        except Exception as e:
            l.warn('{plugin}: failed import: {error}'.format(
                plugin=plugin,
                error=str(e)
            ))
            continue

        # Let plugin run for 30 more seconds than the defined plugin_timeout
        # because that value is also used by the JS code to poll the job
        # status so we don't want rq to kill the job before JS has timed out.
        plugin_timeout = config.getint('portal', 'plugin_timeout')+30

        # Queue plugin.run()
        try:
            plugin_job = Q.enqueue(
                plugin_module.run,
                arg,
                timeout=plugin_timeout
            )
        except Exception as e:
            l.warn('{plugin}: {error}'.format(
                error=str(e),
                plugin=plugin
            ))
            continue

        plugin_meta = {}
        plugin_meta['mandatory'] = plugin_config.getboolean(
            plugin,
            'mandatory'
        )
        plugin_job.meta = plugin_meta
        plugin_job.save()

        jobs[plugin] = {
            'id': plugin_job.id
        }

    return jobs


# Define app so we can add a custom filter to app.router
app = Bottle()
app.router.add_filter('uuid', uuid_filter)


@app.route('/')
def portalindex():
    return template(
        config.get('portal', 'index_page'),
        plugin_timeout=config.getint('portal', 'plugin_timeout')
    )


@app.route('/static/<path:path>')
def server_static(path):
    return static_file(path, root=config.get('portal', 'static_dir'))


@app.route('/jobs')
def list_jobs():
    Q = Queue(connection=R)
    jobs = Q.get_job_ids()
    response.content_tye = 'application/json'
    return json.dumps(jobs)


@app.route('/job/<job_id:uuid>')
def job_status(job_id):
    Q = Queue(connection=R)
    job = Q.fetch_job(str(job_id))
    response.content_type = 'application/json'
    if job is None:
        response.status = 404
        return json.dumps({'error': 'Job not found'})

    # Get data on the job to return to the client
    job_data = {
        'id': job.id,
        'is_failed': job.is_failed,
        'is_finished': job.is_finished,
        'is_queued': job.is_queued,
        'is_started': job.is_started,
        'result': job.result,
        'meta': job.meta
    }


    return json.dumps(job_data)


@app.route('/approve', method='POST')
def approve_client():
    response.content_type = 'application/json'
    try:
        jobs = dispatch_plugins()
    except Exception as e:
        response.status = 500
        jobs = {
            'result': {
                'error': str(e)
            }
        }

    return json.dumps(jobs)


if __name__ == '__main__':
    app.run(
        host=config.get('portal', 'listen_host'),
        port=config.getint('portal', 'listen_port')
    )
    debug(config.getboolean('portal', 'debug'))
else:
    application = app
