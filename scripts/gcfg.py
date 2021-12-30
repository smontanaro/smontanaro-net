#!/usr/bin/env python

"Gunicorn config file"

import gunicorn.glogging

# pylint: disable=invalid-name

# Config File

config                            = "./gcfg.py"
wsgi_app                          = None

# Logging

# pylint: disable=line-too-long
access_log_format                 = '''%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'''
accesslog                         = None
capture_output                    = False
disable_redirect_access_to_syslog = False
dogstatsd_tags                    = ""
enable_stdio_inheritance          = False
errorlog                          = "-"
logconfig_dict                    = {}
logconfig                         = None
logger_class                      = gunicorn.glogging.Logger
loglevel                          = "info"
statsd_host                       = None
statsd_prefix                     = ""
syslog_addr                       = "udp://localhost:514"
syslog_facility                   = "user"
syslog                            = False
syslog_prefix                     = None

# Process Naming

default_proc_name                 = "hello"
proc_name                         = None

# Debugging

check_config                      = False
print_config                      = True
reload_engine                     = "auto"
reload_extra_files                = []
reload                            = False
spew                              = False

# SSL
ca_certs                          = None
certfile                          = None
cert_reqs                         = 0
ciphers                           = None
do_handshake_on_connect           = False
keyfile                           = None
ssl_version                       = "TLS"
suppress_ragged_eofs              = True

# Security

limit_request_fields              = 100
limit_request_field_size          = 8190
limit_request_line                = 4094

# Server Hooks

# child_exit                        = <ChildExit.child_exit()>
# nworkers_changed                  = <NumWorkersChanged.nworkers_changed()>
# on_exit                           = <OnExit.on_exit()>
# on_reload                         = <OnReload.on_reload()>
# on_starting                       = <OnStarting.on_starting()>
# post_fork                         = <Postfork.post_fork()>
# post_request                      = <PostRequest.post_request()>
# post_worker_init                  = <PostWorkerInit.post_worker_init()>
# pre_exec                          = <PreExec.pre_exec()>
# pre_fork                          = <Prefork.pre_fork()>
# pre_request                       = <PreRequest.pre_request()>
# when_ready                        = <WhenReady.when_ready()>
# worker_abort                      = <WorkerAbort.worker_abort()>
# worker_exit                       = <WorkerExit.worker_exit()>
# worker_int                        = <WorkerInt.worker_int()>

# Server Mechanics

chdir                             = "/home/skip/website"
daemon                            = False
group                             = 1002
initgroups                        = False
pidfile                           = None
preload_app                       = False
raw_env                           = []
reuse_port                        = False
forwarded_allow_ips               = ['127.0.0.1']
paste                             = None
proxy_allow_ips                   = ['127.0.0.1']
proxy_protocol                    = False
pythonpath                        = None
raw_paste_global_conf             = []
secure_scheme_headers             = {
    'X-FORWARDED-PROTOCOL': 'ssl',
    'X-FORWARDED-PROTO': 'https',
    'X-FORWARDED-SSL': 'on',
}
sendfile                          = None
strip_header_spaces               = False
tmp_upload_dir                    = None
umask                             = 0
user                              = 1002
worker_tmp_dir                    = None

# Server Socket

backlog                           = 2048
bind                              = [
    '0.0.0.0:8000',
#    '0.0.0.0:443',       # eventually
]

# Worker Processes

graceful_timeout                  = 30
keepalive                         = 2
max_requests                      = 0
max_requests_jitter               = 0
threads                           = 1
timeout                           = 30
worker_class                      = "sync"
worker_connections                = 1000
workers                           = 1
