#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

from datetime import date, datetime

from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.db.models import F

import rapidsms
from rapidsms.message import Message
from logger.models import * 
from rapidsms.connection import Connection
from rapidsms.parsers.keyworder import * 
from  models import * 
import messages
import time

class App(rapidsms.app.App):

    # lets use the Keyworder parser!
    kw = Keyworder()

    def parse(self, message):
        self.handled = False 

    def respond(message,log={}):
        key = "OK"
        if "ERROR" in log: key = "ERROR"
        
        message.respond(log[key])

    def handle(self, message):
        # log message
        try:
            if hasattr(self, "kw"):
                try:
                    # attempt to match tokens in this message
                    # using the keyworder parser
                    func, captures = self.kw.match(self, message.text.lower())
                    func(self, message, *captures)
                    # short-circuit handler calls because 
                    # we are responding to this message
                    return self.handled 
                except Exception, e:
                    # TODO only except NoneType error
                    # nothing was found, use default handler
                    self.incoming_entry(message)
                    return self.handled 
            else:
                self.debug("App does not instantiate Keyworder as 'kw'")
        except Exception, e:
	    # TODO maybe don't log here bc any message not meant
	    # for this app will log this error
	    #
            # self.error(e) 
	    pass
   

    def __get_reporter(self,message,contact=""): #THIS SHOULD BE IN REPORTER CLASS
        conn = PersistantConnection.from_message(message)
        if contact != "":
                conn.identity = contact
                conn.save
        else:
            contact = "%d" % time.mktime(datetime.datetime.now())
        if conn.reporter is null: 
            reporter = Reporter(alias=contact,last_name  = contact)
            reporter.save()
        conn.reporter = reporter
        conn.save()
        return conn.reporter



    def __find_patient(self, cluster, household, code):
        try:
            params = {}
            params["person__code"] = "\"%s\"" % code
            params["person__location"] = "\"%s\"" %  cluster
            params["person__location"] = "\"%s\"" %  household
            cp = ChildPatient.objects.get(**params)
            #cp.ts = datetime.datetime.now()
            return {"PATIENT:":cp}
        except:
            return {"ERROR": "NO RECORD FOR child %s in household  %s in cluster %s" % (child,gmc)}
    
    def __find_worker(self, gmc,id,order="ts"):
        try:
            params = {}
            params["person__short_id"] = "\"%s\"" % id 
            params["person__location"] = "\"%s\"" %  gmc 
            hw = HealthWorker.objects.filter(**params).orderby("\"%s\"" % order)[0]
            hw.ts = datetime.datetime.now()
            hw.message_count  = hw.message_count+1
            return {"WORKER:":hw}
        except:
            return {"ERROR": "NO RECORD FOR HSA %s at gmc %s" % (child,gmc)}
        
        
    # Report 9 from outer space
    @kw("help (.+?)")
    def help(self, message, more=None):
        respond(message,{"OK":SMS_RESPONSE["HELP"]})


    @kw("report (.*?) (.*?) (.*?) (.*?) (.*?) (.*?) (.*?) (.*?)")  #we dont need gmc
    def report(self, message, gmc, hsa, child, wt, ht, muac, oedema, diarrhea):
        resp = {}
        try:
            p = self.__find_patient(gmc,child)
            w = self.__find_worker(gmc,hsa)

            hw.message_count  = hw.message_count+1
            ind = Indicator(health_worker=w["WORKER"], child_patient=p["PATIENT"], height=ht, weight=wt, muac=muac,oedema=oedema,diarrea=diarrea)
            ind.calcStatus()
            resp = ind.verify()

            if ("ERROR" in response):
                hw.errors = hw.errors + 1
                hw.save()
            else:
                try:
                    ind.save()
                    cp.save()
                except Exception,save_err:
                    resp ={"ERROR": save_err}
                    hw.errors = hw.errors + 1
                    hw.save()

            resp["OK"] = "Thank you. You reported height=%s weight=%s muac=%s oedema=%s diarrhea=% : CHILD STATUS = %s" %(ind.height,ind.weight,ind.muac,ind.oedema,ind.diarrea, cp.status)
        except Exception,e:
            resp["ERROR"] = "There was an error with your report - please check your measurements"

        respond(message, resp) 
        
    
    @kw("cancel (.*?) (.*?)")
    def cancel(self, message, gmc,child):
        resp = {}
        try: 
        
            w = self.__find_child(gmc,child,"ts")
            ind = Indicator.objects.filter(child_patient=w).orderby("ts")[0]
            ind.delete()
            resp["OK"] = "CANCELED report for child %s at gmc %s" % (child,gmc)
        except Exception,e:
            resp["ERROR"] = "UNABLE TO CANCEL REPORT for child %s at gmc %" % (child, gmc)
        
        respond(message,resp) 
    

    @kw("register (.*?) (.*?)\?(.*?)\?(.*?)")
    def register_healthworker(self, message, gmc, hsa,oldgmc="",oldhsa=""):
        resp = {}
        try:
            reporter = self.__get_reporter(message)
            if oldgmc !="":
                 person = person.objects.filter(location=oldgmc,short_id=oldhsa)[0]
                 person.short_id  =hsa
                 person.location = gmc
            else:   
                person = Person(reporter=reporter, location=gmc, short_id=hsa)
            person.save()
            hw = HealthWorker(person=person)
            hw.save()
            resp["OK"] = "ADDED HSA %s for %s" % (short_id, location)
        except:
            resp["ERROR"] = "UNABLE TO ADD  %s for %s" % (short_id, location)
        respond(message,resp) 
