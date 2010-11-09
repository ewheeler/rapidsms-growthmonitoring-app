import unittest
from rapidsms.tests.scripted import TestScript
from app import App

from models import *
from datetime import date
from datetime import timedelta

class TestApp (TestScript):
    apps = (App)

    def setUp(self):
        TestScript.setUp(self)
	survey = Survey.objects.create(location='test', begin_date=date.today()-timedelta(7), end_date=date.today()+timedelta(7))
    
    def testRegistration(self):
    	self.assertInteraction("""
           555555 > Enq 112 3 2 m 100208 x 15.6 79.2 N 19.7 
           555555 < Please register before submitting survey: Send the word REGISTER followed by your Interviewer ID and your full name.
           555555 > Reg 99 mister tester
           555555 < Hello mister tester, thanks for registering as Interviewer ID 99!
           555555 > Enq 112 3 2 m 100208 x 15.6 79.2 N 19.7 
	   555555 < Possible measurement error. Please check height, weight, MUAC or age of child - cluster 112, child_id 3, household 2.
           555555 > Enq 112 3 2 m 100208 x 15.6 59.2 N 19.7
           555555 < Thanks, mister tester. Received GrappeID=112 EnfantID=3 MenageID=2 sexe=M DN=2008-02-10 age=32m poids=15.6kg taille=59.2cm oedemes=N PB=19.7cm
         """)
