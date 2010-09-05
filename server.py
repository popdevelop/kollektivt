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

__author__  = "http://popdevelop.com, Johan Brissmyr, Johan Gyllenspetz, Joel Larsson, Sebastian Wallin"
__email__   = "use twitter @popdevelop"
__date__    = "2010-09-04"
__appname__ = 'kollektivt.se'
__version__ = '0.1'


from tornado.options import define, options
define("port", default=8888, help="Run on the given port", type=int)

vehicle_coords = []
shd = False

class vehicle(threading.Thread):
    def run (self):
         global vehicle_coords
         logging.info("%s: VehicleThread - start", __appname__)
         while not shd:
    #         for l in Line.objects.all():
             l = Line.objects.get(name="2")
             vehicles = calculatedistance.get_vehicles(l)
             vehicle_coords = vehicles
             time.sleep(5)
             logging.info("%s: VehicleThread - update vehicles()", __appname__)

class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", MainHandler),
            (r"/lines", LineHandler),
            (r"/vehicles", VehicleHandler)
#            (r"/route/([^/]+)", RouteHandler)
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
        self.set_header("Content-Type", "application/json")
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

        json = tornado.escape.json_encode(vehicle_coords)
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
        all_lines = []
        for i,l in enumerate(lines):
            coords = l.coordinate_set.all()
            print l.name
            all_lines.append([model_to_dict(c) for c in coords])

        json = tornado.escape.json_encode({ "coordinates":all_lines} )

        self.args = dict(zip(self.request.arguments.keys(),
                             map(lambda a: a[0],
                                 self.request.arguments.values())))
        if "callback" in self.args:
            json = "%s(%s)" % (self.args["callback"], json)

        self.set_header("Content-Length", len(json))
        self.set_header("Content-Type", "application/json")
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
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    tornado.options.parse_command_line()
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    t = vehicle() 
    t.start()

def shutdown():
    global shd
    logging.debug('%s: shutdown' % __appname__)
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
