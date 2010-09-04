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
from multiprocessing import Process,Queue

os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
from models import Line

__author__  = "http://popdevelop.com, Johan Brissmyr, Johan Gyllenspetz, Joel Larsson, Sebastian Wallin"
__email__   = "use twitter @popdevelop"
__date__    = "2010-09-04"
__appname__ = 'kollektivt.se'
__version__ = '0.1'

children = []
semaphore = threading.BoundedSemaphore()
q = Queue()

from tornado.options import define, options
define("port", default=8888, help="Run on the given port", type=int)

def vehicle_thread (q):
     global vehicle_coords
     logging.info("%s: VehicleThread - start", __appname__)
     while True:
#         for l in Line.objects.all():
         l = Line.objects.get(name="2")
         vehicles = calculatedistance.get_vehicles(l)
         print "INSIDE", vehicles
         print "got vehicles for line, ", l.name
         q.put(vehicles)

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
        global q
        vehicle_coords = q.get()
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
    def build_command(self, args):
        params = urllib.urlencode({'cf':"0194162221071412519640991", 'id':"1"})
        url = "http://www.labs.skanetrafiken.se/v2.2/journeypath.asp?%s"
        print url
        f = urllib.urlopen(url % params)
        return url % params

    def preprocess(self, data):
        return re.sub(r"&lt;", r"<", re.sub(r"&gt;", r">", data))

    def handle_result(self, tree):
        ns = "http://www.etis.fskab.se/v1.0/ETISws"

        stations = []
        for coord in tree.find('.//{%s}Coords' % ns):
            x = float(coord.find('.//{%s}X' % ns).text)
            y = float(coord.find('.//{%s}Y' % ns).text)
            lat, lon = util.RT90_to_WGS84(x, y)
            stations.append({'lat':lat,'lon':lon})
        return [{"coordinates":stations}]

# enligt..
#                 {"coordinates" :[
#                    {"lat": 55.12, "lon": 13.12},
#                    {"lat": 54.13, "lon": 12.11},
#                    {"lat": 14.13, "lon": 14.88},
#                    {"lat": 55.12, "lon": 13.12},
#                 ]}

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
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    tornado.options.parse_command_line()
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    kid = Process(target=vehicle_thread, args=(q,))
    children.append(kid)
    kid.start()

def shutdown():
    logging.debug('%s: shutdown' % __appname__)
    semaphore.acquire() 
    for child in children:
        try:
            if child.is_alive():
                children.remove(child)
                logging.debug("%s: Kill my child: %s" % (__appname__, child.name))
                child.terminate()
        except AssertionError:
            logging.error('%s: Atleast on dead kid found' % __appname__)

    logging.debug('%s: shutdown complete' % __appname__)
    semaphore.release() 
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
