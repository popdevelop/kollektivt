# -*- coding: utf-8 -*-
import re
import mechanize
from BeautifulSoup import BeautifulSoup
import cookielib
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
import populate

# Browser
br = mechanize.Browser()

# Cookie Jar
cj = cookielib.LWPCookieJar()
br.set_cookiejar(cj)

# Browser options
br.set_handle_equiv(True)
br.set_handle_redirect(True)
br.set_handle_referer(True)
br.set_handle_robots(False)

# Follows refresh 0 but not hangs on refresh > 0
br.set_handle_refresh(mechanize._http.HTTPRefreshProcessor(), max_time=1)

# Want debugging messages?
#br.set_debug_http(True)
#br.set_debug_redirects(True)
#br.set_debug_responses(True)

include = ["4"]
exclude = [] # Line 3 messes things up

def fetch_lines(station):
    br.open("http://www.reseplaneraren.skanetrafiken.se/querystation.aspx")

    br.select_form(nr=0)
    br["inpSingleStation"] = station
    br["selDirectionSingleStation"] = ["0"]
    br["inpTimeSingleStation"] = "15:20"
    br["inpDateSingleStation"] = "2010-12-15"
    br["trafficmask"] = ["1", "2", "4", "8"]
    br.submit()

    br.select_form(nr=0)
    br["selDirectionSingleStation"] = ["0"]
    br["inpTimeSingleStation"] = "15:20"
    br["inpDateSingleStation"] = "2010-12-15"
    br["trafficmask"] = ["1", "2", "4", "8"]
    br.submit()

    soup = BeautifulSoup(br.response().get_data())
    for s in soup.findAll(href=re.compile("^javascript:queryLine")):
        res = re.findall(r"queryLine\(\'([0-9]*)\'\)\".*\">([0-9]*)", str(s))
        if not res:
            continue # This is not a number, could be "Öresundståg"
        key, line_id = res[0]
        if line_id in exclude or line_id not in include:
            continue
        print "=========================="
        print "Fetching line %s" % line_id
        print "=========================="
        br.select_form(nr=0)
        br.form.action = "http://www.reseplaneraren.skanetrafiken.se/lineresults.aspx?key=%s" % key
        br.submit()
        soup = BeautifulSoup(br.response().get_data())
        stations = []
        for s in soup.findAll("td", {"class": "details-col-3"}):
            stations.append(s.a.string)
        populate.grab_line(line_id, stations)
        exclude.append(line_id)

fetch_lines("Malmö Gustav Adolfs Torg")
fetch_lines("Malmö C")
