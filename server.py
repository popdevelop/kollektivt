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
import cjson

os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
from models import Line
from models import Coordinate
from models import Station

from tornado.options import define, options
define("port", default=8888, help="Run on the given port", type=int)


class Application(tornado.web.Application):
    def __init__(self):
        # Periodic threads
        self.position_updater = PositionUpdater()
        self.position_updater.update()
        self.position_updater.start()
        self.position_interpolator = PositionInterpolator(self.position_updater)
        self.position_interpolator.start()

        # A RAM cache of static database content
        self.cache = Cache()

        handlers = [
            (r"/", MainHandler),
            (r"/api", AHandler),
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


class MainHandler(tornado.web.RequestHandler):
    """
    Renders the client.
    """
    def get(self):
        self.render("index.html")

class AHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("api.html")


class PositionUpdater(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.vehicles = []
        self.semaphore = threading.Semaphore()
        self.version = 0

    def run (self):
        while True:
            time.sleep(120)
            self.update()

    def update (self):
        calculatedistance.get_all_stations()
        vehicles = []
        for l in Line.objects.all():
            vehicles.extend(calculatedistance.get_vehicles_pos(l, l.route_set.all()[0], self.version))
            vehicles.extend(calculatedistance.get_vehicles_pos(l, l.route_set.all()[1], self.version))
        self.version = self.version + 1
        self.semaphore.acquire()
        self.vehicles = vehicles
        self.semaphore.release()

    def get_vehicles(self):
        self.semaphore.acquire()
        vehicles = self.vehicles
        self.semaphore.release()
        return vehicles


class PositionInterpolator(threading.Thread):
    def __init__(self, position_updater):
        threading.Thread.__init__(self)
        self.position_updater = position_updater
        self.semaphore = threading.Semaphore()

    def run (self):
        while True:
            vehicles = calculatedistance.update_vehicle_positions(self.position_updater.get_vehicles())
            self.semaphore.acquire()
            self.vehicles = vehicles
            self.semaphore.release()
            time.sleep(0.7)

    def get_vehicles(self):
        self.semaphore.acquire()
        vehicles = self.vehicles
        self.semaphore.release()
        return vehicles


class APIHandler(tornado.web.RequestHandler):
    def prepare(self):
        # Only use the first of each argument
        self.args = dict(zip(self.request.arguments.keys(),
                             map(lambda a: a[0],
                                 self.request.arguments.values())))

    def finish_json(self, data):
        json = cjson.encode(data)
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
        client.fetch(command, callback=self.async_callback(self._on_response))

    def _on_response(self, response):
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
        self.finish_json(self.application.position_interpolator.get_vehicles())


class VehiclesHandler(XMLHandler):
    def get(self, name):
        if Line.objects.filter(name=name).count() == 0:
            raise tornado.web.HTTPError(400)
        coords = self.application.position_interpolator.get_vehicles()
        self.finish_json([v for v in coords if int(v['line']) == int(name)])


class AllLinesHandler(APIHandler):
    def get(self):
        self.finish_json(self.application.cache.get_lines())


class LinesHandler(APIHandler):
    def get(self, name):
        if Line.objects.filter(name=name).count() == 0:
            raise tornado.web.HTTPError(400)
        self.finish_json(self.application.cache.get_line(name))


class StationHandler(APIHandler):
    def get(self):
        self.finish_json([model_to_dict(s) for s in Stations.objects.all()])


class Cache():
    """
    Cache static database entries in RAM for faster access
    """
    def __init__(self):
        self.lines = []
        ls = Line.objects.order_by("name")
        for l in ls:
            line = model_to_dict(l)
            route0 = l.route_set.all()[0]
            route1 = l.route_set.all()[1]
            coords = [c.to_dict() for c in route0.coordinate_set.all()]
            coords.extend([c.to_dict() for c in route1.coordinate_set.all()])
            line["coordinates"] = coords
            self.lines.append(line)

    def get_lines(self):
        return self.lines

    def get_line(self, name):
        for line in self.lines:
            if str(line["name"]) == name:
                return line


def main():
    # Enable Ctrl-C when using threads
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    tornado.options.parse_command_line()
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

    print "kollektivt.se by Popdevelop 2010"

    #try:
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()
    #except Exception as out:
    #logging.error(out)

if __name__ == "__main__":
    main()
