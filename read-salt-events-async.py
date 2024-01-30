#!/usr/bin/python3

import json
import os
import threading
import time
import signal
import sys

import salt.config

from salt.ext.tornado.ioloop import IOLoop, PeriodicCallback
from salt.utils.event import get_event


class AsyncEventReader:
    def __init__(self, opts):
        self.mopts = opts
        self._queue = []
        self.event_bus = None
        self._last_reconnect = 0
        self._exit = False

    def _init_event_bus(self):
        if self.event_bus is not None:
            self.event_bus.destroy()
        self.event_bus = get_event(
            "master",
            listen=True,
            io_loop=self.io_loop,
            opts=self.mopts,
            raise_errors=False,
            keep_loop=True,
        )
        self.event_bus.set_event_handler(self.enqueue_event)

    @salt.ext.tornado.gen.coroutine
    def enqueue_event(self, raw):
        try:
            self._queue.append(self.event_bus.unpack(raw))
        except:
            # Here we can handle mostly the exception on unpacking the data
            # In case of loosing the connection self.check_connected_cb
            # PeriodicCallback is used as here we can not receive
            # an exception anyway
            pass

    @salt.ext.tornado.gen.coroutine
    def check_events_connected(self):
        if self._exit:
            return
        if (
            not self.event_bus.subscriber.connected()
            and self._last_reconnect + 10 < time.time()
        ):
            self._last_reconnect = time.time()
            self._init_event_bus()

    def print_salt_events(self):
        while True:
            if self._exit:
                return
            while self._queue:
                tag, data = self._queue.pop(0)
                if tag is None or data is None:
                    continue
                print(f"{tag}\t{json.dumps(data)}")
            time.sleep(0.5)

    def run(self):
        self.print_thread = threading.Thread(target=self.print_salt_events)
        self.print_thread.start()
        self.io_loop = IOLoop(make_current=True)
        self._init_event_bus()
        self.check_connected_cb = PeriodicCallback(
            self.check_events_connected, 1000, io_loop=self.io_loop
        )
        self.check_connected_cb.start()
        self.io_loop.start()

    def stop(self):
        self._exit = True
        self.event_bus.destroy()
        self.io_loop.stop()
        self.print_thread.join()


client_conf_path = os.path.join(salt.syspaths.CONFIG_DIR, "master")

client_opts = salt.config.client_config(client_conf_path)

event_reader = AsyncEventReader(client_opts)

try:
    event_reader.run()
except KeyboardInterrupt:
    event_reader.stop()
    pass
