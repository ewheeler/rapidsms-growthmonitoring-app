#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4


from django.conf.urls.defaults import *
from apps.docmanager.models import *

import views as v


urlpatterns = patterns('',
    
    # mini dashboard for this app
    url(r'^childhealth/?$',
        v.index),

    url(r'^childhealth/csv/surveyentries?$', 
        v.csv_entries),

    url(r'^childhealth/(?P<breadcrumbs>.*)\/?(?P<view>LocationType|Location)$',
        v.select_left),
    
    url(r'^childhealth/(?P<breadcrumbs>.*)\/?(?P<view>Children|HealthWorker|Report)$',
        v.select),
    
    url(r'^childhealth/(?P<breadcrumbs>.*)\/?date$',
        v.datefilter),
    
    url(r'^childhealth/(?P<breadcrumbs>.*)\/?graph$',
        v.graphfilter),

    url(r'^childhealth/(?P<id>\d+)/download$',
        v.download_file,
        name='download-file'),

   url(r'^childhealth/(?P<header>.*)/(?P<data>.*)/xls$',
        v.download_excel,
        name='download-xls'),
 
)
