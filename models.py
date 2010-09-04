from django.db import models
from django.db.models import Avg, Max, Min, Count

class Line(models.Model):
    name = models.CharField()

    def __unicode__(self):
        return "%s" % self.name
    class Meta:
        db_table = 'lines'
        app_label = "kollektivt"


class Station(models.Model):
    name = models.CharField()
    lon = models.FloatField()
    lat = models.FloatField()
    line = models.ForeignKey(Line)

    def __unicode__(self):
        return "%s (%s)" % (self.name, self.line)
    class Meta:
        db_table = 'stations'
        app_label = "kollektivt"
