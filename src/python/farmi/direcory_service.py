import time
from datetime import datetime

import zmq


def start_directory_service():
    context = zmq.Context()
    available_topics = {}

    # Socket to talk to clients
    publisher = context.socket(zmq.PUB)
    # set SNDHWM, so we don't drop messages for slow subscribers
    # publisher.sndhwm = 1100000
    publisher.bind('tcp://*:5561')

    # Socket to receive signals
    syncservice = context.socket(zmq.REP)
    syncservice.bind('tcp://*:5562')

    syncservice2 = context.socket(zmq.REP)
    syncservice2.bind('tcp://*:5563')

    poller = zmq.Poller()
    poller.register(syncservice, zmq.POLLIN)
    poller.register(syncservice2, zmq.POLLIN)

    while True:
        socks = dict(poller.poll())
        if syncservice in socks:
            topic = syncservice.recv_json()
            syncservice.send_string(str(time.time()))
            available_topics[topic['name']] = topic['address']
            print(available_topics)
            publisher.send_json(available_topics)
        if syncservice2 in socks:
            syncservice2.recv()
            syncservice2.send_string(str(time.time()))
            publisher.send_json(available_topics)

if __name__ == '__main__':
    start_directory_service()