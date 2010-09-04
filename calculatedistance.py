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
            totaldistance = totaldistance + distance_on_unit_sphere(olditem, item)
            distances.append(totaldistance)
        olditem = item

    ms = totaldistance / totaltime
    percent = (time.time() - atime) / totaltime
    traveleddistance = percent * totaldistance

    nbr = 0
    for dist in distances:
        if traveleddistance < dist:
            break
        nbr = nbr + 1
    nbr = nbr - 1

    pdistance = (traveleddistance - distances[nbr - 1]) / (distances[nbr] - distances[nbr - 1])
    new_lat = coords[nbr - 1].lat + ((coords[nbr].lat - coords[nbr - 1].lat) * pdistance)
    new_lon = coords[nbr - 1].lon + ((coords[nbr].lon - coords[nbr - 1].lon) * pdistance)

    return new_lat, new_lon

def get_departures(id, name):
    url = "http://www.labs.skanetrafiken.se/v2.2/stationresults.asp?selPointFrKey=%d" % id
    http_client = tornado.httpclient.HTTPClient()
    try:
        response = http_client.fetch(url)
    except tornado.httpclient.HTTPError, e:
        print "Error:", e
    data = response.body
    tree = ET.XML(data)

    lines = []

    ns = "http://www.etis.fskab.se/v1.0/ETISws"

    for line in tree.findall('.//{%s}Lines//{%s}Line' % (ns, ns)):
        mline = {}
        mline['name'] = line.find('.//{%s}Name' % ns).text
        mline['time'] = line.find('.//{%s}JourneyDateTime' % ns).text
        mline['type'] = line.find('.//{%s}LineTypeName' % ns).text
        mline['towards'] = line.find('.//{%s}Towards' % ns).text
        if str(mline['name']) == str(name):
            lines.append(mline)
    return lines

def get_vehicles(line):
    nbr_stations = line.station_set.all().count()
    stationid = line.station_set.all()[nbr_stations-2].key

    departures = get_departures(stationid, line.name)
    departures = [dep for dep in departures if tornado.escape._unicode(dep['towards']) == u'Västra Hamnen']

    deadtime = time.time() + line.duration

    vehicles = []

    for i, dep in enumerate(departures):
        arrivetime = time.mktime(time.strptime(dep['time'], "%Y-%m-%dT%H:%M:%S"))
        if arrivetime < deadtime:
            lat, lon = get_coord(line.coordinate_set.all(), arrivetime - line.duration, arrivetime)
            travtime = line.duration - (arrivetime - time.time())
            vehicles.append({'lat': lat, 'lon': lon, 'time': travtime, 'id': i})
    print vehicles

line = Line.objects.get(name="2")
get_vehicles(line)
