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

from tornado.options import define, options
define("port", default=8888, help="Run on the given port", type=int)

class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", MainHandler),
            (r"/route", RouteHandler)
#            (r"/route/([^/]+)", RouteHandler)
        ]
        settings = dict(
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
        )
        tornado.web.Application.__init__(self, handlers, **settings)


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Welcome to Dogvibes!")


class APIHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    def get(self):
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


class RouteHandler(APIHandler):
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
            print x, y
            lat, lon = util.RT90_to_WGS84(x, y)
            print lat, lon
            stations.append({'lat':lat,'lon':lon})
        return {"coordinates":stations}

# enligt..
#                 {"coordinates" :[
#                    {"lat": 55.12, "lon": 13.12},
#                    {"lat": 54.13, "lon": 12.11},
#                    {"lat": 14.13, "lon": 14.88},
#                    {"lat": 55.12, "lon": 13.12},
#                 ]}


class ClientHandler(tornado.web.RequestHandler):
    def get(self, dogname):
        try:
            dog = Dog.objects.get(username=dogname)
        except Dog.DoesNotExist:
            self.write("No dog named <i>%s</i>. Wrong spelling?" % dogname)
            return
        self.render("index.html", dog=dog)


def main():
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
    main()
