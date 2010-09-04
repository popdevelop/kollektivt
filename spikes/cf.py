import urllib
import re
import xml.etree.ElementTree as ET
import sys

if len(sys.argv) != 2: print "One argument needed, add cf number"

params = urllib.urlencode({'cf':sys.argv[1], 'id':"1"})

url = "http://www.labs.skanetrafiken.se/v2.2/journeypath.asp?%s"

print "Request url:\n", url % params

f = urllib.urlopen(url % params)
data = f.read()

tree = re.sub(r"&lt;", r"<", re.sub(r"&gt;", r">", data)) 
print "Response\n", tree
xmltree = ET.XML(tree)

ns = "http://www.etis.fskab.se/v1.0/ETISws"

for coord in xmltree.find('.//{%s}Coords' % ns):
     print "X=" + coord.find('.//{%s}X' % ns).text
     print "Y=" + coord.find('.//{%s}Y' % ns).text
#     print util.RT90_to_WGS84(X, Y)
