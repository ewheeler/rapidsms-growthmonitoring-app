#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

from django.contrib import admin 
from models import *

class AssessmentInline(admin.TabularInline):
    model = Assessment

class HealthWorkerAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'interviewer_id', 'errors',\
        'connection', 'last_seen')
    search_fields = ('first_name', 'last_name', 'alias', 'connection')
    inlines = [AssessmentInline, ]

class PatientAdmin(admin.ModelAdmin):
    list_display = ('code', 'cluster_id', 'household_id', 'gender',\
        'date_of_birth', 'age_in_months', 'age_in_months_from_date_of_birth',\
        'status', 'last_updated')
    ordering = ['cluster_id']
    date_hierarchy = 'last_updated'
    inlines = [AssessmentInline, ]

class AssessmentAdmin(admin.ModelAdmin):
    list_display = ('status', 'healthworker', 'patient', 'date')
    search_fields = ('healthworker', 'patient', 'date', 'status')
    date_hierarchy = 'date'

class SurveyEntryAdmin(admin.ModelAdmin):
    list_display = ('healthworker_id', 'household_id', 'child_id', 'cluster_id', 'survey_date')


class SurveyAdmin(admin.ModelAdmin):
    list_display = ('location', 'begin_date', 'end_date')
    seach_fields = ('begin_date', 'end_date', 'location', 'description')

admin.site.register(HealthWorker, HealthWorkerAdmin)
admin.site.register(Patient, PatientAdmin)
admin.site.register(Assessment, AssessmentAdmin)
admin.site.register(SurveyEntry, SurveyEntryAdmin)
admin.site.register(Survey, SurveyAdmin)
