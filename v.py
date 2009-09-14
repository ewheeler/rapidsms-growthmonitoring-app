#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

import datetime
import os,sys

from django.core.servers.basehttp import FileWrapper
from django.views.decorators.http import require_GET, require_POST
from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseServerError
from django.db import IntegrityError
from django.template import RequestContext
from django import forms
from django.core.urlresolvers import reverse


from rapidsms.webui.utils import render_to_response, paginated
from apps.export.utils import excel,download
from apps.nutrition.models import *
from apps.locations.models import *
from apps.docmanager.models import *
from apps.displaymanager.models import *
from models import *

#put in utils class
def divide(n,d): 
    try: 
        return n/d
    except:
        return 0


#header and data are hash->list.  The key is the column, the list are order
def CreateResultSet(req,header,data,exceldata,title,breadcrumbs)
    resultset = {}
    dataset_count = len(data)

    
    object_data = {}
    list_data = [] #list-i-fy excel data
        

    for c in  object_data:
        od = object_data[c]
        h = header[c]
        for i in range(0,len(od))
            resultset["header_col%s_%s"%(c,i)] = h[i]
            resultset["data_col%s_%s"%(c,i)] = paginated(req,od[i],prefix="data_col%s_%s"%(c,i)),
        resultset["column_count%s_%s"] = (c,len(od))

    resultset["column_count"] = len(object_data)
    resultset["excel"] = excel(list_data)
    resultset["title"] = title
    resultset["breadcrumbs"] = breadcrumbs
    return resultset


#SHOULD GO IN NUTRITION VIEW    
def statsoverview(locations):
    now = datetime.datetime.now()
    days = 1000

    #OPTIMIZE
    data = []
    lenl= []
    for l in locations: 
            d_ids = [d.id for d in l.descendants(True)]
            patients = Person.objects.filter(location__in=d_ids,active=True)
            patient_ids = [p.id for p in patients]
            nutritional_data = Nutrition.objects.filter(patient__in=patient_ids,ts__range=(now-datetime.timedelta(days=days),datetime.datetime.now())) #rough
            lenl.append([l,d_ids])
            #this is bogus but it works
            measures = [0,0.0,0.0,0.0,0.0,0.0] 
            for d in nutritional_data:
                measures[0] += 1
                if d.isStunting() : measures[1] += 1
                malnurished = d.isMalnurished()
                if malnurished == "moderate"  : measures[2] += 1
                if malnurished == "severe"  : measures[3] += 1
                if d.oedema : measures[4] += 1
                if d.diarrea : measures[5] += 1
            percent = [l] + [measures[0]] + [ "%1.0f" % ((divide(measures[i],measures[0]))*100,) for i in range(1,len(measures))]
            data.append(percent)
    header = ["last month","#SMS","%mm","%sm","%wasting","%oedema","%diarrea"]
    return (header, data)


def parsedates(date1,date2):
    y = datetime.datetime.now().year
    y1,y2,m1,m2,d1,d2 = y,y,1,1,1,1

    try: 
        y1 = int(date1[0:4])
    except:
        pass
    try:
        y2 = int(date2[0:4])
    except:
        pass

    if len(date1) > 4: m1 = int(date1[4:6])
    if len(date2) > 4: m2 = int(date2[4:6])
    if len(date1) > 6: d1 = int(date1[6:8])
    if len(date2) > 6: d2 = int(date2[6:8])

    dt1 = datetime.datetime(y1,m1,d1)
    dt2 = datetime.datetime(y2,m2,d2)
    return (dt1,dt2)

def parsedatesFromForm(req):
    #cant i use json?
    try:
	    date1 = req.POST["start-date"]
	    date2 = req.POST["end-date"]
	    return parsedates(date1,date2)
    except:
        return (datetime.datetime.now(),datetime.datetime.now())  #better user feedback 

def parsedata(data,header,href=""): 
    retdata = []
    for d in data:
        inner = []
        for h in header:
            try:
                v = getattr(d,h.lower().replace(" ",""))
                if "<" in str(v): v = v() #CHECK IF FUNCTON BUT THIS WILL DO
                
            except :
                v = "" #"%d" % getattr(d,h.lower())
            inner.append(v)
        retdata.append(inner)

        #oops I just realized we need to check if malnutrition and add to report
        try:
                report = d.report()
                if report != "False": 
                    r = [''] * len(inner)
                    r[len(inner)/2] = report
                    retdata.append(r)
                        #wont be different color unless I unescape it - tb
                        
        except:
            pass #that would be a hs
    return retdata

@require_GET
def dashboard(req):
    files = File.objects.all()
    text  = TextBlock.objects.all()
    return render_to_response(req,
        "infsss/index.html", {
            "title":"About the INFSSS RapidSMS Project",
            "files":files,
            "text":text
             })

@require_GET
#add region and type
def data_date_filter(req,date1,date2):
    dt1,dt2= parsedates(date1,date2)
    title = "Data between %s and %s" % (dt1.strftime("%Y-%m-%d"),dt2.strftime("%Y-%m-%d"))
    data = Nutrition.objects.filter(ts__range=(dt1,dt2)) 
    header = Nutrition.header()
    data = parsedata(data,header) 
    return render_to_response(req,
        "infsss/data.html", {
            "header" : header,
            "title": title,
            "data": data })

@require_GET
def bylocation(req,location):
    type_id = LocationType.objects.get(name=location).id
    locations = Location.objects.filter(type=type_id).order_by("name")
    rapidsms_locations =[]
    other_locations = []
    status_location =  [l.location.id for l in LocationStatus.objects.all()] 
    rapidsms_loctions = Location.objects.filter(type=type_id,id__in=status_location).order_by("name")
    other_locations = Location.objects.filter(type=type_id)#.exclude(id__in=status_location).order_by("name")
            
    header,data = statsoverview([l for l in locations])
    #header,data = statsoverview(rapidsms) #replace with  this

    title = "Data on a %s Level"  % location

    locations = Location.objects.filter(type=type_id).order_by("name")
    return render_to_response(req,
        "infsss/locations.html", {
            "rapidsms_locations": paginated(req,rapidsms_locations,prefix="rapidsms"),
            "other_locations": paginated(req,other_locations,prefix="other"),
            "test": paginated(req,test,prefix="test"),
            "title": title,
            "header":header,
            "data": data })


@require_GET
def bylocationid(req,id):

    location = Location.objects.get(id=id)
    location_ids = [l.id for l in location.descendants(True) ]

    #CAN I DO A JOIN?  OH WELL
    patients = Person.objects.filter(active=True,location__in=location_ids)
    patient_ids = [p.id for p in patients]

    header =Nutrition.header()
    data = Nutrition.objects.filter(patient__in=patient_ids).order_by("ts")

    data =parsedata(data,header)
    title = "Data for  %s"  % location.name
    return render_to_response(req,
        "infsss/data.html", {
            "title": title,
            "header":header,
            "data": data })


@require_GET
def people(req,type):
    if type == "Child": #hack because I just realized this was a requirement
        header = Person.childheader()
    else:
        header = Person.header()

    p =Person.objects.filter(type=type,active=True).order_by("lastupdated")
    data = parsedata(p,header,"%s/"%type)
    title = "%s Data" % type
    return render_to_response(req,
        "infsss/data.html", {
            "header":header,
            #"status":type,
            "title":title,
            "data": data }) 

@require_GET
def byhsaid(req,type,id):
    header = Nutrition.header()
    p = Nutrition.objects.filter(patient=id)
    data = parsedata(p,header)
    
    title = "%s Data :: ID #%s" % (type,id)
    return render_to_response(req,
        "infsss/data.html", {
            "header":header,
            #"status":"HSA",
            "title":title,
            "data": data}) 

@require_GET
def bychildid(req,type,id):
    header = Nutrition.header()
    p = Nutrition.objects.filter(reporter=id)
    data = parsedata(p,header)
    
    title = "%s Data :: ID #%s" % (type,id)
    return render_to_response(req,
        "infsss/data.html", {
            "header":header,
            "title":title,
            #"status":"Child",
            "data": data}) 
            

@require_POST
def datefilter(req):
    dt1,dt2,= parsedatesFromForm(req)
    title = "Data between %s and %s" % (dt1.strftime("%Y-%m-%d"),dt2.strftime("%Y-%m-%d"))
    data = Nutrition.objects.filter(ts__range=(dt1,dt2)) 
    header = Nutrition.header()
    data = parsedata(data,header) 
    return render_to_response(req,
        "infsss/data.html",{ 
         "header":header,
         "title":title,
         "data": data}) 

    
@require_GET
def export_xls(req, type):
    header = Nutrition.header()
    data = parsedata(Nutrition.objects.all(),header)
   
    return excel(
        [header] + data)

@require_GET
def download_file(req, id):
    return download(req,id)


            

