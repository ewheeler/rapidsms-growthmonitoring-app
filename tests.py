from rapidsms.tests.scripted import TestScript
from app import App
import reporters.app as reporters_app

from childhealth.models import *
from childhealth.utils import *
from reporters.models import Reporter, PersistantConnection, PersistantBackend
from logger.models import *
from people.models import PersonType
    
class TestApp (TestScript):
    apps = (App, reporters_app.App)
    # the test_backend script does the loading of the dummy backend that allows reporters
    # to work properly in tests
    fixtures = ['test_backend']

    def setUp(self):
        TestScript.setUp(self)
    
    testRegistration = """
           555555 > Enq 112 3 2 m 100208 x 15.6 79.2 N 19.7 
           555555 < Please register before submitting survey: Send the word REGISTER followed by your Interviewer ID and your full name.
           555555 > Reg 99 mister tester
           555555 < Hello mister tester, thanks for registering as Interviewer ID 999!
           555555 > Enq 112 3 2 m 100208 x 15.6 79.2 N 19.7 
           555555 < Thanks, mister tester. Received ClusterID=112 ChildID=3 HouseholdID=2 gender=M DOB=2008-02-10 age=21 height=79.2 weight=15.6 oedema=N MUAC=19.7
           555555 > Oops. I think weight or height is incorrect
         """        
