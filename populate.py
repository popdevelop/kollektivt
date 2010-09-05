# -*- coding: utf-8 -*-

import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
from models import Line
from models import Station
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
    # Query 1
    nbr_stations = line.station_set.all().count()
    key_from = line.station_set.all()[0].key
    key_to = line.station_set.all()[nbr_stations-1].key

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
    line.duration = duration
    line.save()

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
        Coordinate.objects.create(line=line, lat=lat, lon=lon)

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
    line.forward = grab_direction(line, 0)
    line.reverse = grab_direction(line, line.station_set.all().count()-1)
    print line.forward
    print line.reverse
    line.save()

line = Line.objects.create(name="1")
grab_station(line, "Kristineberg Syd")
grab_station(line, "Käglinge Tingdammen")
grab_station(line, "Käglinge Hans Winbergs väg")
grab_station(line, "Oxie Fajansvägen")
grab_station(line, "Oxie Oxievångsskolan")
grab_station(line, "Oxie Centrum")
grab_station(line, "Oxie Flamtegelvägen")
grab_station(line, "Oxie Oshögavången")
grab_station(line, "Oxie Hanehögaparken")
grab_station(line, "Oxie Vårdhemmet")
grab_station(line, "Oxie Pilevallsvägen")
grab_station(line, "Oxie Johan Möllares väg")
grab_station(line, "Malmö Elisedals industriområde")
grab_station(line, "Malmö Jägershill")
grab_station(line, "Malmö Jägersro")
grab_station(line, "Malmö Ögårdsparken")
grab_station(line, "Malmö Cypressvägen")
grab_station(line, "Malmö Kastanjeplatsen")
grab_station(line, "Malmö Poppelgatan")
grab_station(line, "Malmö Persborgs station")
grab_station(line, "Malmö Sofielund")
grab_station(line, "Malmö Södervärn")
grab_station(line, "Malmö Smedjegatan")
grab_station(line, "Malmö Möllevångsgatan")
grab_station(line, "Malmö Triangeln")
grab_station(line, "Malmö Davidshall")
grab_station(line, "Malmö Gustav Adolfs torg")
grab_station(line, "Malmö Stadsbiblioteket")
grab_station(line, "Malmö Aq-va-kul")
grab_station(line, "Malmö Kronprinsen")
grab_station(line, "Malmö Fågelbacken")
grab_station(line, "Malmö Dammfri")
grab_station(line, "Malmö Rönneholm")
grab_station(line, "Malmö Major Nilssonsgatan")
grab_station(line, "Malmö Mellanheden")
grab_station(line, "Malmö Vilebovägen")
grab_station(line, "Malmö Bellevue Park")
grab_station(line, "Malmö Ärtholmsvägen")
grab_station(line, "Malmö Rudbecksgatan")
grab_station(line, "Malmö Bågängsvägen")
grab_station(line, "Malmö Grönbetet")
grab_station(line, "Malmö Broddastigen")
grab_station(line, "Malmö Elinelund")
grab_route(line)
grab_directions(line)
#line = Line.objects.get(name="4")
#raise

line = Line.objects.create(name="2")
grab_station(line, "Malmö Lindängen")
grab_station(line, "Malmö Almviksgången")
grab_station(line, "Malmö Högaholm")
grab_station(line, "Malmö Kungsörnsgatan")
grab_station(line, "Malmö Tornfalksgatan")
grab_station(line, "Malmö Söderkulla")
grab_station(line, "Malmö Helenetorpsgången")
grab_station(line, "Malmö Eriksfält")
grab_station(line, "Malmö Vandrarhemmet")
grab_station(line, "Malmö Mobilia")
grab_station(line, "Malmö Dalaplan")
grab_station(line, "Malmö Södervärn")
grab_station(line, "Malmö Smedjegatan")
grab_station(line, "Malmö Möllevångsgatan")
grab_station(line, "Malmö Triangeln")
grab_station(line, "Malmö Davidshall")
grab_station(line, "Malmö Gustav")
grab_station(line, "Malmö Djäknegatan")
grab_station(line, "Malmö C")
grab_station(line, "Malmö Anna")
grab_station(line, "Malmö Orkanen")
grab_station(line, "Malmö Dockan")
grab_station(line, "Malmö Kockums")
grab_station(line, "Malmö Propellergatan")
grab_station(line, "Malmö Turning")
grab_station(line, "Malmö Scaniabadet")
grab_route(line)
grab_directions(line)

#line = Line.objects.create(name="3")
#grab_station(line, "Malmö Värnhem")
#grab_station(line, "Malmö Slussen")
#grab_station(line, "Malmö Schougens bro")
#grab_station(line, "Malmö Drottningtorget")
#grab_station(line, "Malmö Caroli city")
#grab_station(line, "Malmö C")
#grab_station(line, "Malmö Anna Lindhs plats")
#grab_station(line, "Malmö Orkanen")
#grab_station(line, "Malmö Dockan")
#grab_station(line, "Malmö Kockums")
#grab_station(line, "Malmö Propellergatan")
#grab_station(line, "Malmö Kockum Fritid")
#grab_station(line, "Malmö Tekniska museet")
#grab_station(line, "Malmö Ribershus")
#grab_station(line, "Malmö Sergels väg")
#grab_station(line, "Malmö Fridhemstorget")
#grab_station(line, "Malmö Erikslust")
#grab_station(line, "Malmö Torupsgatan")
#grab_station(line, "Malmö Mellanheden")
#grab_station(line, "Malmö Solbacken")
#grab_station(line, "Malmö Lorensborg")
#grab_station(line, "Malmö Stadion")
#grab_station(line, "Malmö Anneberg")
#grab_station(line, "Malmö UMAS Södra")
#grab_station(line, "Malmö Dalaplan")
#grab_station(line, "Malmö Södervärn")
#grab_station(line, "Malmö Södervärnsplan")
#grab_station(line, "Malmö Falsterboplan")
#grab_station(line, "Malmö Nobeltorget")
#grab_station(line, "Malmö Spånehusvägen")
#grab_station(line, "Malmö Sorgenfri")
#grab_station(line, "Malmö Celsiusgården")
#grab_station(line, "Malmö Ellstorp")
#grab_route(line)

line = Line.objects.create(name="4")
grab_station(line, "Klagshamn")
grab_station(line, "Klagshamn Nygårdsvägen")
grab_station(line, "Klagshamn Syster Ellens stig")
grab_station(line, "Klagshamn Glada hörnan")
grab_station(line, "Klagshamn Möllevägen")
grab_station(line, "Bunkeflostrand Strandhem")
grab_station(line, "Bunkeflostrand Naffentorpsvägen")
grab_station(line, "Bunkeflostrand")
grab_station(line, "Bunkeflostrand Vingen")
grab_station(line, "Bunkeflostrand Ängslätt")
grab_station(line, "Bunkeflostrand Norra vägen")
grab_station(line, "Bunkeflostrand Ängsdalsvägen")
grab_station(line, "Bunkeflostrand Bunkeflovägen")
grab_station(line, "Bunkeflostrand Betalstationen")
grab_station(line, "Malmö Strandåsvägen")
grab_station(line, "Malmö Sibbarpsvägen")
grab_station(line, "Malmö Götgatan")
grab_station(line, "Malmö Hyllie kyrkoväg")
grab_station(line, "Malmö Limhamn Centrum")
grab_station(line, "Malmö Linnéskolan")
grab_station(line, "Malmö Västanväg")
grab_station(line, "Malmö Rosenvång")
grab_station(line, "Malmö Bellevue")
grab_station(line, "Malmö Västervång")
grab_station(line, "Malmö Erikslust")
grab_station(line, "Malmö Fridhemstorget")
grab_station(line, "Malmö Skvadronsgatan")
grab_station(line, "Malmö Kronprinsen")
grab_station(line, "Malmö Aq-va-kul")
grab_station(line, "Malmö Stadsbiblioteket")
grab_station(line, "Malmö Gustav Adolfs torg")
grab_station(line, "Malmö Djäknegatan")
grab_station(line, "Malmö C")
grab_route(line)
grab_directions(line)

line = Line.objects.create(name="5")
grab_station(line, "Bunkeflostrand")
grab_station(line, "Malmö Skogsmätaregatan")
grab_station(line, "Malmö Mary Hemmings gata")
grab_station(line, "Bunkeflostrand Gottorp")
grab_station(line, "Bunkeflostrand Annestad")
grab_station(line, "Malmö Ollebo")
grab_station(line, "Malmö Bunkeflo by")
grab_station(line, "Malmö Kroksbäck")
grab_station(line, "Malmö Mellanbäck")
grab_station(line, "Malmö Kroksbäcksparken")
grab_station(line, "Malmö Bellevuegården")
grab_station(line, "Malmö Bellevueallén")
grab_station(line, "Malmö Hålsjögatan")
grab_station(line, "Malmö Hallingsgatan")
grab_station(line, "Malmö Lorensborg")
grab_station(line, "Malmö Dammfri")
grab_station(line, "Malmö Själlandstorget")
grab_station(line, "Malmö Carl Gustafs väg")
grab_station(line, "Malmö Teatern")
grab_station(line, "Malmö Triangeln")
grab_station(line, "Malmö Davidshall")
grab_station(line, "Malmö Gustav Adolfs torg")
grab_station(line, "Malmö C")
grab_station(line, "Malmö Djäknegatan")
grab_station(line, "Malmö Studentgatan")
grab_station(line, "Malmö Konserthuset")
grab_station(line, "Malmö Folkets park")
grab_station(line, "Malmö Nobeltorget")
grab_station(line, "Malmö Vitemöllegången")
grab_station(line, "Malmö Annelund")
grab_station(line, "Malmö Emilstorp")
grab_station(line, "Malmö Rosengård")
grab_station(line, "Malmö Rosengård Centrum")
grab_station(line, "Malmö Ramels väg")
grab_station(line, "Malmö Västra Skrävlinge")
grab_station(line, "Malmö Buketten")
grab_station(line, "Malmö Stenkällan")
grab_station(line, "Malmö Högatorpsvägen")
grab_station(line, "Malmö Stenkällevägen")
grab_station(line, "Malmö Husiegård")
grab_station(line, "Malmö Toftängen")
grab_station(line, "Malmö Husie kyrkoväg")
grab_station(line, "Malmö Borgnäs")
grab_station(line, "Malmö Tillysborgsvägen")
grab_station(line, "Malmö Vårbo")
grab_station(line, "Malmö Kvarnby")
grab_route(line)
grab_directions(line)

line = Line.objects.create(name="6")
grab_station(line, "Malmö Holma")
grab_station(line, "Malmö Snödroppsgatan")
grab_station(line, "Malmö Fosiedal")
grab_station(line, "Malmö Konsultgatan")
grab_station(line, "Malmö Gröndal")
grab_station(line, "Malmö Södertorp")
grab_station(line, "Malmö Borgmästaregården")
grab_station(line, "Malmö UMAS Södra")
grab_station(line, "Malmö Dalaplan")
grab_station(line, "Malmö Södervärn")
grab_station(line, "Malmö Smedjegatan")
grab_station(line, "Malmö Möllevångsgatan")
grab_station(line, "Malmö Triangeln")
grab_station(line, "Malmö Davidshall")
grab_station(line, "Malmö Gustav Adolfs torg")
grab_station(line, "Malmö Studentgatan")
grab_station(line, "Malmö Konserthuset")
grab_station(line, "Malmö Disponentgatan")
grab_station(line, "Malmö S:t Pauli kyrka")
grab_station(line, "Malmö Celsiusgatan")
grab_station(line, "Malmö Värnhem")
grab_station(line, "Malmö Ellstorp")
grab_station(line, "Malmö Katrinelund")
grab_station(line, "Malmö Katarina kyrka")
grab_station(line, "Malmö Håkanstorp")
grab_station(line, "Malmö Kyrkogården")
grab_station(line, "Malmö Ulricedal")
grab_station(line, "Malmö Dalvik")
grab_station(line, "Malmö Videdal")
grab_station(line, "Malmö Hallstorpsparken")
grab_station(line, "Malmö Granbacken")
grab_station(line, "Malmö Risebergaparken")
grab_station(line, "Malmö Långhällagatan")
grab_station(line, "Malmö Åkvagnsgatan")
grab_station(line, "Malmö Ventilgatan")
grab_station(line, "Malmö Toftanäs")
grab_route(line)
grab_directions(line)

line = Line.objects.create(name="7")
grab_station(line, "Stora Bernstorp")
grab_station(line, "Bernstorp Santessons väg")
grab_station(line, "Malmö Kontorsvägen")
grab_station(line, "Malmö Valdemarsro")
grab_station(line, "Malmö Blåhakevägen")
grab_station(line, "Malmö Vattenverket")
grab_station(line, "Malmö Segemöllegatan")
grab_station(line, "Malmö Segevångsbadet")
grab_station(line, "Malmö Segevång")
grab_station(line, "Malmö Kronetorpsgatan")
grab_station(line, "Malmö Rostorp")
grab_station(line, "Malmö Östra Fäladen")
grab_station(line, "Malmö Beijers park")
grab_station(line, "Malmö Kirsebergs kyrka")
grab_station(line, "Malmö Kirsebergs torg")
grab_station(line, "Malmö Östervärn")
grab_station(line, "Malmö Värnhem")
grab_station(line, "Malmö Slussen")
grab_station(line, "Malmö Schougens bro")
grab_station(line, "Malmö Drottningtorget")
grab_station(line, "Malmö Caroli city")
grab_station(line, "Malmö C")
grab_station(line, "Malmö Gustav Adolfs torg")
grab_station(line, "Malmö Davidshall")
grab_station(line, "Malmö Triangeln")
grab_station(line, "Malmö Möllevångsgatan")
grab_station(line, "Malmö Smedjegatan")
grab_station(line, "Malmö Södervärn")
grab_station(line, "Malmö Dalaplan")
grab_station(line, "Malmö Mobilia")
grab_station(line, "Malmö Blekingsborg")
grab_station(line, "Malmö Per Albins hem")
grab_station(line, "Malmö Velandergatan")
grab_station(line, "Malmö Bergdala")
grab_station(line, "Malmö Lindeborgsgatan")
grab_station(line, "Malmö Lindeborg Centrum")
grab_station(line, "Malmö Fosieborg")
grab_station(line, "Malmö Aktrisgatan")
grab_station(line, "Malmö Stolpalösa")
grab_station(line, "Malmö Svågertorpsparken")
grab_station(line, "Malmö Syd Svågertorp")
grab_route(line)
grab_directions(line)

line = Line.objects.create(name="8")
grab_station(line, "Malmö Kastanjegården")
grab_station(line, "Malmö Gånglåtsvägen")
grab_station(line, "Malmö Lindängsstigen")
grab_station(line, "Malmö Fosie kyrka")
grab_station(line, "Malmö Hermodsdal")
grab_station(line, "Malmö Professorsgatan")
grab_station(line, "Malmö Nydala")
grab_station(line, "Malmö Nydalatorget")
grab_station(line, "Malmö Eriksfält")
grab_station(line, "Malmö Heleneholmsskolan")
grab_station(line, "Malmö Sevedsgården")
grab_station(line, "Malmö Dalslandsgatan")
grab_station(line, "Malmö Dalaplan")
grab_station(line, "Malmö Södervärn")
grab_station(line, "Malmö Smedjegatan")
grab_station(line, "Malmö Möllevångsgatan")
grab_station(line, "Malmö Triangeln")
grab_station(line, "Malmö Davidshall")
grab_station(line, "Malmö Gustav Adolfs torg")
grab_station(line, "Malmö Djäknegatan")
grab_station(line, "Malmö C")
grab_route(line)
grab_directions(line)

print Line.objects.all()
print Station.objects.all()
