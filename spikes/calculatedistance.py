import math
import time

def distance_on_unit_sphere(X, Y):
    # Convert latitude and longitude to 
    # spherical coordinates in radians.
    degrees_to_radians = math.pi/180.0
        
    lat1 = X[0]
    lat2 = Y[0]
    long1 = X[1]
    long2 = Y[1]

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
            distance = distance_on_unit_sphere(olditem, item)
            distances.append(distance)
            totaldistance = totaldistance + distance 
        olditem = item

    ms = totaldistance / totaltime
    percent = (time.time() - atime) / totaltime
    traveleddistance = percent * totaldistance

    nbr = 0
    for dist in distances:
        if traveleddistance < dist:
            print dist
            break
        nbr = nbr + 1

    pdistance = (traveleddistance - distances[nbr - 1]) / (distances[nbr] - distances[nbr - 1])
    newx = coords[nbr - 1][0] + ((coords[nbr][0] - coords[nbr - 1][0]) * pdistance)
    newy = coords[nbr - 1][1] + ((coords[nbr][1] - coords[nbr - 1][1]) * pdistance)

    ret = [newx, newy]

    print ret
    return ret

ar = [[13.5139, 55.522779999999997],[13.5151, 55.522640000000003],[13.509650000000001, 55.495750000000001],[13.50759, 55.494639999999997],[13.08794, 55.558010000000003],[12.93746, 55.819020000000002],[12.936019999999999, 55.8217],[12.97565, 55.863680000000002],[12.989039999999999, 55.868819999999999]]

#get_coord(ar, time.time() - 200, time.time() + 400)

import xml.etree.ElementTree as ET
import urllib

def get_station(id, name):
    url = "http://www.labs.skanetrafiken.se/v2.2/stationresults.asp?selPointFrKey=%d" % id

    response = urllib.urlopen(url)
    ret = response.read()

    tree = ET.XML(ret)

    lines = []

    ns = "http://www.etis.fskab.se/v1.0/ETISws"

    for line in tree.findall('.//{%s}Lines//{%s}Line' % (ns, ns)):
        mline = {}
        mline['name'] = line.find('.//{%s}Name' % ns).text
        mline['time'] = line.find('.//{%s}JourneyDateTime' % ns).text
        mline['type'] = line.find('.//{%s}LineTypeName' % ns).text
        mline['towards'] = line.find('.//{%s}Towards' % ns).text
        if mline['name'] == name:
            lines.append(mline)
    return lines


turning = get_station(80032, '2')
#lindangen = get_station(80600, '2')

turning = [tur for tur in turning if tur['towards'] == u'V\xe4stra Hamnen']
#print lindangen
#print "*******************************************"
#print turning
#print len(lindangen)
#print len(turning)

deadtime = time.time() + 34 * 60

print time.mktime(time.strptime("2010-09-04T21:48:00", "%Y-%m-%dT%H:%M:%S"))

#json = tornado.escape.json_encode(lines)
        
