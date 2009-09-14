#!/usr/bin/env pytho]
# vim: ai ts=4 sts=4 et sw=4

from django.db import models
from django.contrib.auth import models as auth_models
from django.core.exceptions import ObjectDoesNotExist 
from datetime import datetime, date

from apps.locations.models import Location  
from apps.reporters.models import Reporter,PersistantConnection
from apps.person.models import PersonBase

from messages import *
   
class HealthWorker(models.Model):
    person                 = models.ForeignKey(PersonBase)
    ts                     = models.DateTimeField(auto_now_add=True,default=datetime.now())
    errors                 = models.IntegerField(max_length=5,default=0) 
    message_count          = models.IntegerField(max_length=5,default=0)  # I am going to log this explicitly - not through the Logger


    class Meta:
        verbose_name = "Health Worker"

    def __unicode__(self):
        return "%s" % self.id

class ChildPatient(models.Model):
    person                 = models.ForeignKey(PersonBase)
    status   = models.CharField(max_length=1000,choices=tuple(CHILD_HEALTH_STATUS),default="",blank=True)
    ts                     = models.DateTimeField(auto_now_add=True,default=datetime.now())

    def __unicode__(self):
        return "%s" % (self.id)
    
    class Meta:
        verbose_name = "Patient"
        

class Indicator(models.Model): 

    health_worker       = models.ForeignKey(HealthWorker,null=True)
    child_patient      = models.ForeignKey(ChildPatient)
    height             = models.DecimalField(max_digits=4,decimal_places=1,null=True) 
    weight             = models.DecimalField(max_digits=4,decimal_places=1,null=True) 
    muac               = models.DecimalField(max_digits=4,decimal_places=2,null=True) 
    oedema             = models.BooleanField(default=False)
    diarrea            = models.BooleanField(default=False)
    quality      = models.IntegerField(max_length=1,default=1)
    ts           = models.DateTimeField(auto_now_add=True)
    # I dont want to calc on fly
    mam            = models.BooleanField(default=False)
    sam            = models.BooleanField(default=False)
    stunting       = models.BooleanField(default=False)



    class Meta:
        verbose_name = "Indicator"

    def __unicode__(self):
        return "%s" % self.id
     
    #not pretty
    def calc_health_status(self):
        try: 
            s_calc = StuntingTable.objects.filter(gender=self.patient.reporter.gender,age=self.patient.age())
            self.stunting = self.height < s_calc.height
            malnurished = WastingTable.objects.get(height=self.height)
            self.sam = self.weight <= malnurished.weight_70 
            self.mam = (self.weight <= malnurished.weight_80) and (not self.sam)
            self.child_patient.status = CHILD_HEALTH_STATUS[CHILD_HEALTH_STATUS_BOOL[(self.mam,self.sam)]]       
        except:
            return False
    
    def verify(self): 
        resp = {}
        i = Indicators.objects.filter(child_patient=self.child_patient).orderby("ts")[0]
        if i.height > self.height: return {"ERROR":"last height is %s and this height is %s" % (i.height,self.height)}
        return resp
        
