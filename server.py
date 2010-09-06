import logging
import os.path
import re
import tornado.escape
import tornado.httpclient
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
import util
import xml.etree.ElementTree as ET
import urllib
import time
import optparse
import signal
import sys
import threading
import calculatedistance
from django.forms.models import model_to_dict

os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
from models import Line
from models import Coordinate
from models import Station

__author__  = "http://popdevelop.com, Johan Brissmyr, Johan Gyllenspetz, Joel Larsson, Sebastian Wallin"
__email__   = "use twitter @popdevelop"
__date__    = "2010-09-04"
__appname__ = 'kollektivt.se'
__version__ = '0.1'

from tornado.options import define, options
define("port", default=8888, help="Run on the given port", type=int)

vehicle_coords = []
shd = False
vehicle_semaphore = threading.Semaphore()


class VehiclesFetcher(threading.Thread):
   def __init__ (self, line):
       threading.Thread.__init__(self)
       self.line = line
   def run(self):
       calculatedistance.get_vehicles(self.line, True)


class StationFetcher(threading.Thread):
    def run(self):
        global vehicle_coords
        global vehicle_semapore
        logging.info("%s: StationFetcher.start", __appname__)
        while not shd:
            thread_list = []
            for line in Line.objects.all():
                current = VehiclesFetcher(line)
                thread_list.append(current)
                current.start()

            for t in thread_list:
                t.join()

            logging.info("Finished fetching fresh departure and deviation times")
            time.sleep(120)


class vehicle(threading.Thread):
    def run (self):
         global vehicle_coords
         global vehicle_semapore
         logging.info("%s: VehicleThread - start", __appname__)
         nexttime = 0
         while not shd:
             new_vehicle_coords = []
             for l in Line.objects.all():
                 vehicles = calculatedistance.get_vehicles(l, False)
                 new_vehicle_coords.extend(vehicles)

             vehicle_semaphore.acquire()
             vehicle_coords = new_vehicle_coords
             vehicle_semaphore.release()
             time.sleep(0.2)

class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", MainHandler),
            (r"/lines", LineHandler),
            (r"/vehicles", VehicleHandler),
            (r"/stations", StationHandler),
            (r"/lines/([^/]+)", NiceLineHandler),
            (r"/lines/([^/]+)/([^/]+)", NiceVehicleHandler)
        ]
        settings = dict(
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
        )
        tornado.web.Application.__init__(self, handlers, **settings)


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html")


class APIHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    def get(self):
        logging.info("APIHandler - build_command()")
        self.args = dict(zip(self.request.arguments.keys(),
                             map(lambda a: a[0],
                                 self.request.arguments.values())))
        client = tornado.httpclient.AsyncHTTPClient()
        command = self.build_command(self.args)
        if not command: raise tornado.web.HTTPError(204)
        client.fetch(command, callback=self.async_callback(self.on_response))

    def on_response(self, response):
        if response.error: raise tornado.web.HTTPError(500)
        body = self.preprocess(response.body)

        try:
            tree = ET.XML(body)
        except Exception as e:
            raise tornado.web.HTTPError(500)

        json = tornado.escape.json_encode(self.handle_result(tree))
        if "callback" in self.args:
            json = "%s(%s)" % (self.args["callback"], json)
        self.set_header("Content-Length", len(json))
        self.set_header("Content-Type", "text/javascript")
        self.write(json)
        self.finish()

    def build_command(self, args):
        return None

    def preprocess(self, data):
        return data

    def handle_result(self, tree):
        return []


class VehicleHandler(APIHandler):
    def get(self):
        global vehicle_coords
        global vehicle_semapore

        vehicle_semaphore.acquire()
        json = tornado.escape.json_encode(vehicle_coords)
        vehicle_semaphore.release()
        self.args = dict(zip(self.request.arguments.keys(),
                             map(lambda a: a[0],
                                 self.request.arguments.values())))
        if "callback" in self.args:
            json = "%s(%s)" % (self.args["callback"], json)
        self.set_header("Content-Length", len(json))
        self.set_header("Content-Type", "text/javascript")
        self.write(json)
        self.finish()

class NiceVehicleHandler(APIHandler):
    def get(self,line, vehicle):

        if vehicle != "vehicles":
            raise tornado.web.HTTPError(404)

        global vehicle_coords
        global vehicle_semapore

        vehicle_semaphore.acquire()

        vehicle_coords_line = [v for v in vehicle_coords if int(v['line']) == int(line)]
        print vehicle_coords_line
        json = tornado.escape.json_encode(vehicle_coords_line)
        vehicle_semaphore.release()
        self.args = dict(zip(self.request.arguments.keys(),
                             map(lambda a: a[0],
                                 self.request.arguments.values())))
        if "callback" in self.args:
            json = "%s(%s)" % (self.args["callback"], json)
        self.set_header("Content-Length", len(json))
        self.set_header("Content-Type", "application/json")
        self.write(json)
        self.finish()

class LineHandler(APIHandler):
    def get(self):
        logging.info("%s: LineHandler - start()", __appname__)
        lines = Line.objects.all()
        res = []
        for i, l in enumerate(lines):
            line = model_to_dict(l)
            line["coordinates"] = [model_to_dict(c) for c in l.coordinate_set.all()]
            res.append(line)

        json = tornado.escape.json_encode(res)

        self.args = dict(zip(self.request.arguments.keys(),
                             map(lambda a: a[0],
                                 self.request.arguments.values())))
        if "callback" in self.args:
            json = "%s(%s)" % (self.args["callback"], json)

        self.set_header("Content-Length", len(json))
        self.set_header("Content-Type", "text/javascript")
        self.write(json)
        self.finish()

class NiceLineHandler(APIHandler):
    def get(self, line):
        logging.info("%s: NiceLineHandler - start()", __appname__)
        l = Line.objects.get(name = line)
        res = []

        line = model_to_dict(l)
        line["coordinates"] = [model_to_dict(c) for c in l.coordinate_set.all()]
        res.append(line)

        json = tornado.escape.json_encode(res)

        self.args = dict(zip(self.request.arguments.keys(),
                             map(lambda a: a[0],
                                 self.request.arguments.values())))
        if "callback" in self.args:
            json = "%s(%s)" % (self.args["callback"], json)

        self.set_header("Content-Length", len(json))
        self.set_header("Content-Type", "application/json")
        self.write(json)
        self.finish()

class StationHandler(APIHandler):
    def get(self):
        logging.info("%s: StationHandler - start()", __appname__)
        stations = Station.objects.all()
        res = []
        for s in stations:
            res.append(model_to_dict(s))

        json = tornado.escape.json_encode(res)

        self.set_header("Content-Length", len(json))
        self.set_header("Content-Type", "text/javascript")
        self.write(json)
        self.finish()

class ClientHandler(tornado.web.RequestHandler):
    def get(self, dogname):
        #FIXME: remove
        try:
            dog = Dog.objects.get(username=dogname)
        except Dog.DoesNotExist:
            self.write("No dog named <i>%s</i>. Wrong spelling?" % dogname)
            return
        self.render("index.html", dog=dog)

def print_intro():
    logging.info("%s: print_intro()", __appname__)
    print "******************************************************"
    print "*                                                    *"
    print "*       CODEMOCRACY PROJECT BY POPDEVELOP            *"
    print "*                                                    *"
    print "******************************************************"
    print "*                                                    *"
    print "* source  @ http://github.com/popdevelop/codemocracy *"
    print "* blog    @ http://popdevelop.com                    *"
    print "* twitter @ http://twitter.com/popdevelop            *"
    print "*                                                    *"
    print "******************************************************"

def settings():
    global parent_conn

    # Enable Ctrl-C
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    tornado.options.parse_command_line()
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    station_fetcher = StationFetcher()
    station_fetcher.start()
    t = vehicle() 
    t.start()

def shutdown():
    global shd
    shd = True
    logging.debug('%s: shutdown complete' % __appname__)
    sys.exit(0)

def handle_signal(sig, frame):
    shutdown()

def main():
    print_intro()
    settings()

    try:
        http_server = tornado.httpserver.HTTPServer(Application())
        http_server.listen(options.port)
        tornado.ioloop.IOLoop.instance().start()

    except KeyboardInterrupt:
        shutdown()

    except Exception as out:
        logging.error(out)
        shutdown()

if __name__ == "__main__":
    main()
