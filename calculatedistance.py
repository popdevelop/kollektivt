# -*- coding: utf-8 -*-

import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
from models import Line
from models import Station
from models import Coordinate
from models import Route
import math
import time
import tornado.httpclient
import urllib
import xml.etree.ElementTree as ET
from datetime import timedelta
import threading
import hashlib

class Profiler:
    profile = {}
    sum = 0
    @classmethod
    def addTime(self, Func, time):
        if(Func not in self.profile):
            self.profile[Func] = 0;
        self.profile[Func] += time
        self.sum += time
    
    @classmethod
    def summary(self):
        print "----------"
        for t in self.profile:
            print "%s: %d (%d%%)" % (t, self.profile[t], self.profile[t]*100/self.sum)


def distance_on_unit_sphere(X, Y):
    # Convert latitude and longitude to 
    # spherical coordinates in radians.
    degrees_to_radians = math.pi/180.0

    lat1 = X.lat
    lat2 = Y.lat
    long1 = X.lon
    long2 = Y.lon

    # phi = 90 - latitude
    phi1 = (90.0 - lat1)*degrees_to_radians
    phi2 = (90.0 - lat2)*degrees_to_radians
        
    # theta = longitude
    theta1 = long1*degrees_to_radians
    theta2 = long2*degrees_to_radians
        
    # Compute spherical distance from spherical coordinates.
        
    # For two locations in spherical coordinates 
    # (1, theta, phi) and (1, theta, phi)
    # cosine( arc length ) = 
    #    sin phi sin phi' cos(theta-theta') + cos phi cos phi'
    # distance = rho * arc length
    
    cos = (math.sin(phi1)*math.sin(phi2)*math.cos(theta1 - theta2) + 
           math.cos(phi1)*math.cos(phi2))
    arc = math.acos( cos )

    # Remember to multiply arc by the radius of the earth 
    # in your favorite set of units to get length.
    return (arc * 6373 * 1000)

def get_new_coords_vehicle(vehicle):
    speed = 10
    traveledtime = time.time() - vehicle['time']
    traveleddistance = traveledtime * speed


def get_coords_backward(coords, startcoord, stopcoord, percent):
    olditem = None
    totaldistance = 0

    distances = [0]

    for item in coords[startcoord:stopcoord]:
        if olditem != None:
            if not (olditem.lat == item.lat and olditem.lon == item.lon):
                totaldistance = totaldistance + distance_on_unit_sphere(olditem, item)
            distances.append(totaldistance)
        olditem = item

    traveleddistance = percent * totaldistance

    nbr = 0
    for dist in distances:
        if traveleddistance <= dist:
            break
        nbr = nbr + 1

    #FIXME a small distance is added since the route sometimes have two distances which are the same
    pdistance = (traveleddistance - distances[nbr - 1]) / ((distances[nbr] - distances[nbr - 1]) + 0.01)

    nbr += startcoord

    new_lat = coords[nbr - 1].lat + ((coords[nbr].lat - coords[nbr - 1].lat) * pdistance)
    new_lon = coords[nbr - 1].lon + ((coords[nbr].lon - coords[nbr - 1].lon) * pdistance)

    return new_lat, new_lon


def get_departures_full(id):
    url = "http://www.labs.skanetrafiken.se/v2.2/stationresults.asp?selPointFrKey=%d" % id
    http_client = tornado.httpclient.HTTPClient()
    try:
        response = http_client.fetch(url)
    except tornado.httpclient.HTTPError, e:
        print "Error:", e
        return lines
    data = response.body
    tree = ET.XML(data)

    ns = "http://www.etis.fskab.se/v1.0/ETISws"

    lines = []
 
    for line in tree.findall('.//{%s}Lines//{%s}Line' % (ns, ns)):
        mline = {}
        mline['name'] = line.find('.//{%s}Name' % ns).text
        mline['time'] = line.find('.//{%s}JourneyDateTime' % ns).text
        mline['type'] = line.find('.//{%s}LineTypeName' % ns).text
        mline['towards'] = line.find('.//{%s}Towards' % ns).text

        # Check delay
        devi = line.find('.//{%s}DepTimeDeviation' % ns)
        if devi != None:
            mline['deviation'] = devi.text
        else:
            mline['deviation'] = "0"

        lines.append(mline)

    return lines


stations = {}
class AllStationFetcher(threading.Thread):
    def __init__(self, station_id):
        threading.Thread.__init__(self)
        self.station_id = station_id
        self.stations = None
    def run(self):
        self.stations = get_departures_full(self.station_id)


def get_all_stations():
    global stations

    thread_list = []
    visited = []
    for r in Route.objects.all():
        for s in r.station_set.all():
            if s.key in visited: continue
            current = AllStationFetcher(s.key)
            visited.append(s.key)
            thread_list.append(current)
            current.start()

    for t in thread_list:
        t.join()
        stations[t.station_id] = t.stations


def update_pos(vehicle):
    (vehicle['lat'], vehicle['lon']) = get_new_coords(vehicle)
    return vehicle

 
def update_vehicle_positions(vehicles):
    vehicles_new = []

    for v in vehicles:
        vehicles_new = update_pos(v)

    return vehicles_new


def get_station_deviations(l, station, towards):
    global stations
    p = stations[station.key]
    return [k for k in p if (tornado.escape._unicode(k['towards']).startswith(towards)) and tornado.escape._unicode(str(k['name'])) == str(l.name)]


def get_vehicles_pos(l, route):
    oldtime = 0
    vehicles = []
    nbr_stations = route.station_set.all().count()

    for i in range(2, route.station_set.all().count()):
        s = route.station_set.all()[i]
        p = get_station_deviations(l, s, route.towards)
        if len(p) < 1: continue
        newtime = time.mktime(time.strptime(p[0]['time'], "%Y-%m-%dT%H:%M:%S"))
        if newtime < oldtime:
            q = route.station_set.all()[i-1]
            vehicle = {}
            vehicle['line'] = l.name
            vehicle['time'] = time.time()
            devi = (newtime + 60 * int(p[0]['deviation']) + 60) - time.time()
            for j, c in enumerate(route.coordinate_set.all()):
                if c.id == q.coordinate.id: break
            c0 = j
            for j, c in enumerate(route.coordinate_set.all()):
                if c.id == s.coordinate.id: break
            c1 = j
            print p[0]['time']
            print "Station: %s" % s.name
            print "Deviation: %s" % p[0]['deviation']
            print time.time() - (newtime + 60 * int(p[0]['deviation']) + 60)
            print "*************************************"
            (vehicle['lat'],vehicle['lon']) = get_coords_backward(l.route_set.all()[0].coordinate_set.all(), c0, c1, min(1, max(0, 1 - devi/(s.duration))))
            vehicles.append(vehicle)
        oldtime = newtime

    endstation = route.station_set.all()[nbr_stations - 2]
    fendstation = get_station_deviations(l, endstation, route.towards)

    for i,v in enumerate(vehicles):
        v['id'] = hashlib.md5(str(time.mktime(time.strptime(fendstation[i]['time'], "%Y-%m-%dT%H:%M:%S"))) + str(endstation.key) + str(l.name))
    return vehicles
