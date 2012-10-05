#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

from tastypie.resources import ModelResource
from .models import Survey
from .models import SurveyEntry
from .models import Assessment


class SurveyResource(ModelResource):
    class Meta:
        queryset = Survey.objects.all()
        resource_name = 'survey'

class EntryResource(ModelResource):
    class Meta:
        queryset = SurveyEntry.objects.all()
        resource_name = 'entry'

class AssessmentResource(ModelResource):
    class Meta:
        queryset = Assessment.objects.all()
        resource_name = 'assessment'
