#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

from datetime import *
import os,sys,string
import csv

from django.http import HttpResponse

from rapidsms.webui.utils import render_to_response, paginated
from locations.models import *
from reporters.models import *
from models import *

from utilities.export import export

def index(req):
    template_name="growthmonitoring/index.html"
    surveyentries = SurveyEntry.objects.order_by('survey_date')
    all = []
    [ all.append(entry) for entry in surveyentries]
    # sort by date, descending
    all.sort(lambda x, y: cmp(y.survey_date, x.survey_date))

    assessments = ass_dicts_for_display()
    # sort by date, descending
    assessments.sort(lambda x, y: cmp(y['date'], x['date']))

    context = {}
    context['entries'] = paginated(req, all, per_page=50)
    context['assessments'] = paginated(req, assessments, per_page=50)
    return render_to_response(req, template_name, context )

def instance_to_dict(instance):
    dict = {}
    for field in instance._meta.fields:

        # skip foreign keys. for now... TODO
        if (hasattr(field, "rel")) and (field.rel is not None):# and (depth < max_depth):
                #columns.extend(build_row(field.rel.to, cell, depth+1))
                continue
        value = getattr(instance, field.name)

        # append to dict if its not None, this way the django template
        # will leave a blank space rather than listing 'None'
        if value is not None:
            dict.update({ field.name : value })
    return dict


def ass_dicts_for_display():
    dicts_for_display = []
    asses = Assessment.objects.all().select_related()
    for ass in asses:
        ass_dict = {}
        # add desired fields from related models (we want to display the
        # IDs, ect from foreign fields rather than just the unicode() names
        # or all of the fields from related models)
        # TODO is there a better way to do this? adding fields to the queryset???
        ass_dict.update({'interviewer_id'   : ass.healthworker.interviewer_id})
        ass_dict.update({'child_id'         : ass.patient.code})
        ass_dict.update({'household_id'     : ass.patient.household_id})
        ass_dict.update({'cluster_id'       : ass.patient.cluster_id})
        ass_dict.update({'sex'              : ass.patient.gender})
        ass_dict.update({'date_of_birth'    : ass.patient.date_of_birth})
        ass_dict.update({'age_in_months'    : ass.patient.age_in_months})
        ass_dict.update({'human_status'     : ass.get_status_display()})
        ass_dict.update(**instance_to_dict(ass))
        dicts_for_display.append(ass_dict)
    return dicts_for_display

# TODO DRY
def ass_dicts_for_export():
    dicts_for_export = []
    #asses = Assessment.objects.all().select_related()
    patients = Patient.objects.all()
    asses = []
    for patient in patients:
        if patient.latest_assessment() is not None:
            asses.append(patient.latest_assessment())

    for ass in asses:
        ass_dict = {}
        # add desired fields from related models (we want to display the
        # IDs, ect from foreign fields rather than just the unicode() names
        # or all of the fields from related models)
        # TODO is there a better way to do this? adding fields to the queryset???
        ass_dict.update({'interviewer_id'   : ass.healthworker.interviewer_id})
        ass_dict.update({'child_id'         : ass.patient.code})
        ass_dict.update({'household_id'     : ass.patient.household_id})
        ass_dict.update({'cluster_id'       : ass.patient.cluster_id})
        ass_dict.update({'sex'              : ass.patient.gender})
        ass_dict.update({'date_of_birth'    : ass.patient.date_of_birth})
        ass_dict.update({'age_in_months'    : ass.patient.age_in_months})
        ass_dict.update({'human_status'     : ass.get_status_display()})
        ass_dict.update(**instance_to_dict(ass))
        dicts_for_export.append(ass_dict)
    return dicts_for_export

def csv_assessments(req):
    # Create the HttpResponse object with the appropriate CSV header.
    response = HttpResponse(mimetype='text/csv')
    response['Content-Disposition'] = 'attachment; filename=assessments.csv'

    assessments = ass_dicts_for_export()
    # sort by date, descending
    assessments.sort(lambda x, y: cmp(y['date'], x['date']))

    writer = csv.writer(response)
    # column labels
    writer.writerow(['date', 'interviewer ID', 'cluster ID', 'child ID',\
        'household ID', 'sex', 'date of birth', 'age in months', 'height',\
        'weight', 'oedema', 'muac', 'height for age', 'weight for age',\
        'weight for height', 'survey status'])
    for ass in assessments:
        row = []
        keys = ['date', 'interviewer_id', 'cluster_id', 'child_id',\
            'household_id', 'sex', 'date_of_birth', 'age_in_months',\
            'height', 'weight', 'oedema', 'muac', 'height4age', 'weight4age',\
            'weight4height', 'human_status']
        for key in keys:
            if ass.has_key(key):
                row.append(ass[key])
            else:
                row.append("None")
        writer.writerow(row)

    return response

def csv_entries(req, format='csv'):
    context = {}
    if req.user.is_authenticated():
        return export(SurveyEntry.objects.all())
    return export(SurveyEntry.objects.all(), ['Survey Date','Interviewer ID','Cluster ID','Child ID','Household ID', 'Sex', 'Date of Birth', 'Age', 'Height', 'Weight', 'Oedema', 'MUAC'])

