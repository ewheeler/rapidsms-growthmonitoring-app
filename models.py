#!/usr/bin/env pytho]
# vim: ai ts=4 sts=4 et sw=4

from django.db import models
from django.contrib.auth import models as auth_models
from django.core.exceptions import ObjectDoesNotExist 
from datetime import datetime, date

from locations.models import Location  
from reporters.models import Reporter
from people.models import Person

from messages import *
   
class HealthWorker(Reporter):
    last_updated           = models.DateTimeField(auto_now=True)
    errors                 = models.IntegerField(max_length=5,default=0) 
    message_count          = models.IntegerField(max_length=5,default=0)  # I am going to log this explicitly - not through the Logger


    class Meta:
        verbose_name = "Health Worker"

    def __unicode__(self):
        return "%s" % self.id

class Patient(Person):
    status   = models.CharField(max_length=1000,choices=tuple(CHILD_HEALTH_STATUS),default="",blank=True)
    last_updated           = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return "%s" % (self.id)
    
    class Meta:
        verbose_name = "Patient"
        

class Assesment(models.Model): 

    health_worker       = models.ForeignKey(HealthWorker,null=True)
    patient              = models.ForeignKey(Patient)
    height             = models.DecimalField(max_digits=4,decimal_places=1,null=True) 
    weight             = models.DecimalField(max_digits=4,decimal_places=1,null=True) 
    muac               = models.DecimalField(max_digits=4,decimal_places=2,null=True) 
    oedema             = models.BooleanField(default=False)
    diarrea            = models.BooleanField(default=False)
    quality      = models.IntegerField(max_length=1,default=1)
    date           = models.DateTimeField(auto_now_add=True)
    # I dont want to calc on fly
    mam            = models.BooleanField(default=False)
    sam            = models.BooleanField(default=False)
    stunting       = models.BooleanField(default=False)



    class Meta:
        verbose_name = "Nutrition Assessment"

    def __unicode__(self):
        return "%s" % self.id
     
    #not pretty
    def calc_health_status(self):
        try: 
            s_calc = StuntingTable.objects.filter(gender=self.patient.gender,age=self.patient.age())
            self.stunting = self.height < s_calc.height
            malnurished = WastingTable.objects.get(height=self.height)
            self.sam = self.weight <= malnurished.weight_70 
            self.mam = (self.weight <= malnurished.weight_80) and (not self.sam)
            self.patient.status = CHILD_HEALTH_STATUS[CHILD_HEALTH_STATUS_BOOL[(self.mam,self.sam)]]       
        except:
            return False
    
    def verify(self): 
        resp = {}
        i = Assessment.objects.filter(patient=self.patient).orderby("last_updated")[0]
        if i.height > self.height: return {"ERROR":"last height is %s and this height is %s" % (i.height,self.height)}
        return resp
        
