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
    HW_STATUS_CHOICES = (
        ('A', 'Active'),
        ('I', 'Inactive'),
    )
    last_updated           = models.DateTimeField(auto_now=True)
    errors                 = models.IntegerField(max_length=5,default=0) 
    message_count          = models.IntegerField(max_length=5,default=0)  # I am going to log this explicitly - not through the Logger
    status                 = models.CharField(max_length=1,choices=HW_STATUS_CHOICES,default='A')
    interviewer_id          = models.PositiveIntegerField(max_length=10, blank=True, null=True)


    class Meta:
        verbose_name = "Health Worker"

    def __unicode__(self):
        return "%s" % (self.full_name())

class Patient(Person):
    status          = models.CharField(max_length=1000,choices=tuple(CHILD_HEALTH_STATUS),default="",blank=True)
    last_updated    = models.DateTimeField(auto_now=True)
    household_id    = models.PositiveIntegerField(max_length=10, blank=True, null=True)
    cluster_id      = models.PositiveIntegerField(max_length=10, blank=True, null=True)
    age_in_months   = models.PositiveIntegerField(max_length=10, blank=True, null=True)

    @property
    def assessments(self):
        # returns patient's GOOD assessments
        return Assessment.objects.filter(patient=self.patient, status='G').order_by('-patient__last_updated')

    def __unicode__(self):
        return "Child %s, Household %s, Cluster %s" % (self.code, self.household_id, self.cluster_id)
    
    class Meta:
        verbose_name = "Patient"
        

class Assessment(models.Model): 
    ASS_STATUS_CHOICES = (
        ('C', 'Cancelled'),
        ('G', 'Good'),
        ('B', 'Bad'),
    )

    # who what where when why
    healthworker       = models.ForeignKey(HealthWorker,null=True)
    patient             = models.ForeignKey(Patient)
    date                = models.DateTimeField(auto_now_add=True)
    status              = models.CharField(max_length=1,choices=ASS_STATUS_CHOICES,default='G')

    # indicators
    height              = models.DecimalField(max_digits=4,decimal_places=1,null=True) 
    weight              = models.DecimalField(max_digits=4,decimal_places=1,null=True) 
    muac                = models.DecimalField(max_digits=5,decimal_places=2,null=True) 
    oedema              = models.BooleanField(default=False)
    diarrea             = models.BooleanField(default=False)

    # expensive calculations 
    mam                 = models.BooleanField(default=False)
    sam                 = models.BooleanField(default=False)
    stunting            = models.BooleanField(default=False)

    # z-scores
    weight4age          = models.DecimalField(max_digits=4,decimal_places=2,null=True,blank=True)
    height4age          = models.DecimalField(max_digits=4,decimal_places=2,null=True,blank=True)
    weight4height       = models.DecimalField(max_digits=4,decimal_places=2,null=True,blank=True)



    class Meta:
        verbose_name = "Nutrition Assessment"

    def __unicode__(self):
        return "%s" % self.id
     
    def analyze(self):
        self.nutritional_status()
        self.zscores()

    #not pretty
    def nutritional_status(self):
        try: 
            s_calc = StuntingTable.objects.filter(gender=self.patient.gender,age=self.patient.age())
            self.stunting = self.height < s_calc.height
            malnurished = WastingTable.objects.get(height=self.height)
            self.sam = self.weight <= malnurished.weight_70 
            self.mam = (self.weight <= malnurished.weight_80) and (not self.sam)
            self.patient.status = CHILD_HEALTH_STATUS[CHILD_HEALTH_STATUS_BOOL[(self.mam,self.sam)]]       
        except:
            return False
    
    def zscores(self):
        pass

    def verify(self): 
        resp = {}
        if self.patient.assessments.count() > 0:
            last_assessment = self.patient.assessments[0]
            if last_assessment.height > self.height: return {"ERROR":"last height is %s and this height is %s" % (last_assessment.height,self.height)}
        return resp
        
    def cancel(self):
        self.status = 'C'
        self.save()
