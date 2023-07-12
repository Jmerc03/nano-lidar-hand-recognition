import logging
import threading
import time

class ThreadHandler:
    i = 12345

    def __init__(self):
        print("Hello world!")

    def f(self):
        return 'hello world'

    def thread_function(name):
        logging.info("Thread %s: starting", name)
        time.sleep(2)
        logging.info("Thread %s: finishing", name)

    