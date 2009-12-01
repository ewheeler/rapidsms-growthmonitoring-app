#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4
from datetime import datetime, timedelta

from django import template
register = template.Library()
from django.db.models import Avg

from rapidsms.webui.utils import * 

from childhealth.models import *

@register.inclusion_tag("childhealth/partials/stats.html")
@dashboard("top_right", "childhealth/partials/stats.html", "childhealth.can_view")
def childhealth_stats():
    return { "stats": [
        {
            "caption": "Interviewers",
            "value":   HealthWorker.objects.count()
        },
        {
            "caption": "Children",
            "value":   Patient.objects.count()
        },
        {
            "caption": "Total Survey Entries",
            "value":   SurveyEntry.objects.count()
        },
        {
            "caption": "Valid Surveys",
            "value":   Assessment.objects.count()
        },
        {
            "caption": "Suspect Surveys",
            "value":   Assessment.objects.filter(status='S').count()
        }
    ]}

@register.inclusion_tag("childhealth/partials/progress.html")
@dashboard("top_middle", "childhealth/partials/progress.html", "childhealth.can_view")
def childhealth_progress():
    start = datetime.datetime(2009, 11, 20)
    end = datetime.datetime(2009, 12, 20)
    days = []
    for d in range(0, (end - start).days):
        date = start + datetime.timedelta(d)
        
        ass_args = {
            "date__year":  date.year,
            "date__month": date.month,
            "date__day":   date.day
        }
        
        data = {
            "number": d+1,
            "date": date,
            "in_future": date > datetime.datetime.now()
        }
        
        if not data["in_future"]:
            data.update({
                "children": Patient.objects.filter(created_at__year=date.year,\
                    created_at__month=date.month, created_at__day=date.day\
                    ).count(),
                "surveys": SurveyEntry.objects.filter(survey_date__year=date.\
                    year, survey_date__month=date.month, survey_date__day=\
                    date.day).count(),
                "valids": Assessment.objects.filter(**ass_args).count(),
                "goods": Assessment.objects.filter(**ass_args).filter(\
                    status='G').count(),
                "suspects": Assessment.objects.filter(**ass_args).filter(\
                    status='S').count()
            })
        
            data.update({
                "valid_perc":    int((data["valids"]    / data["surveys"])    * 100) if (data["valids"]    > 0) else 0,
                "good_perc":    int((data["goods"]    / data["valids"])    * 100) if (data["goods"]    > 0) else 0,
                "suspect_perc":    int((data["suspects"]    / data["valids"])    * 100) if (data["suspects"]    > 0) else 0,
            })
        days.append(data)
    return {
        "days" : days,
        "total_children" : Patient.objects.all().count(),
        "total_surveys": SurveyEntry.objects.all().count(),
        "total_valids": Assessment.objects.all().count(),
        "total_goods": Assessment.objects.all().filter(status='G').count(),
        "total_suspects": Assessment.objects.all().filter(status='S').count()
    }

@register.inclusion_tag("childhealth/partials/healthworkers.html")
@dashboard("bottom_left", "childhealth/partials/healthworkers.html", "childhealth.can_view")
def childhealth_healthworkers():
    healthworkers_infos = []
    hws = HealthWorker.objects.filter(status="A")
    for hw in hws:
        info = {
            "first_name" : hw.first_name,
            "last_name" : hw.last_name,
            "interviewer_id" : hw.interviewer_id,
            "groups" : [g.title for g in hw.groups.flatten()],
            "last_seen" : hw.last_seen(),
            "num_message_count" : hw.num_messages_sent(),
            "num_message_month" : hw.num_messages_sent("month"),
            "num_message_week" : hw.num_messages_sent("week"),
            "num_message_today" : hw.num_messages_sent("today"),
            "surveys_today" : Assessment.objects.filter(\
                healthworker=hw.pk, date__gte=datetime.datetime.now().date())\
                .count(),
            "goods" : Assessment.objects.filter(status="G",\
                healthworker=hw.pk).count(),
            "suspects" : Assessment.objects.filter(status="S",\
                healthworker=hw.pk).count()
        }
        healthworkers_infos.append(info)

    return { "healthworkers" : healthworkers_infos }
