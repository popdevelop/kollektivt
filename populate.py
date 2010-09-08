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

def grab_station(line, name):
    ename = tornado.escape.url_escape(name)
    url = "http://www.labs.skanetrafiken.se/v2.2/querypage.asp?inpPointFr=%s&inpPointTo=%s" % (ename, "Davidshall")
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
    s = Station.objects.create(line=line, name=tornado.escape._unicode(name), lon=lon, lat=lon, key=key)
    print s

def grab_route(line):
    nbr_stations = line.station_set.all().count()
    route = Route.objects.create(line=line)
    print "--- Route forward ---"
    for i in range(nbr_stations-1):
        grab_segment(route,
                     line.station_set.all()[i],
                     line.station_set.all()[i+1])
    route = Route.objects.create(line=line)
    print "--- Route reverse ---"
    for i in range(nbr_stations-1, 1, -1):
        grab_segment(route,
                     line.station_set.all()[i],
                     line.station_set.all()[i-1])
    key_from = line.station_set.all()[0].key
    key_to = line.station_set.all()[nbr_stations-1].key
    grab_times(line, key_from, key_to, 0) # forward
    grab_times(line, key_to, key_from, 1) # reverse

def grab_segment(route, station_from, station_to):
    # Query 1
    print "Fetching segment: %s -> %s" % (station_from, station_to)
    url = "http://www.labs.skanetrafiken.se/v2.2/resultspage.asp?cmdaction=next&selPointFr=m|%s|0&selPointTo=m|%s|0&LastStart=2010-09-04" % (station_from.key, station_to.key)
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
    station_from.departure = dep_time
    station_to.arrival = arr_time

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
    for coord in tree.find('.//{%s}Coords' % ns):
        x = float(coord.find('.//{%s}X' % ns).text)
        y = float(coord.find('.//{%s}Y' % ns).text)
        lat, lon = util.RT90_to_WGS84(x, y)
        Coordinate.objects.create(route=route, lat=lat, lon=lon)

# FIXME: this only grabs times based on last and first station. Could be wrong if a closer line is found
def grab_times(line, key_from, key_to, index):
    url = "http://www.labs.skanetrafiken.se/v2.2/resultspage.asp?cmdaction=next&selPointFr=m|%s|0&selPointTo=m|%s|0&LastStart=2010-09-04" % (key_from, key_to)
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

    route = line.route_set.all()[index]
    route.duration = duration
    route.save()
    print "Route[%d] duration: %d s" % (index, duration)

def grab_direction(line, index):
    key = line.station_set.all()[index].key
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
        if name == str(line.name):
            towards = l.find('.//{%s}Towards' % ns).text
            return towards.split(" ")[0]

def grab_directions(line):
    route_forward = line.route_set.all()[0]
    route_reverse = line.route_set.all()[1]
    route_forward.towards = hej = grab_direction(line, 0)
    route_reverse.towards = grab_direction(line, line.station_set.all().count()-1)
    print "Forward end-station: %s" % route_forward.towards
    print "Reverse end-station: %s" % route_reverse.towards
    route_forward.save()
    route_reverse.save()

def grab_line(name, stations):
    line = Line.objects.create(name=name)
    for station in stations:
        grab_station(line, station)
    grab_route(line)
    grab_directions(line)
    print line.route_set.all()


def debug_grab_line(name):
    line = Line.objects.get(name=name)
#    for station in stations:
#        grab_station(line, station)


#    Coordinate.objects.all().delete()
#    grab_route(line)

    grab_directions(line)
    print line.route_set.all()


if __name__ == "__main__":
    debug_grab_line("4")

