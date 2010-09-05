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

#incrementing idnbr
idnbr = 0

def distance_on_unit_sphere(X, Y):
    # Convert latitude and longitude to 
    # spherical coordinates in radians.
    degrees_to_radians = math.pi/180.0

    lat1 = X.lat
    lat2 = Y.lat
    long1 = X.lon
    long2 = X.lon

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

saved = {}
def get_departures(id, name, updatedata):
    global saved
    key = str(id)+"L"+str(name)

    if not saved.has_key(key) or updatedata:
        url = "http://www.labs.skanetrafiken.se/v2.2/stationresults.asp?selPointFrKey=%d" % id
        http_client = tornado.httpclient.HTTPClient()
        try:
            response = http_client.fetch(url)
        except tornado.httpclient.HTTPError, e:
            print "Error:", e
        data = response.body
        saved[key] = data
    else:
        data = saved[key]

    tree = ET.XML(data)

    lines = []

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
    return lines

def get_vehicles_full(line, stationid, coords, towards, updatedata):
    global idnbr
    departures = get_departures(stationid, line.name, updatedata)
    departures = [dep for dep in departures if tornado.escape._unicode(dep['towards']).startswith(towards)]

    deadtime = time.time() + line.duration

    vehicles = []

    for dep in departures:
        arrivetime = time.mktime(time.strptime(dep['time'], "%Y-%m-%dT%H:%M:%S"))
        if arrivetime < deadtime:
            lat, lon = get_coord(coords, arrivetime - line.duration, arrivetime + int(dep['deviation']))
            travtime = line.duration - (arrivetime - time.time())
            if lat != 0:
                vehicles.append({'line':line.name,'lat': lat, 'lon': lon, 'time': travtime, 'id': idnbr + (100 * int(line.name))})
                idnbr = idnbr + 1

    return vehicles

def get_vehicles(line, updatedata):
    global idnbr
    nbr_stations = line.station_set.all().count()
    stationid = line.station_set.all()[nbr_stations-2].key
    stationid_reverse = line.station_set.all()[2].key

    idnbr = 0
    vehicles = get_vehicles_full(line, stationid, line.coordinate_set.all(), line.forward, updatedata)
    vehicles_reverse = get_vehicles_full(line, stationid_reverse, line.coordinate_set.order_by("-id"), line.reverse, updatedata)

    vehicles.extend(vehicles_reverse)

    return vehicles 

#for line in Line.objects.all():
#    print get_vehicles(line, True)
