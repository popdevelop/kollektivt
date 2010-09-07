from django.db import models
from django.db.models import Avg, Max, Min, Count

class Line(models.Model):
    name = models.CharField()

    def __unicode__(self):
        return "%s" % self.name
    class Meta:
        db_table = 'lines'
        app_label = "kollektivt"


class Route(models.Model):
    towards = models.CharField()
    line = models.ForeignKey(Line)
    # TODO: Remove when we have accurate times for each segment
    duration = models.IntegerField()

    def __unicode__(self):
        return "%s, %s" % (self.line, self.towards)
    class Meta:
        db_table = 'routes'
        app_label = "kollektivt"


class Station(models.Model):
    key = models.CharField()
    name = models.CharField()
    lon = models.FloatField()
    lat = models.FloatField()
    line = models.ForeignKey(Line)
    arrival = models.IntegerField()
    departure = models.IntegerField()

    def __unicode__(self):
        return "%s (%s)" % (self.name, self.key)
    class Meta:
        db_table = 'stations'
        app_label = "kollektivt"


class Coordinate(models.Model):
    lon = models.FloatField()
    lat = models.FloatField()
    route = models.ForeignKey(Route)

    def __unicode__(self):
        return "(%.5f, %.5f" % (self.lat, self.lon)
    class Meta:
        db_table = 'coordinates'
        app_label = "kollektivt"
