#!/usr/bin/python3

import json
import os
import threading
import time
import signal

import salt.config
import salt.utils.event


class ExitCommand(Exception):
    pass


def signal_handler(signal, frame):
    raise ExitCommand()


def print_salt_events(queue):
    while True:
        while queue:
            event = queue.pop(0)
            tag = event.pop("tag", None)
            if tag == "salt/event/exit":
                os.kill(os.getpid(), signal.SIGUSR1)
                return
            data = event.pop("data", None)
            if tag is None or data is None:
                continue
            print(f"{tag}\t{json.dumps(data)}")
        time.sleep(0.5)


def read_salt_events(queue):
    with salt.utils.event.get_event(
        "master",
        sock_dir=client_opts["sock_dir"],
        opts=client_opts,
        raise_errors=True,
    ) as salt_events:
        while True:
            try:
                event = salt_events.get_event(full=True, auto_reconnect=True)
            except TypeError:
                # Most probably cosmetic issue on handling the signal
                event = None

            if event is None:
                continue

            queue.append(event)


client_conf_path = os.path.join(salt.syspaths.CONFIG_DIR, "master")

client_opts = salt.config.client_config(client_conf_path)

queue = []

signal.signal(signal.SIGUSR1, signal_handler)

print_thread = threading.Thread(target=print_salt_events, args=(queue,))
print_thread.start()

try:
    read_salt_events(queue)
except ExitCommand:
    pass
finally:
    print_thread.join()
