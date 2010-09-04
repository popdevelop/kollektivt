# -*- coding: utf-8 -*-
import urllib
import re
import xml.etree.ElementTree as ET
import sys

for i,arg in enumerate(sys.argv):
    print i,arg

params = urllib.urlencode({'inpPointFr':sys.argv[1],'inpPointTo':sys.argv[2]})

url = "http://www.labs.skanetrafiken.se/v2.2/querypage.asp?%s"

print "Request URL:\n", url % params

f = urllib.urlopen(url % params)
data = f.read()

tree = re.sub(r"&lt;", r"<", re.sub(r"&gt;", r">", data)) 
print "Response:\n", tree

xmltree = ET.XML(tree)

ns = "http://www.etis.fskab.se/v1.0/ETISws"

coord = xmltree.find('.//{%s}StartPoints' % ns)[0]
print "X=" + coord.find('.//{%s}Name' % ns).text
print "X=" + coord.find('.//{%s}X' % ns).text
print "Y=" + coord.find('.//{%s}Y' % ns).text

coord = xmltree.find('.//{%s}EndPoints' % ns)[0]
print "X=" + coord.find('.//{%s}Name' % ns).text
print "X=" + coord.find('.//{%s}X' % ns).text
print "Y=" + coord.find('.//{%s}Y' % ns).text
