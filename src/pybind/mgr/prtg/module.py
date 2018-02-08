"""
A Health publisher for PRTG.
"""

import os
import json
import time
import errno
import inspect
import tempfile
import threading
import traceback
import socket

from uuid import uuid4
from pecan import jsonify, make_app
from OpenSSL import crypto
from pecan.rest import RestController
from werkzeug.serving import make_server, make_ssl_devcert

from hooks import ErrorHook
from mgr_module import MgrModule, CommandResult

# Global instance to share
instance = None


class CannotServe(Exception):
    pass


class Module(MgrModule):

    def __init__(self, *args, **kwargs):
        super(Module, self).__init__(*args, **kwargs)
        global instance
        self.log.info("FTW {}".format(instance))
        instance = self

        self.requests = []
        self.requests_lock = threading.RLock()

        self.keys = {}
        self.disable_auth = False

        self.server = None

        self.stop_server = False
        self.serve_event = threading.Event()


    def serve(self):
        self.log.info("Start serve method")
        while not self.stop_server:
            try:
                self._serve()
                self.server.socket.close()
            except CannotServe as cs:
                self.log.warn("server not running: {0}".format(cs.message))
            except:
                self.log.error(str(traceback.format_exc()))

            # Wait and clear the threading event
            self.serve_event.wait()
            self.serve_event.clear()

    def _serve(self):
        # Load stored authentication keys

        jsonify._instance = jsonify.GenericJSON(
            sort_keys=True,
            indent=4,
            separators=(',', ': '),
        )

        server_addr = self.get_localized_config('server_addr', '::')
        if server_addr is None:
            raise CannotServe('no server_addr configured; try "ceph config-key set mgr/prtg/server_addr <ip>"')

        server_port = int(self.get_localized_config('server_port', '8004'))
        self.log.info('server_addr: %s server_port: %d',
                      server_addr, server_port)

        # Publish the URI that others may use to access the service we're
        # about to start serving
        self.set_uri("http://{0}:{1}/".format(
            socket.gethostname() if server_addr == "::" else server_addr,
            server_port
        ))

        # Create the HTTPS werkzeug server serving pecan app
        self.server = make_server(
            host=server_addr,
            port=server_port,
            app=make_app(
                root='prtg.api.Root',
                hooks = [ErrorHook()],  # use a callable if pecan >= 0.3.2
            ),
        )

        self.server.serve_forever()


    def shutdown(self):
        self.log.warn("Shutting down server")
        try:
            self.stop_server = True
            if self.server:
                self.server.shutdown()
            self.serve_event.set()
        except:
            self.log.error(str(traceback.format_exc()))
            raise


    def restart(self):
        try:
            if self.server:
                self.server.shutdown()
            self.serve_event.set()
        except:
            self.log.error(str(traceback.format_exc()))


    def notify(self, notify_type, tag):
        try:
            self._notify(notify_type, tag)
        except:
            self.log.error(str(traceback.format_exc()))


    def _notify(self, notify_type, tag):
        self.log.debug("Unhandled notification type '%s'" % notify_type)
