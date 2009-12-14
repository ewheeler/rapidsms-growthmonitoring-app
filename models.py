#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

from datetime import datetime, date, timedelta
from decimal import Decimal as D

from django.db import models
from django.db.models.aggregates import Avg
from django.contrib.auth import models as auth_models
from django.core.exceptions import ObjectDoesNotExist 

from logger.models import IncomingMessage
#from locations.models import Location  
from reporters.models import Reporter, PersistantConnection
from people.models import Person
from childhealth.utils import *

#from healthtables.models import StuntingTable, WastingTable
#from messages import *
   
class HealthWorker(Reporter):
    HW_STATUS_CHOICES = (
        ('A', 'Active'),
        ('I', 'Inactive'),
    )
    last_updated           = models.DateTimeField(auto_now=True)
    # counter for measurement errors, not poor texting skills
    # incremented only when z-scores indicate unreasonable measurements
    errors                 = models.IntegerField(max_length=5,default=0) 
    status                 = models.CharField(max_length=1,choices=HW_STATUS_CHOICES,default='A')
    interviewer_id          = models.PositiveIntegerField(max_length=10, blank=True, null=True)

    class Meta:
        verbose_name = "Health Worker"

    def __unicode__(self):
        return "%s" % (self.full_name())

    def num_messages_sent(self, when=None):
        time_chunks = {
                'today' : datetime.datetime.now().date(),
                'week' : (datetime.datetime.now()-timedelta(weeks=1)),
                'month' : (datetime.datetime.now()-timedelta(days=30)),
                'year' : (datetime.datetime.now()-timedelta(days=365))}
        if when in time_chunks.keys():
                return self.incoming_messages.filter(\
                            received__gte=time_chunks[when]).count()
        else:
            return self.incoming_messages.all().count()

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
        return Assessment.objects.filter(patient=self.patient).order_by('-patient__last_updated')

    def latest_assessment(self):
        if len(self.assessments) > 0:
            return self.assessments[0]
        else:
            return None

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
    survey              = models.ForeignKey('Survey')
    date                = models.DateTimeField(auto_now_add=True)
    status              = models.CharField(max_length=1,choices=ASS_STATUS_CHOICES,default='G')

    # indicators
    height              = models.DecimalField(max_digits=4,decimal_places=1,blank=True,null=True)
    weight              = models.DecimalField(max_digits=4,decimal_places=1,blank=True,null=True)
    muac                = models.DecimalField(max_digits=6,decimal_places=2,blank=True,null=True)
    oedema              = models.NullBooleanField(default=False)
    #diarrea             = models.BooleanField(default=False)

    # expensive calculations 
    #mam                 = models.BooleanField(default=False)
    #sam                 = models.BooleanField(default=False)
    #stunting            = models.BooleanField(default=False)

    # z-scores
    weight4age          = models.DecimalField(max_digits=4,decimal_places=2,null=True,blank=True)
    height4age          = models.DecimalField(max_digits=4,decimal_places=2,null=True,blank=True)
    weight4height       = models.DecimalField(max_digits=4,decimal_places=2,null=True,blank=True)

    class Meta:
        # define a permission for this app to use the @permission_required
        # decorator in childhealth's views
        # in the admin's auth section, we have a group called 'viewers' whose
        # users have this permission -- and are able to see this section
        permissions = (
            ("can_view", "Can view"),
        )

        verbose_name = "Nutrition Assessment"

    def __unicode__(self):
        return "%s" % self.id
    
    @property
    def human_oedema(self):
        if self.oedema == True:
            return 'Y'
        else:
            return 'N'

    def analyze(self, childgrowth):
        results = {}
        #self.nutritional_status()
        self.zscores(childgrowth)
        results.update({'weight4age' : self.weight4age,\
                        'height4age' : self.height4age,\
                        'weight4height' : self.weight4height})
        return results

    def zscores(self, childgrowth):
        print 'ZSCORES'
        age = self.patient.age_in_months
        print age
        gender = self.patient.gender
        print gender
        if age is not None:
            if self.weight is not None:
                self.weight4age = childgrowth.zscore_for_measurement(\
                                "wfa", self.weight, D(age), gender)
            if self.height is not None:
                self.height4age = childgrowth.zscore_for_measurement(\
                                "lhfa", self.height, D(age), gender)

        # determine whether to use weight-for-length or weight-for-height
        # based on age. TODO accept a parameter indicating whether child
        # was measured standing or recumbent
        if self.weight is not None and self.height is not None:
            if age <= 24:
                self.weight4height = childgrowth.zscore_for_measurement(\
                            "wfl", self.weight, D(age), gender, self.height)
            elif age > 24:
                self.weight4height = childgrowth.zscore_for_measurement(\
                            "wfh", self.weight, D(age), gender, self.height)
            else:
                pass
        self.save()

    #TODO refactor malawi analysis
    #not pretty
#    def nutritional_status(self):
        #stunts = StuntingTable.objects.all()
        #for stunt in stunts:
            # convert to int to get floor, then to string
            # so django will save as decimal
        #    new_age = str(float(int(stunt.age)))
        #    stunt.age = new_age
        #    stunt.save()
#        try: 
#            s_calc = StuntingTable.objects.get(gender=self.patient.gender,age=self.patient.age_in_months)
#            self.stunting = self.height < s_calc.height
            #print "STUNTING: " + str(self.stunting)
#            malnurished = WastingTable.objects.get(height=self.height)
#            self.sam = self.weight <= malnurished.weight_70 
            #print "SAM: " + str(self.sam)
#            self.mam = (self.weight <= malnurished.weight_80) and (not self.sam)
            #print "MAM: " + str(self.mam)
            #print "STATUS: " + self.patient.status_from_bools(self.mam,self.sam, self.stunting)
#            self.patient.status = self.patient.status_from_bools(self.mam,self.sam, self.stunting)
#        except Exception, e:
#            print e
#            return False

#    def get_stunting(self):
#        stunt_from_table = stunting(self.date_of_birth, self.gender)
#        if stunt_from_table:
#            self.stunting = float(stunt_from_table) > float(self.height)

#    def verify(self): 
#        resp = {}
        #if self.patient.assessments.count() > 0:
        #    last_assessment = self.patient.assessments[0]
        #    if last_assessment.height > self.height: return {"ERROR":"last height is %s and this height is %s" % (last_assessment.height,self.height)}
#        return resp
        
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
    gender              = models.CharField(max_length=25,blank=True,null=True)
    date_of_birth       = models.CharField(max_length=25,blank=True,null=True)
    age_in_months       = models.CharField(max_length=25,blank=True,null=True)

    # indicators
    height              = models.CharField(max_length=25,blank=True,null=True)
    weight              = models.CharField(max_length=25,blank=True,null=True)
    oedema              = models.CharField(max_length=15,blank=True,null=True)
    muac                = models.CharField(max_length=15,blank=True,null=True)

class Survey(models.Model):
    begin_date              = models.DateField(blank=True,null=True)
    end_date                = models.DateField(blank=True,null=True)
    location                = models.CharField(max_length=160,blank=True,null=True)
    description             = models.CharField(max_length=160,blank=True,null=True)

    # these should come from the latest survey completed in the
    # same season
    # -1.27
    baseline_weight4age     = models.DecimalField(max_digits=8,decimal_places=2,blank=True,null=True)
    # -0.98
    baseline_height4age     = models.DecimalField(max_digits=8,decimal_places=2,blank=True,null=True)
    # -0.79
    baseline_weight4height  = models.DecimalField(max_digits=8,decimal_places=2,blank=True,null=True)

    avg_weight4age          = models.DecimalField(max_digits=8,decimal_places=2,blank=True,null=True)
    avg_height4age          = models.DecimalField(max_digits=8,decimal_places=2,blank=True,null=True)
    avg_weight4height       = models.DecimalField(max_digits=8,decimal_places=2,blank=True,null=True)

    def __unicode__(self):
        return "%s (%s to %s)" % (self.location, self.begin_date, self.end_date)

    def update_avg_zscores(self):
        context = decimal.getcontext()
        survey_assessments = self.assessment_set.filter(status='G')
        sample_avg_weight4age = survey_assessments.aggregate(avg_w4a=Avg('weight4age'))["avg_w4a"]
        sample_avg_height4age = survey_assessments.aggregate(avg_h4a=Avg('height4age'))["avg_h4a"]
        sample_avg_weight4height = survey_assessments.aggregate(avg_w4h=Avg('weight4height'))["avg_w4h"]

        # calculate survey's avg_weight4height, avg_height4age, and avg_weight4age
        # these averages are seeded with a baseline z-score given the
        # weight of 30 entries
        if survey_assessments.count() > 0:
            if self.baseline_weight4age is not None: 
                # (baseline z-score * 30) + avg z-score of survey's assessments
                weighted_avg_weight4age_numerator = context.add(context.multiply(\
                    self.baseline_weight4age, D(30)), D(str(sample_avg_weight4age))) 
                # 30 + number of survey's assessments that are not none
                weighted_avg_weight4age_denomenator = context.add(D(30),\
                    D(survey_assessments.exclude(weight4age=None).count()))
                # divide and limit to hundreths place
                self.avg_weight4age = context.divide(weighted_avg_weight4age_numerator,\
                    weighted_avg_weight4age_denomenator).quantize(D('.01'))

            if self.baseline_height4age is not None:
                weighted_avg_height4age_numerator = context.add(context.multiply(\
                    self.baseline_height4age, D(30)), D(str(sample_avg_height4age))) 
                weighted_avg_height4age_denomenator = context.add(D(30),\
                    D(survey_assessments.exclude(height4age=None).count()))
                self.avg_height4age = context.divide(weighted_avg_height4age_numerator,\
                    weighted_avg_height4age_denomenator).quantize(D('.01'))

            if self.baseline_weight4height is not None:
                weighted_avg_weight4height_numerator = context.add(context.multiply(\
                    self.baseline_weight4height, D(30)), D(str(sample_avg_weight4height))) 
                weighted_avg_weight4height_denomenator = context.add(D(30),\
                    D(survey_assessments.exclude(weight4height=None).count()))
                self.avg_weight4height = context.divide(weighted_avg_weight4height_numerator,\
                    weighted_avg_weight4height_denomenator).quantize(D('.01'))
            # i dont remember if i have to do this here
            self.save()
            return self.avg_zscores_dict()
        else:
            return None

    def avg_zscores_dict(self):
        return {'weight4age'    : self.avg_weight4age,
                'height4age'    : self.avg_height4age,
                'weight4height' : self.avg_weight4height
                }
