#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8


from django.conf.urls.defaults import *

import views as v

from tastypie.api import Api
import api

v1_api = Api(api_name='v1')
v1_api.register(api.EntryResource())
v1_api.register(api.SurveyResource())
v1_api.register(api.AssessmentResource())

urlpatterns = patterns('',
    # mini dashboard for this app
    url(r'^$', v.index, name='growth_index'),
    url(r'^csv/surveyentries/$', v.csv_entries, name='growth_surveyentries'),
    url(r'^csv/assessments/$', v.csv_assessments, name='growth_assessments'),
    url(r'^api/', include(v1_api.urls)),
)
