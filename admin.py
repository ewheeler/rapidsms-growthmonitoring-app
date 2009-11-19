from django.contrib import admin 
from models import *

class AssessmentInline(admin.TabularInline):
    model = Assessment

class HealthWorkerAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'message_count', 'errors', 'last_seen')
    search_fields = ('first_name', 'last_name', 'alias')
    inlines = [AssessmentInline, ]

class PatientAdmin(admin.ModelAdmin):
    list_display = ('code', 'cluster_id', 'household_id', 'gender', 'date_of_birth', 'age_in_months', 'age_in_months_from_date_of_birth', 'status', 'last_updated')
    ordering = ['cluster_id']
    date_hierarchy = 'last_updated'
    inlines = [AssessmentInline, ]

class AssessmentAdmin(admin.ModelAdmin):
    list_display = ('status', 'healthworker', 'patient', 'date')
    search_fields = ('healthworker', 'patient', 'date', 'status')
    date_hierarchy = 'date'

admin.site.register(HealthWorker, HealthWorkerAdmin)
admin.site.register(Patient, PatientAdmin)
admin.site.register(Assessment, AssessmentAdmin)

