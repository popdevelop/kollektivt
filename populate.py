# -*- coding: utf-8 -*-

import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
from models import Line
from models import Station
from models import Route
from models import Coordinate
import urllib
import re
import xml.etree.ElementTree as ET
import sys
import tornado.escape
import util
import tornado.httpclient
import time

def grab_station(route, name):
    ename = tornado.escape.url_escape(name)
    url = "http://www.labs.skanetrafiken.se/v2.2/querypage.asp?inpPointFr=%s&inpPointTo=%s" % (ename, "Lund")
    http_client = tornado.httpclient.HTTPClient()
    try:
        response = http_client.fetch(url)
    except tornado.httpclient.HTTPError, e:
        print "Error:", e
    data = response.body

    tree = ET.XML(data)
    ns = "http://www.etis.fskab.se/v1.0/ETISws"
    coord = tree.find('.//{%s}StartPoints' % ns)[0]
    found_name = coord.find('.//{%s}Name' % ns).text
    key = coord.find('.//{%s}Id' % ns).text
    x = coord.find('.//{%s}X' % ns).text
    y = coord.find('.//{%s}Y' % ns).text
    lat, lon = util.RT90_to_WGS84(int(x), int(y))
    s = Station.objects.create(route=route, name=tornado.escape._unicode(name), key=key)
    print s

def connect_stations(route):
    nbr_stations = route.station_set.all().count()
    for i in range(nbr_stations-1):
        grab_segment(route,
                     route.station_set.all()[i],
                     route.station_set.all()[i+1])
    # Special case. First station gets first coordinate

    key_from = route.station_set.all()[0].key
    key_to = route.station_set.all()[nbr_stations-1].key
    grab_times(route, key_from, key_to, 0)

def grab_segment(route, station_from, station_to):
    # Query 1
    url = "http://www.labs.skanetrafiken.se/v2.2/resultspage.asp?cmdaction=next&selPointFr=m|%s|0&selPointTo=m|%s|0&LastStart=2010-12-30" % (station_from.key, station_to.key)
    http_client = tornado.httpclient.HTTPClient()
    try:
        response = http_client.fetch(url)
    except tornado.httpclient.HTTPError, e:
        print "Error:", e
    data = response.body
    tree = ET.XML(data)
    ns = "http://www.etis.fskab.se/v1.0/ETISws"
    cf = tree.find('.//{%s}JourneyResultKey' % ns).text
    dep_time = tree.find('.//{%s}DepDateTime' % ns).text
    arr_time = tree.find('.//{%s}ArrDateTime' % ns).text

    dep_time = int(time.mktime(time.strptime(dep_time, "%Y-%m-%dT%H:%M:%S")))
    arr_time = int(time.mktime(time.strptime(arr_time, "%Y-%m-%dT%H:%M:%S")))
    station_to.duration = arr_time - dep_time

    print "Fetching segment: %s -> %s (%ds)" % (station_from, station_to,
                                                station_to.duration)
    # Query 2
    url = "http://www.labs.skanetrafiken.se/v2.2/journeypath.asp?cf=%s&id=1" % cf
    http_client = tornado.httpclient.HTTPClient()
    try:
        response = http_client.fetch(url)
    except tornado.httpclient.HTTPError, e:
        print "Error:", e
    data = response.body
    data = re.sub(r"&lt;", r"<", re.sub(r"&gt;", r">", data))

    tree = ET.XML(data)
    ns = "http://www.etis.fskab.se/v1.0/ETISws"
    first_coord = None
    last_coord = None
    for coord in tree.find('.//{%s}Coords' % ns):
        x = float(coord.find('.//{%s}X' % ns).text)
        y = float(coord.find('.//{%s}Y' % ns).text)
        lat, lon = util.RT90_to_WGS84(x, y)
        last_coord = Coordinate.objects.create(route=route, lat=lat, lon=lon)
        if not first_coord:
            first_coord = last_coord

    station_from.coordinate = first_coord
    station_to.coordinate = last_coord
    station_to.save()

# FIXME: this only grabs times based on last and first station. Could be wrong if a closer line is found
def grab_times(route, key_from, key_to, index):
    url = "http://www.labs.skanetrafiken.se/v2.2/resultspage.asp?cmdaction=next&selPointFr=m|%s|0&selPointTo=m|%s|0&LastStart=2010-12-30" % (key_from, key_to)
    http_client = tornado.httpclient.HTTPClient()
    try:
        response = http_client.fetch(url)
    except tornado.httpclient.HTTPError, e:
        print "Error:", e
    data = response.body

    tree = ET.XML(data)
    ns = "http://www.etis.fskab.se/v1.0/ETISws"
    cf = tree.find('.//{%s}JourneyResultKey' % ns).text
    dep_time = tree.find('.//{%s}DepDateTime' % ns).text
    arr_time = tree.find('.//{%s}ArrDateTime' % ns).text

    dep_time = int(time.mktime(time.strptime(dep_time, "%Y-%m-%dT%H:%M:%S")))
    arr_time = int(time.mktime(time.strptime(arr_time, "%Y-%m-%dT%H:%M:%S")))
    duration = arr_time - dep_time

    route.duration = duration
    route.save()
    print "Total duration: %d s" % duration

def grab_direction(route):
    key = route.station_set.all()[0].key
    url = "http://www.labs.skanetrafiken.se/v2.2/stationresults.asp?selPointFrKey=%s" % key
    http_client = tornado.httpclient.HTTPClient()
    try:
        response = http_client.fetch(url)
    except tornado.httpclient.HTTPError, e:
        print "Error:", e
    data = response.body

    tree = ET.XML(data)
    ns = "http://www.etis.fskab.se/v1.0/ETISws"
    for l in tree.find('.//{%s}Lines' % ns):
        name = l.find('.//{%s}Name' % ns).text
        if name == str(route.line.name):
            towards = l.find('.//{%s}Towards' % ns).text
            route.towards = towards.split(" ")[0]
            print "Towards: %s" % route.towards
            route.save()
            return

def grab_directions(line):
    route_forward = line.route_set.all()[0]
    route_reverse = line.route_set.all()[1]
    route_forward.towards = hej = grab_direction(line, 0)
    route_reverse.towards = grab_direction(line, line.station_set.all().count()-1)
    print "Forward end-station: %s" % route_forward.towards
    print "Reverse end-station: %s" % route_reverse.towards
    route_forward.save()
    route_reverse.save()

def grab_line(name, keys):
    line = Line.objects.create(name=name)

    forward = Route.objects.create(line=line)
    reverse = Route.objects.create(line=line)

    print "=== FORWARD ==="
    for key in keys:
        grab_station(forward, key)
    connect_stations(forward)
    grab_direction(forward)

    print "=== REVERSE ==="
    keys.reverse()
    for key in keys:
        grab_station(reverse, key)
    connect_stations(reverse)
    grab_direction(reverse)


def debug_grab_line(name):
    Line.objects.all().delete()
    Route.objects.all().delete()
    Coordinate.objects.all().delete()
    keys=["Malmö Scaniabadet", "Malmö Turning Torso", "Malmö Propellergatan", "Malmö Lindängen"]

    line = Line.objects.create(name="2")

    forward = Route.objects.create(line=line)
    reverse = Route.objects.create(line=line)

    print "=== FORWARD ==="
    for key in keys:
        grab_station(forward, key)
    connect_stations(forward)

    print "=== REVERSE ==="
    keys.reverse()
    for key in keys:
        grab_station(reverse, key)
    connect_stations(reverse)


if __name__ == "__main__":
    debug_grab_line("4")

