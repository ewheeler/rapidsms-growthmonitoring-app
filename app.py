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
from people.models import PersonType
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
                    self.debug(func)
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


    def __get_or_create_healthworker(self, msg, interviewer_id, name=None, lang='fr'):
        self.debug("finding worker...")
        if hasattr(msg, "reporter"):
            self.debug("REPORTER PRESENT")
            try:
                # if healthworker is already registered return him/her
                self.debug(interviewer_id)
                healthworker = HealthWorker.objects.get(interviewer_id=interviewer_id)
            except ObjectDoesNotExist:
                #self.debug(e)
                self.debug("no healthworker")
                try:
                    # parse the name, and create a healthworker/reporter
                    alias, first, last = Reporter.parse_name(name)
                    healthworker = HealthWorker(
                        first_name=first, last_name=last,
                        interviewer_id=interviewer_id, registered_self=True,
                        message_count=1, language=lang)
                    healthworker.save()

                    # attach the reporter to the current connection
                    msg.persistant_connection.reporter = healthworker
                    msg.persistant_connection.save()

                    return healthworker, True

                # something went wrong - at the
                # moment, we don't care what
                except Exception, e:
                    self.debug(e)
            self.debug("trouble")
        
    def __get_or_create_patient(self, **kwargs):
        self.debug("finding patient...")
        # Person model requires a PersonType, rather than rock the boat and
        # alter how People work, make sure that a Patient PersonType exists.
        # Also this seems sensible if this code gets refactored it will be
        # easier to port old data...
        person_type, created = PersonType.objects.get_or_create(singular='Patient', plural='Patients')
        kwargs.update({'type' : person_type})
        patient, created  = Patient.objects.get_or_create(**kwargs)
        return patient, created
        

    # Report 9 from outer space
    @kw("help (.+?)")
    def help(self, message, more=None):
        respond(message,{"OK":SMS_RESPONSE["HELP"]})


    kw.prefix = ['report', 'rep']
    @kw("(.*?) (.*?) (.*?) (.*?) (.*?) (.*?) (.*?) (.*?) (.*?) (.*?) (.*?)") 
    def report(self, message, interviewer, cluster, household, child, gender, bday, age, weight, height, muac, oedema):
        self.debug("reporting...")
        try:
            # find out who is submitting this report
            healthworker, created = self.__get_or_create_healthworker(message, interviewer)
        except Exception, e:
            self.debug(e)
        self.debug(healthworker)
        # TODO this is silly. move to reporters? logger? count logged messages?
        healthworker.message_count  = healthworker.message_count+1
        if created:
            # halt reporting process and tell sender to register first
            return message.respond("Please register before submitting survey: Send the word REGISTER followed by your Interviewer ID and your full name.")

        try:
            self.debug("getting patient...")
            # find patient or create a new one
            # TODO perform this with only a subset of this info? we dont want to
            # erroneously create a new patient if one of these is incorrect
            patient, created = self.__get_or_create_patient(cluster_id=cluster,\
                household_id=household, gender=gender, code=child)
            # update bday separately (see above TODO)
            patient.date_of_birth = bday
            # update age separately (should be the only volitile piece of info)
            patient.age_in_months = age
            patient.save()

            self.debug("making assessment...")
            # create nutritional assessment entry
            ass = Assessment(healthworker=healthworker, patient=patient,\
                    height=height, weight=weight, muac=muac, oedema=oedema)
            # perform analysis
            # TODO add to save method
            ass.analyze()
            results = ass.verify()

            if ("ERROR" in results):
                self.debug("error in result")
                healthworker.errors = healthworker.errors + 1
                healthworker.save()
            else:
                try:
                    ass.save()
                except Exception,save_err:
                    self.debug("error saving")
                    resp ={"ERROR": save_err}
                    healthworker.errors = healthworker.errors + 1
                    healthworker.save()

            message.respond("Thank you, %s. Received height=%scm weight=%skg muac=%smm oedema=%s for Child ID %s (Household %s, Cluster %s)." % (healthworker.full_name(), ass.height, ass.weight, ass.muac, ass.oedema, patient.code, patient.household_id, patient.cluster_id))
        except Exception,e:
            self.debug(e)
            resp["ERROR"] = "There was an error with your report - please check your measurements"

        respond(message, resp) 
        
    
    @kw("cancel (.*?) (.*?)")
    def cancel_report(self, message, cluster, household, child):
        resp = {}
        try: 
            patient = Patient.objects.get(cluster_id=cluster,\
                        household_id=household, code=child)
            ass = patient.assessments[0] 
            ass.cancel()
            resp["OK"] = "CANCELED report for child %s at gmc %s" % (child,gmc)
        except Exception,e:
            resp["ERROR"] = "UNABLE TO CANCEL REPORT for child %s at gmc %" % (child, gmc)
        
        respond(message,resp) 
    

    kw.prefix = ['register', 'reg']
    @kw("(\d+?) (.*?)")
    def register_healthworker(self, message, code, name):
        self.debug("register...")
        try:
            healthworker, created = self.__get_or_create_healthworker(message, code, name)
            if created:
                message.respond("Hello %s, thanks for registering as Interviewer ID %s!" % (healthworker.full_name(), healthworker.alias))
            else:
                message.respond("Hello again, %s. " % (healthworker.full_name()))
                message.respond("To register a different interviewer for this ID, please first text REMOVE followed by the interviewer ID.")
        except Exception, e:
            self.debug("oops!")
            self.debug(e)
            pass

    def remove_healthworker(self, message, code):
        self.debug("removing...")
        healthworker, created = self.__get_or_create_healthworker(message, code)
        try:
            if not created:
                healthworker.status = 'I'
                healthworker.save()
                message.respond("%s has been removed from Interviewer ID %s" % (healthworker.full_name(), healthworker.alias))
                message.respond("To register a new person as Interviewer ID %s, text REGISTER followed by %s and a new name." % (healthworker.alias, healthworker.alias))
                # TODO shameful hack alert! shameful hack alert!
                # reporter aliases must be unique, and its easier to use alias
                # than add a healthworker id field to healthworker.
                # i will most certainly regret this in the future
                healthworker.alias = int(healthworker.alias) + 30000
                healthworker.save()
        except Exception, e:
            self.debug(e)
