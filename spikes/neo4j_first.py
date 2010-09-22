import sys, random, csv
from time import sleep
from random import randint
import neo4j
class Stations(neo4j.Traversal):
    types = [
        neo4j.Outgoing.after
        ]
    order = neo4j.DEPTH_FIRST
    stop = neo4j.STOP_AT_END_OF_GRAPH

    def isReturnable(self, position):
        return (not position.is_start
                and position.last_relationship.type == 'after')


graphdb = neo4j.GraphDatabase("db")
index = graphdb.index("ppl", create=True)
print " Linje 1"
stations = []
with graphdb.transaction:
    for a in range(0, 10):
        print a
        s = graphdb.node(name="station"+str(a), x = str(a), y = str(a*a), line="Linje 1")
        stations.append(s)
        if a != 0:
            stations[a-1].after(stations[a])
            print "added relation between:", a-1, a
            print stations[a].name, stations[a].id

print " Linje 2"
with graphdb.transaction:
    for a in range(10, 30):
        print a
        s = graphdb.node(name="station"+str(a), x = str(a), y = str(a*a), line="Linje 2")
        stations.append(s)
        stations[a-1].after(stations[a])
        print "added relation between:", a-1, a
        print stations[a].name, stations[a].id


print "iterate stations"
for s in Stations(stations[0]):
    print s['name'] + ' with x=' + s['x'] + " y=" + s['y'] + " on line: " + s['line']

graphdb.shutdown()
