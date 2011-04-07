import unittest
from rapidsms.tests.scripted import TestScript
from rapidsms.models import Connection
from app import App

from models import *
from datetime import date
from datetime import timedelta

class TestApp (TestScript):
    apps = (App)

    def setUp(self):
        TestScript.setUp(self)
        survey = Survey.objects.create(location='test', begin_date=date.today()-timedelta(7), end_date=date.today()+timedelta(7))
        # this is the birthdate used in the tests
        birthdate = date(2008,2,10)
        td = date.today() - birthdate
        # calculate how many months ago so we know what to expect in the
        # confirmation message, since we cannot hard-code the expected reply
        self.months_ago = str(int(td.days/30.4375))
    
    def testRegistration(self):
        # TODO: calculate number of months since birth date in test
    	self.assertInteraction("""
           555555 > Enq 112 3 2 m 100208 x 15.6 79.2 N 19.7 
           555555 < Please register before submitting survey: Send the word REGISTER followed by your Interviewer ID and your full name.
           555555 > Reg 99 mister tester
           555555 < Hello mister tester, thanks for registering as Interviewer ID 99!
           555555 > Enq 112 3 2 m 100208 x 15.6 79.2 N 19.7 
           555555 < Possible measurement error. Please check height, weight, MUAC or age of child - cluster 112, child_id 3, household 2.
           555555 > Enq 112 3 2 m 100208 x 15.6 89.2 N 19.7
           555555 < Thanks, mister tester. Received ClusterID=112 ChildID=3 HouseholdID=2 Gender=M DOB=2008-02-10 Age=%sm Weight=15.6kg Height=89.2cm Oedema=N Muac=19.7cm
         """ % self.months_ago)
        # check that a Mister Tester contact has been created
        mister_tester = Connection.objects.get(identity="555555").contact
        # find assessments sent by Mister Tester
        asses = Assessment.objects.filter(healthworker=mister_tester).order_by('-date')
        # ensure only two have been created
        self.assertEqual(asses.count(),2)
        # ensure that z-scores have been saved for all assessments
        for ass in asses:
            self.assertFalse(ass.weight4age == None)
            self.assertFalse(ass.height4age == None)
            self.assertFalse(ass.weight4height == None)
