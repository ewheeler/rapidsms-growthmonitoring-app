#!/usr/bin/env pytho]
# vim: ai ts=4 sts=4 et sw=4

from django.db import models
from django.contrib.auth import models as auth_models
from django.core.exceptions import ObjectDoesNotExist 
from datetime import datetime, date

from locations.models import Location  
from reporters.models import Reporter
from people.models import Person

from healthtables.models import StuntingTable, WastingTable

from childhealth.utils import *
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
    PATIENT_STATUS = (
		 ("NA","NA"),
		 ("NAM",""),
                 ("MAM","Moderate Malnutrition"),
                 ("SAM","Severe Malnutrition"),
                 ("W","Wasting"),
                 ("S","Stunting"),)

    status          = models.CharField(max_length=1000,choices=PATIENT_STATUS,default="",blank=True)
    last_updated    = models.DateTimeField(auto_now=True)
    household_id    = models.PositiveIntegerField(max_length=10, blank=True, null=True)
    cluster_id      = models.PositiveIntegerField(max_length=10, blank=True, null=True)
    age_in_months   = models.PositiveIntegerField(max_length=10, blank=True, null=True)

    @property
    def assessments(self):
        # returns patient's GOOD assessments
        return Assessment.objects.filter(patient=self.patient, status='G').order_by('-patient__last_updated')

    def latest_assessment(self):
        return assessments[0]

    @property
    def age_in_months_from_date_of_birth(self):
        return util.sloppy_date_to_age_in_months(self.date_of_birth)

    def __unicode__(self):
        return "Child %s, Household %s, Cluster %s" % (self.code, self.household_id, self.cluster_id)

    def status_from_bools(self, mam, sam, stunting):
        if not mam and not sam and not stunting:
            return "NAM"
        #(False,True):"SAM"
        elif sam and not mam:
            return "SAM"
        #(False,False):"NAM"
        elif mam and not sam:
            return "MAM"
        elif stunting:
            return "S"
        #(True,False):"MAM"
        elif not mam and not sam:
            return "NAM"
        else:
            return "NA"

    class Meta:
        verbose_name = "Patient"
        

class Assessment(models.Model): 
    ASS_STATUS_CHOICES = (
        ('C', 'Cancelled'),
        ('G', 'Good'),
        ('B', 'Baseline'),
        ('S', 'Suspect'),
    )

    # who what where when why
    healthworker        = models.ForeignKey(HealthWorker,null=True)
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
     
    def analyze(self, childgrowth):
        results = {}
        #self.nutritional_status()
        self.zscores(childgrowth)
        results.update({'weight4age' : self.weight4age,\
                        'height4age' : self.height4age,\
                        'weight4height' : self.weight4height})
        return results

    def zscores(self, childgrowth):
        age = self.patient.age_in_months
        gender = self.patient.gender
        self.weight4age = childgrowth.zscore_for_measurement(\
                        "wfa", self.weight, age, gender)
        self.height4age = childgrowth.zscore_for_measurement(\
                        "lhfa", self.height, age, gender)

        # determine whether to use weight-for-length or weight-for-height
        # based on age. TODO accept a parameter indicating whether child
        # was measured standing or recumbent
        if age <= 24:
            self.weight4height = childgrowth.zscore_for_measurement(\
                        "wfl", self.weight, age, gender, self.height)
        elif age > 24:
            self.weight4height = childgrowth.zscore_for_measurement(\
                        "wfh", self.weight, age, gender, self.height)
        else:
            pass
        self.save()

    #not pretty
    def nutritional_status(self):
        #stunts = StuntingTable.objects.all()
        #for stunt in stunts:
            # convert to int to get floor, then to string
            # so django will save as decimal
        #    new_age = str(float(int(stunt.age)))
        #    stunt.age = new_age
        #    stunt.save()
        try: 
            s_calc = StuntingTable.objects.get(gender=self.patient.gender,age=self.patient.age_in_months)
            self.stunting = self.height < s_calc.height
            #print "STUNTING: " + str(self.stunting)
            malnurished = WastingTable.objects.get(height=self.height)
            self.sam = self.weight <= malnurished.weight_70 
            #print "SAM: " + str(self.sam)
            self.mam = (self.weight <= malnurished.weight_80) and (not self.sam)
            #print "MAM: " + str(self.mam)
            #print "STATUS: " + self.patient.status_from_bools(self.mam,self.sam, self.stunting)
            self.patient.status = self.patient.status_from_bools(self.mam,self.sam, self.stunting)
        except Exception, e:
            print e
            return False

    def get_stunting(self):
        stunt_from_table = stunting(self.date_of_birth, self.gender)
        if stunt_from_table:
            self.stunting = float(stunt_from_table) > float(self.height)

    def verify(self): 
        resp = {}
        #if self.patient.assessments.count() > 0:
        #    last_assessment = self.patient.assessments[0]
        #    if last_assessment.height > self.height: return {"ERROR":"last height is %s and this height is %s" % (last_assessment.height,self.height)}
        return resp
        
    def cancel(self):
        self.status = 'C'
        self.save()

class SurveyEntry(models.Model): 
    FLAG_CHOICES = (
        ('C', 'Cancelled'),
        ('G', 'Good'),
        ('B', 'Baseline'),
        ('S', 'Suspect'),
    )

    flag = models.CharField(max_length=1,choices=FLAG_CHOICES,default='G')

    # who what where when why
    survey_date         = models.DateTimeField(auto_now_add=True)
    healthworker_id     = models.CharField(max_length=25,blank=True,null=True)
    cluster_id          = models.CharField(max_length=25,blank=True,null=True)
    child_id            = models.CharField(max_length=25,blank=True,null=True)
    household_id        = models.CharField(max_length=25,blank=True,null=True)
    sex                 = models.CharField(max_length=25,blank=True,null=True)
    date_of_birth       = models.CharField(max_length=25,blank=True,null=True)
    age_in_months       = models.CharField(max_length=25,blank=True,null=True)

    # indicators
    height              = models.CharField(max_length=25,blank=True,null=True)
    weight              = models.CharField(max_length=25,blank=True,null=True)
    oedema              = models.CharField(max_length=15,blank=True,null=True)
    muac                = models.CharField(max_length=15,blank=True,null=True)
