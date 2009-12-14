#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

from datetime import *
import os,sys,string
import time as t
import csv


from django.core.servers.basehttp import FileWrapper
from django.utils.datastructures import MergeDict 
from django.views.decorators.http import require_GET, require_POST
from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseServerError
from django.db import IntegrityError
from django.template import RequestContext
from django import forms
from django.core.urlresolvers import reverse
from django.db.models import Avg,Max,Min,Count


from rapidsms.webui.utils import render_to_response, paginated
from displaymanager.utils import *
from export.utils import excel#,download
from childhealth.models import *
from pilot.models import *
from locations.models import *
from reporters.models import *
from docmanager.models import *
from displaymanager.models import *
from models import *

from utilities.export import export

def index(req):
    template_name="childhealth/index.html"
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

def csv_assessments(req):
    # Create the HttpResponse object with the appropriate CSV header.
    response = HttpResponse(mimetype='text/csv')
    response['Content-Disposition'] = 'attachment; filename=assessments.csv'

    assessments = ass_dicts_for_display()
    # sort by date, descending
    assessments.sort(lambda x, y: cmp(y['date'], x['date']))

    writer = csv.writer(response)
    # column labels
    writer.writerow(['date', 'interviewer ID', 'cluster ID', 'child ID',\
        'household ID', 'sex', 'date of birth', 'age in months', 'height',\
        'weight', 'oedema', 'muac', 'height for age', 'weight for age',\
        'weight for height', 'survey status'])
    for ass in assessments:
        writer.writerow([ass['date'], ass['interviewer_id'], ass['cluster_id'],\
            ass['child_id'], ass['household_id'], ass['sex'], ass['date_of_birth'],\
            ass['age_in_months'], ass['height'], ass['weight'], ass['oedema'],\
            ass['muac'], ass['height4age'], ass['weight4age'], ass['weight4height'],\
            ass['human_status']])

    return response

def csv_entries(req, format='csv'):
    context = {}
    if req.user.is_authenticated():
        return export(SurveyEntry.objects.all())
    return export(SurveyEntry.objects.all(), ['Survey Date','Interviewer ID','Cluster ID','Child ID','Household ID', 'Sex', 'Date of Birth', 'Age', 'Height', 'Weight', 'Oedema', 'MUAC'])

# TODO can't get any of meredith's view code (below) to work
def to_js_date(dt):
    return 1000 * t.mktime(dt.timetuple())
    
#THIS IS HARD CODED BECAUSE DJANGO AGGREGATION SUCKS BALLS
def stats(filter_params,hd,header,descendants):
    filter_params["health_worker__person__location__in"] = [i.id for i in descendants]
    table = {}
    indicators = Indicator.objects.filter(**filter_params)
    for i in indicators:
      try:
        for h in hd:
            v = evalFunc(i,h)
            try:
                v = int(v)
            except:
                try:
                    v = int(h.func)
                except:
                     if v.strip(" ") == "": v = 0
            
            if h.title not in table: table[h.title] = []
            table[h.title].append(v)
      except Exception,e:
            return {"here":e}
    keys = table.keys() 
    tableresult = dict(zip(keys,[] * len(keys)))
    for t in keys:
        try:
            s = sum(table[t])
            l = len(table[t])
            if s == l:
                r = s
            else:
                r = "%1.0f%%" % (s/(l*.01))
        except Exception,e1:
           r = header
        #tableresult["sum#"] = sum(table["sum#"]) #BOGUS
        tableresult[t] = r
        
    return tableresult

    
def default_date_range():
        default_start = datetime(2007,01,01)
        return (default_start.isoformat()[0:10],(default_start + timedelta(30)).isoformat()[0:10])

#should be a class and not crap
def parse_breadcrumbs(breadcrumbs,view=""):
    bhash = {}
    blist = []    
    #bhash["view"] = view
    skip = False 
    if breadcrumbs == "" : 
            blist = [view]
    else:
        breadcrumbs = breadcrumbs.replace("->","/")       
        breadcrumbs = breadcrumbs.strip(" ").strip("/") 
             
        if "startdate" in breadcrumbs:
                b= breadcrumbs.split("/")                
                breadcrumbs = b[0:b.index("startdate")-2]
                breadcrumbs = "/".join(breadcrumbs)
        
        if "startdate" in view : 
            b =view.split("/")            
            bhash["startdate"] = b[b.index("startdate") -1]            
            bhash["enddate"] = b[b.index("startdate") +1]            
            breadcrumbs = breadcrumbs+"/"+view
            view =breadcrumbs[0:breadcrumbs.index("/startdate")].split("/")[-2]
            if "Location" in breadcrumbs: 
                bb = breadcrumbs.split("/")                
                bhash["Location"] = bb.index("Location")-1            
                view ="Report"            
            skip= True
            blist = b
        
        elif "/" in breadcrumbs: 
            blist = breadcrumbs.split("/")
        else:  
            blist = [breadcrumbs,view]
            
        if not skip:       
            if (len(blist) % 2) > 0: blist.pop() 
            bhash= dict([(blist[i+1],blist[i]) for i in range(0,len(blist)) if (not (i % 2))])

    if "startdate" in bhash: bhash["startdate"] = parse_date(bhash["startdate"])
    if "enddate" in bhash: bhash["enddate"] = parse_date(bhash["enddate"])
    
    try:
        breadlist ="->".join(blist)
    except Exception,e:
        breadlist =e
    kfilter = {}    
    # I need to clean this up and support two kwargs stats and other
    #breadcrumbs should build a dynamic list of kwargs from the flow manager
    if "Location" not in view and "LocationType" in bhash :
        klass = "health_worker"    
        if view == "Children": klass = "child_patient"
        if view == "Indicator":    klass = "indicator__health_worker"
        loctypes =  dict([(l.name,l.id) for l in LocationType.objects.all() ]) #filter does not work?
        ending = "__parent" * (len(loctypes) -loctypes[bhash["LocationType"]]) + "__name"    
        kfilter[klass+"__person__location"+ending] = bhash["Location"]  
            
    if "LocationType" not in view:         
        r = kfilter["ts__range"] = default_date_range()
        if "startdate" in bhash: r = (bhash["startdate"],bhash["enddate"])
        if "Location"in view: 
            bhash.pop("startdate")
            bhash.pop("enddate")            
            bhash["ts__range"] = r
        else:
            kfilter["ts__range"]= r
            bhash = kfilter
    
    return (bhash,breadlist,view)

def parse_date(date):
  try:
    #y = datetime.now().year
    if len(date) == 8:
        return datetime(int(date[0:4]),int(date[4:6]),int[6:8]).isoformat()[0:10]
    elif len(date) >5:
        return datetime(int(date[0:4]),int(date[4:6]),1).isoformat()[0:10]
    else :
        return datetime(int(date[0:4]),1,1).isoformat()[0:10]
    
  except Exception,e:
    return e

def parse_form(req,breadcrumbs):
    breadcrumbs = breadcrumbs.replace("->","/").strip("/")
    date1 = req.POST["start-date"]
    date2 = req.POST["end-date"]
    try:
	    return parse_breadcrumbs(breadcrumbs,date1+"/startdate/"+date2+"/enddate")
    except Exception,e:
        #return {},"",e
        return parse_breadcrumbs(breadcrumbs,e)

#header and data are hash->list.  The key is the column, the list are order
def create_data_hash(req,data={},breadcrumbs="",filter="",view="",kfilter={},measure=""):
    resultset = {}
    resultset["title"] = HeaderDisplay.by_view("INDEX")#[0]
    resultset["navbar"] =HeaderDisplay.by_view("NAVBAR")
    resultset["graphchoice"] =HeaderDisplay.by_view("GRAPHCHOICES")
    resultset["breadcrumbs"] = breadcrumbs

    resultset["view"] =view 
    resultset["filter"] = filter
   
    try:
       datefilter = {} 
       if "ts__range" in kfilter:
             datefilter["ts__range"] = kfilter["ts__range"]
       else:
            datefilter["ts__range"] = default_date_range()
    
       hd = HeaderDisplay.by_view("STATS")
       location = ""
       try: 
             location  = kfilter["Location"]
       except:
        for k in kfilter :
            if "__parent" in k: # hack 
                location = kfilter[k]
        
       if location:
                headers = Location.objects.filter(name=location)#**{"name":kfilter["Location"]})
                loc = location
       else: 
                headers = Location.objects.filter(type__name=kfilter["LocationType"])#{"type":"\""+kfilter["LocationType"]+"\""}
                loc = kfilter["LocationType"]
       locids = []
       locidsadd = locids.append
       for h in headers:
            for h2 in h.descendants(True):
                locidsadd(h2)
       if measure == "": measure = "mam"
        #Location list
       #resultset["test"] = datefilter
       d1,d2 = datefilter["ts__range"]
       date1 = datetime(int(d1[0:4]),int(d1[5:7]),int(d1[8:10]))
       date2 = datetime(int(d2[0:4]),int(d2[5:7]),int(d2[8:10]))
       #resultset["test"] = [(hd,header.name,header.descendants()) for header in headers ]
       stat_data = [stats(datefilter,hd,header.name,header.descendants()) for header in headers ]
       data["stats"] = {"header":[h.title for h in hd],"data":stat_data,"dates":"From %s to %s" % datefilter["ts__range"]}
       ts1 = []
       ts2 = []
       p1 = {}
       p2 = {}
       p3 = {}
       p4 = {}
       p1["health_worker__person__location__in"] = locids
       p2["health_worker__person__location__in"] = locids
       p1[measure] = True 
       p2[measure] = False
       p3[measure] = True 
       p4[measure] = False
       date2 = datetime.now()
       while date1 < date2:
            p1["ts__range"] = (date1.isoformat()[0:10],(date1+timedelta(30)).isoformat()[0:10])
            p2["ts__range"] =  p1["ts__range"]
            p3["ts__range"] =  p1["ts__range"]
            p4["ts__range"] =  p1["ts__range"]

            g1_1 = Indicator.objects.filter(**p1).aggregate(sum=Count("id"))["sum"]
            g1_2 = Indicator.objects.filter(**p2).aggregate(sum=Count("id"))["sum"]
            g2_1 = Indicator.objects.filter(**p3).aggregate(sum=Count("id"))["sum"]
            g2_2 = Indicator.objects.filter(**p4).aggregate(sum=Count("id"))["sum"]

            date1 = date1 + timedelta(30)

            try:
                ts1.append([to_js_date(date1),g1_2/g1_1])
            except Exception,e:
                resultset["test"] = e
                ts1.append([to_js_date(date1),0])

            try:
                ts2.append([to_js_date(date1),g2_2/g2_1])
            except: 
                ts2.append([to_js_date(date1),0])

                 
       #resultset["js_x1"] = {"label":"\"%s %s\"" % (measure,kfilter["LocationType"]),"data": ts1}
       #resultset["js_x2"] = {"label":"\"%s %s\"" % (measure,"National"),"data": ts2}
       resultset["js_x1"] = ts1 
       resultset["js_x2"] = ts2
       resultset["js_l1"] = "%s %s" % (measure.upper(), loc)
       resultset["js_l2"] = "%s %s" % (measure.upper(), "National")
       resultset["mapdata"] = []
    except Exception,e:
        resultset["js_x1"] = []
        resultset["js_x2"] = []
        #resultset["test"] = resultset["test"]+"error %s" % e
    resultset["display_data"] = data
    return resultset


    
@require_GET
def dashboard(req):
    data_hash = create_data_hash(req)
    data_hash["files"]  = File.objects.all()
    data_hash["text"] = TextBlock.objects.all()
    data_hash["breadcrumbs"] = ""
    return render_to_response(req, "childhealth/index.html",data_hash)

def process(req,filter_params,crumbs,view,breadcrumbs,measure=""):     
    data_hash = {}
    #HACK fix in date area
    if "enddate" in view: view = "Report"
                    
    data_hash["left"] = {tuple([l for l in HeaderDisplay.by_view(view)]):dataPaginatev2(req,HeaderDisplay.get_section(view),filter_params)}
    v = HeaderDisplay.get_section(view)
    x = dataPaginatev2(req,v,filter_params)
    
    return create_data_hash(req,data=data_hash,breadcrumbs=crumbs,filter=HeaderDisplay.next_flow("FLOW",view),view=view,kfilter=filter_params,measure=measure)


def process_location(req,filter_params,crumbs,view,breadcrumbs,measure=""):
    params = {}

    cmd = "%s.objects.get(name='%s').id" % (view,filter_params[view])
    try:
        params["id"]= eval(cmd)
    except Exception,e:
        return render_to_response(req, "childhealth/test.html",{"test":"t"})#filter_params})
    #make dynamic -add to layoutmanager
    params["activeids"] = [l.location.id for l in ActiveLocation.objects.all()] #make dynamic
    data_hash = {} 
    
    data_hash["left"] = dict([((l.title,),dataPaginate(req,l,**params)) for l in HeaderDisplay.by_view("LOCATION_SECTIONS")])
    #return {"view":filter_params[view]}
    data_hash = create_data_hash(req,data=data_hash,breadcrumbs=crumbs,filter=HeaderDisplay.next_flow("FLOW",view),view="Location",kfilter=filter_params)  #no hard code
    return data_hash
    #return {"test":"loc"}       


@require_GET
def select_left(req,breadcrumbs,view):
    filter_params, crumbs,view = parse_breadcrumbs(breadcrumbs, view)
    data_hash = process_location(req,filter_params,crumbs,view,breadcrumbs)
    return render_to_response(req, "childhealth/data.html",data_hash)
    
@require_GET
def select(req,breadcrumbs,view):
    filter_params, crumbs,view = parse_breadcrumbs(breadcrumbs, view)
    
    data_hash = process(req,filter_params,crumbs,view,breadcrumbs)
    return render_to_response(req, "childhealth/data.html",data_hash)	

@require_POST
def datefilter(req,breadcrumbs):
    if "Location" not in breadcrumbs and "Report" not in breadcrumbs and "Child" not in breadcrumbs and "Health" not in breadcrumbs: 
        data_hash = create_data_hash(req,data={})
    else:    
        filter_params, crumbs,view = parse_form(req,breadcrumbs)
    
        if "Location" in view : 
            data_hash = process_location(req,filter_params,crumbs,view,breadcrumbs)
        else: 
            data_hash = process(req,filter_params,crumbs,view,breadcrumbs)
    return render_to_response(req, "childhealth/data.html",data_hash)
    
@require_GET
def download_file(req, id):
    return download(req,id)

@require_GET
def download_excel(req, header,data):
    if "delete" in data: return excel([[]])    
    try:
        klass,title,func= header.split(";")
        data =[[h for h in header.split("|")]]+ [[l for l in evalFunc(klass,func)]   ]
    except:
        data =[[h]]+ [[l] for l in eval(data)]   

    return excel(data) 
            

@require_POST
def graphfilter(req,breadcrumbs):
    breadcrumbs = breadcrumbs.replace("->","/").strip("/graphchoice/")
    gmeasure = req.POST["graphchoice"]
    if "Location" not in breadcrumbs and "Report" not in breadcrumbs and "Child" not in breadcrumbs and "Health" not in breadcrumbs: 
        data_hash = create_data_hash(req,data={},measure=gmeasure)
    else:    
        filter_params, crumbs,view = parse_breadcrumbs(breadcrumbs,"")
        if "Location" in view : 
            data_hash = process_location(req,filter_params,crumbs,view,breadcrumbs,measure=gmeasure)
        else: 
            data_hash = process(req,filter_params,crumbs,view,breadcrumbs,measure=gmeasure)
    return render_to_response(req, "childhealth/data.html",data_hash)
    
