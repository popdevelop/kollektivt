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
__email__   = "contact@popdevelop"
__date__    = "2010-09-04"
__appname__ = 'kollektivt.se'
__version__ = '0.1'

from tornado.options import define, options
define("port", default=8888, help="Run on the given port", type=int)

class Application(tornado.web.Application):
    def __init__(self):
        self.station_fetcher = StationsFetcher()
        self.station_fetcher.start()
        self.position_interpolator = PositionInterpolator()
        self.position_interpolator.start()

        handlers = [
            (r"/", MainHandler),
            (r"/stations", StationHandler),
            (r"/lines", AllLinesHandler),
            (r"/lines/([^/]+)", LinesHandler),
            (r"/vehicles", AllVehiclesHandler),
            (r"/lines/([^/]+)/vehicles", VehiclesHandler)
        ]
        settings = dict(
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
        )
        tornado.web.Application.__init__(self, handlers, **settings)


class StationFetcher(threading.Thread):
    """
    Used to parallelize fetching of stations to speed things up.
    """
    def __init__(self, line):
        threading.Thread.__init__(self)
        self.line = line
    def run(self):
        calculatedistance.get_vehicles(self.line, True)


class StationsFetcher(threading.Thread):
    """
    Loop that fetches station updates every two minutes.
    """
    def run(self):
        while True:
            thread_list = []
            for line in Line.objects.all():
                current = StationFetcher(line)
                thread_list.append(current)
                current.start()

            for t in thread_list:
                t.join()

            logging.info("Finished fetching departure and deviation times")
            time.sleep(120)


class PositionInterpolator(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.coords = []
        self.semaphore = threading.Semaphore()

    def run (self):
        while True:
            nexttime = 0
            new_vehicle_coords = []
            for l in Line.objects.all():
                vehicles = calculatedistance.get_vehicles(l, False)
                new_vehicle_coords.extend(vehicles)

            self.semaphore.acquire()
            self.coords = new_vehicle_coords[:]
            self.semaphore.release()
            time.sleep(0.2)

    def get_coords(self):
        self.semaphore.acquire()
        coords = self.coords
        self.semaphore.release()
        return coords


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html")


class APIHandler(tornado.web.RequestHandler):
    def prepare(self):
        self.args = dict(zip(self.request.arguments.keys(),
                             map(lambda a: a[0],
                                 self.request.arguments.values())))

    def finish_json(self, data):
        json = tornado.escape.json_encode(data)
        if "callback" in self.args:
            json = "%s(%s)" % (self.args["callback"], json)
        self.set_header("Content-Length", len(json))
        self.set_header("Content-Type", "text/javascript")
        self.write(json)
        self.finish()


class XMLHandler(APIHandler):
    @tornado.web.asynchronous
    def get(self):
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
        self.finish_json(self.handle_result(tree))

    def build_command(self, args):
        return None

    def preprocess(self, data):
        return data

    def handle_result(self, tree):
        return []


class AllVehiclesHandler(XMLHandler):
    def get(self):
        self.finish_json(self.application.position_interpolator.get_coords())


class VehiclesHandler(XMLHandler):
    def get(self, line):
        coords = self.application.position_interpolator.get_coords()
        vehicle_coords_line = [v for v in coords if int(v['line']) == int(line)]
        self.finish_json(vehicle_coords_line)


class AllLinesHandler(APIHandler):
    def get(self):
        lines = Line.objects.order_by("name")
        res = []
        for i, l in enumerate(lines):
            line = model_to_dict(l)
            line["coordinates"] = [model_to_dict(c, exclude=["id", "line"]) for c in l.coordinate_set.all()]
            res.append(line)
        self.finish_json(res)


class LinesHandler(APIHandler):
    def get(self, line):
        l = Line.objects.get(name = line)
        res = []

        line = model_to_dict(l)
        line["coordinates"] = [model_to_dict(c, exclude=["id", "line"]) for c in l.coordinate_set.all()]
        res.append(line)
        self.finish_json(res)


class StationHandler(APIHandler):
    def get(self):
        stations = Station.objects.all()
        res = []
        for s in stations:
            res.append(model_to_dict(s))
        self.finish_json(res)


class ClientHandler(tornado.web.RequestHandler):
    def get(self, dogname):
       #FIXME: removes
       try:
           dog = Dog.objects.get(username=dogname)
       except Dog.DoesNotExist:
           self.write("No dog named <i>%s</i>. Wrong spelling?" % dogname)
           return
       self.render("index.html", dog=dog)


def main():
    print "kollektivt.se by Popdevelop 2010"

    # Enable Ctrl-C
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    tornado.options.parse_command_line()
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

    try:
       http_server = tornado.httpserver.HTTPServer(Application())
       http_server.listen(options.port)
       tornado.ioloop.IOLoop.instance().start()
    except Exception as out:
       logging.error(out)

if __name__ == "__main__":
    main()
