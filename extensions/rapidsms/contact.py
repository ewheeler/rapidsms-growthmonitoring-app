#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

from django.db import models


class HealthWorker(models.Model):
    HW_STATUS_CHOICES = (
        ('A', 'Active'),
        ('I', 'Inactive'),
    )
    last_updated           = models.DateTimeField(auto_now=True)
    # counter for measurement errors, not poor texting skills
    # incremented only when z-scores indicate unreasonable measurements
    errors                 = models.IntegerField(max_length=5,default=0) 
    status                 = models.CharField(max_length=1,choices=HW_STATUS_CHOICES,default='A')
    interviewer_id          = models.PositiveIntegerField(max_length=10, blank=True, null=True)

    def __unicode__(self):
        return "%s" % (self.name)

    def num_messages_sent(self, when=None):
        time_chunks = {
                'today' : datetime.datetime.now().date(),
                'week' : (datetime.datetime.now()-timedelta(weeks=1)),
                'month' : (datetime.datetime.now()-timedelta(days=30)),
                'year' : (datetime.datetime.now()-timedelta(days=365))}
        if when in time_chunks.keys():
                return self.incoming_messages.filter(\
                            received__gte=time_chunks[when]).count()
        else:
            return self.incoming_messages.all().count()

