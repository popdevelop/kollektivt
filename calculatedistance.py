# -*- coding: utf-8 -*-

import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
from models import Line
from models import Station
from models import Coordinate
import math
import time
import tornado.httpclient
import urllib
import xml.etree.ElementTree as ET
from datetime import timedelta
import threading

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

def get_coord(coords, atime, btime):
    olditem = None
    totaldistance = 0
    totaltime = btime - atime
    distances = [0]

    for item in coords:
        if olditem != None:
            if not (olditem.lat == item.lat and olditem.lon == item.lon):
                totaldistance = totaldistance + distance_on_unit_sphere(olditem, item)
            distances.append(totaldistance)
        olditem = item

    ms = totaldistance / totaltime

    percent = (time.time() - atime) / totaltime

    # bus is in garage
    if (percent >= 1):
        return 0,0

    traveleddistance = percent * totaldistance

    nbr = 0
    for dist in distances:
        if traveleddistance <= dist:
            break
        nbr = nbr + 1

    #FIXME a small distance is added since the route sometimes have two distances which are the same
    pdistance = (traveleddistance - distances[nbr - 1]) / ((distances[nbr] - distances[nbr - 1]) + 0.01)
    new_lat = coords[nbr - 1].lat + ((coords[nbr].lat - coords[nbr - 1].lat) * pdistance)
    new_lon = coords[nbr - 1].lon + ((coords[nbr].lon - coords[nbr - 1].lon) * pdistance)

    return new_lat, new_lon

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

saved = {}
def get_departures(id, name, updatedata):
    global saved
    key = str(id)+"L"+str(name)

    lines = []

    if updatedata:
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

            if str(mline['name']) == str(name):
                lines.append(mline)

        saved[key] = lines[:]
            
    elif not saved.has_key(key):
        return []
    
    return saved[key]

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

def get_vehicles_full(line, stationid, coords, towards, updatedata):
    departures = get_departures(stationid, line.name, updatedata)
    departures = [dep for dep in departures if tornado.escape._unicode(dep['towards']).startswith(towards)]

    deadtime = time.time() + line.duration

    vehicles = []
    for dep in departures:
        # Today we assume that the last stop is two minutes from the next last stop
        arrivetime = time.mktime(time.strptime(dep['time'], "%Y-%m-%dT%H:%M:%S")) + (2 * 60)
        if arrivetime < deadtime:
            lat, lon = get_coord(coords, arrivetime - line.duration, arrivetime + int(dep['deviation']))
            if lat != 0:
                vehicles.append({'line':line.name,'lat': lat, 'lon': lon, 'id': str(arrivetime) + str(stationid) + str(line.name)})
    return vehicles

def get_vehicles(line, updatedata):
    nbr_stations = line.station_set.all().count()
    stationid = line.station_set.all()[nbr_stations-2].key
    stationid_reverse = line.station_set.all()[1].key

    vehicles = get_vehicles_full(line, stationid, line.coordinate_set.all(), line.forward, updatedata)
    vehicles_reverse = get_vehicles_full(line, stationid_reverse, line.coordinate_set.order_by("-id"), line.reverse, updatedata)

    vehicles.extend(vehicles_reverse)

    return vehicles 


stations = {}
tstations = {}
class AllStationFetcher(threading.Thread):
    """
    Used to parallelize fetching of stations to speed things up.
    """
    def __init__(self, stationid):
        threading.Thread.__init__(self)
        self.stationid = stationid
    def run(self):
        global tstations
        tstations[self.stationid] = get_departures_full(self.stationid)

def get_all_stations():
    global stations
    global tstations

    thread_list = []

    tstations = {}

    for l in Line.objects.all():
        for s in l.station_set.all():
            current = AllStationFetcher(s.key)
            thread_list.append(current)
            current.start()

    for t in thread_list:
        t.join()

    stations = tstations

def get_station_deviations(l, station, towards):
    global stations

    p = stations[station.key]

    return [k for k in p if (tornado.escape._unicode(k['towards']).startswith(towards)) and tornado.escape._unicode(str(k['name'])) == str(l.name)]

all_vehicles = []
all_vehicles_upd = []
def get_vehicles_pos(l, route, endstation):
    oldtime = 0
    vehicles = []

    for s in l.station_set.all():
        p = get_station_deviations(l, s, route.towards)
        if len(p) < 1:
            continue
        newtime = time.mktime(time.strptime(p[0]['time'], "%Y-%m-%dT%H:%M:%S"))
        if newtime < oldtime:
            vehicle = {}
            vehicle['line'] = l.name
            vehicle['time'] = time.time()
            devi = (newtime + 60 * int(p[0]['deviation']) + 60) - time.time()
            (vehicle['lat'],vehicle['lon']) = get_coords_backward(l.route_set.all()[0].coordinate_set.all(), 10, 80, devi/(2*60))
            print p[0]['time']
            print "Station: %s" % s.name
            print "Deviation: %s" % p[0]['deviation']
            print time.time() - (newtime + 60 * int(p[0]['deviation']) + 60)
            print "*************************************"
            vehicles.append(vehicle)
        oldtime = newtime

    fendstation = get_station_deviations(l, endstation, route.towards)

    global all_vehicles_upd
    for i,v in enumerate(vehicles):
        v['id'] = str(time.mktime(time.strptime(fendstation[i]['time'], "%Y-%m-%dT%H:%M:%S"))) + str(endstation.key) + str(l.name)
    all_vehicles_upd.extend(vehicles)


class PositionUpdater(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run (self):
        while True:
            time.sleep(120)
            self.update()

    def update (self):
        get_all_stations()
        for l in Line.objects.all():
            nbr_stations = l.station_set.all().count()
            get_vehicles_pos(l, l.route_set.all()[0], l.station_set.all()[nbr_stations - 2])
        all_vehicles = all_vehicles_upd

pu = PositionUpdater()
pu.update()
pu.start()

def update_vehicle_positions():
    print "Update positions here"

class PositionInterpolater(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run (self):
        while True:
            update_vehicle_positions()
            time.sleep(0.2)

pi = PositionInterpolater()
pi.start()
