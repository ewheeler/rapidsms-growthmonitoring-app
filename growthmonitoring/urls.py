#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8


from django.conf.urls.defaults import *

import views as v


urlpatterns = patterns('',
    
    # mini dashboard for this app
    url(r'^growthmonitoring/?$',
        v.index),

    url(r'^growthmonitoring/csv/surveyentries?$', 
        v.csv_entries),

    url(r'^growthmonitoring/csv/assessments?$',
        v.csv_assessments),
 
)
