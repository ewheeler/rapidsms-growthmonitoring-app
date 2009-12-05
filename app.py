#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

from datetime import date, datetime
import time

from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.db.models import F

import rapidsms
from rapidsms.message import Message
from rapidsms.message import StatusCodes
from rapidsms.connection import Connection
from rapidsms.parsers.keyworder import *

from logger.models import *
from people.models import PersonType
from childhealth.utils import *
from childhealth.models import *
import messages

class App(rapidsms.app.App):

    # lets use the Keyworder parser!
    kw = Keyworder()

    # patterns for dates
    datesep = r"(\.|\/|\\|\-)"
    date = r"\d\d?"
    month = r"\d\d?"
    year = r"\d{2}(\d{2})?"
    # expecting YYYY-MM-DD, YY-MM-DD, YY-M-D, YYYYMMDD, YYMMDD, etc
    datepattern = r"^\d{2}(\d{2})?(?:[\.|\/|\\|\-])?\d\d?(?:[\.|\/|\\|\-])?\d\d?$"

    def start(self):
        # initialize childgrowth, which loads WHO tables
        # TODO is this the best place for this??
        # TODO make childgrowth options configurable via config.py
        self.cg = childgrowth(False, False)

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
                    #self.unmatched(message)
                    self.debug("BANG:")
                    self.debug(e)
                    #return self.handled 
            else:
                self.debug("App does not instantiate Keyworder as 'kw'")
        except Exception, e:
	    # TODO maybe don't log here bc any message not meant
	    # for this app will log this error
	    #
            # self.error(e) 
	    pass


    def __get_or_create_healthworker(self, msg, interviewer_id=None, name=None, lang='fr'):
        self.debug("finding worker...")
        if hasattr(msg, "reporter"):
            self.debug("REPORTER PRESENT")
            self.debug(msg.persistance_dict)
            if msg.persistance_dict.has_key('reporter'):
                # if healthworker is already registered return him/her
                healthworker = HealthWorker.objects.get(pk=msg.persistance_dict['reporter'].pk)
                return healthworker, False
            if not msg.persistance_dict.has_key('reporter'):
                #self.debug(e)
                self.debug("no healthworker")
                if interviewer_id is not None:
                    try:
                        healthworker = HealthWorker.objects.get(interviewer_id=interviewer_id)
                        per_con = msg.persistance_dict['connection']
                        # giving per_con.reporter healthworker
                        # from above doesnt seem to work..
                        per_con.reporter=Reporter.objects.get(pk=healthworker.pk)
                        per_con.save()
                        return healthworker, False
                    except ObjectDoesNotExist, MultipleObjectsReturned:
                        try:
                            # parse the name, and create a healthworker/reporter
                            alias, first, last = Reporter.parse_name(name)
                            healthworker = HealthWorker(
                                first_name=first, last_name=last, alias=alias,
                                interviewer_id=interviewer_id, registered_self=True,
                                message_count=1, language=lang)
                            healthworker.save()

                            return healthworker, True

                        # something went wrong - at the
                        # moment, we don't care what
                        except Exception, e:
                            self.debug('problem finding worker:')
                            self.debug(e)
                else:
                    return None, False


    def __get_or_create_patient(self, message, **kwargs):
        self.debug("finding patient...")
        # Person model requires a PersonType, rather than rock the boat and
        # alter how People work, make sure that a Patient PersonType exists.
        # Also this seems sensible if this code gets refactored it will be
        # easier to port old data...
        person_type, created = PersonType.objects.get_or_create(singular='Patient', plural='Patients')
        kwargs.update({'type' : person_type})

        try:
            # first try to look up patient using only id
            # we don't want to use bday and gender in case this is an update
            # or correction to an already known patient (get_or_create would make
            # a new patient)
            patient_args = kwargs.copy()
            self.debug(patient_args)
            ids = ['code', 'cluster_id', 'household_id']
            has_ids = [patient_args.has_key(id) for id in ids]
            self.debug(has_ids)
            if False not in has_ids:
                self.debug("has ids...")
                id_kwargs = {}
                [id_kwargs.update({id : patient_args.pop(id)}) for id in ids]
                self.debug(id_kwargs)
                # next line should bump us into the exception if we have a new kid
                patient = Patient.objects.get(**id_kwargs)
                self.debug("patient!")

                # compare reported gender and bday to data on file
                # and update + notify if necessary
                bday_on_file = patient.date_of_birth
                gender_on_file = patient.gender
                if patient_args.has_key('gender'):
                    reported_gender = patient_args.get('gender')
                    if gender_on_file != reported_gender:
                        patient.gender = reported_gender
                        patient.save()
                        message.respond("Reported gender '%s' for Child ID %s does not match previosly reported gender=%s" % (reported_gender, patient.code, gender_on_file))
                if patient_args.has_key('date_of_birth'):
                    reported_bday = patient_args.get('date_of_birth')
                    if bday_on_file != reported_bday:
                        patient.date_of_birth = reported_bday
                        patient.save()
                        message.respond("Reported date of birth '%s' for Child ID %s does not match previosly reported DOB=%s" % (reported_bday, patient.code, bday_on_file))
                return patient, False
        except ObjectDoesNotExist, IndexError:
            # patient doesnt already exist, so create with all arguments
            self.debug("new patient!")
            patient, created  = Patient.objects.get_or_create(**kwargs)
            return patient, created


    # Report 9 from outer space
    #@kw("help (.+?)")
    #def help(self, message, more=None):
    #    respond(message,{"OK":SMS_RESPONSE["HELP"]})

    def _validate_date(self, potential_date):
        self.debug("validate date...")
        self.debug(potential_date)
        try:
            matches = re.match( self.datepattern, potential_date, re.IGNORECASE)
            self.debug(matches)
            if matches is not None:
                date = matches.group(0)
                self.debug(date)
                good_date_str, good_date_obj = util.get_good_date(date)
                self.debug(good_date_str)
                return good_date_str, good_date_obj 
            else:
                return None, None
        except Exception, e:
            self.debug('problem validating date:')
            self.debug(e)

    def _validate_sex(self, potential_sex):
        self.debug("validate sex...")
        self.debug(potential_sex)
        try:
            gender = util.get_good_sex(potential_sex)
            if gender is not None:
                return gender
            else:
                return None
        except Exception, e:
            self.debug('problem validating sex:')
            self.debug(e)
    
    def _validate_bool(self, potential_bool):
        self.debug("validate bool...")
        self.debug(potential_bool)
        try:
            if potential_bool is not None:
                if potential_bool[0].upper() in ["Y", "YES", "O", "OUI"]:
                    return "Y"
                elif potential_bool[0].upper() in ["N", "NO", "NON"]:
                    return "N"
                else:
                    return None
            else:
                return None
        except Exception, e:
            self.debug('problem validating bool:')
            self.debug(e)

    def _validate_ids(self, id_dict):
        self.debug("validate ids...")
        try:
            valid_ids = {}
            invalid_ids = {}
            for k,v in id_dict.iteritems():
                if v.isdigit():
                    valid_ids.update({k:v})
                else:
                    invalid_ids.update({k:v})
            return valid_ids, invalid_ids
        except Exception, e:
            self.debug('problem validating ids:')
            self.debug(e)

    def _validate_measurements(self, height, weight, muac):
        self.debug("validate measurements...")
        valid_height = False
        valid_weight = False
        valid_muac = False
        try:
            if height is not None:
                if 44.5 < float(height) < 120.4:
                    valid_height = True
            else:
                valid_height = True
            if weight is not None:
                if 3.0 < float(weight) < 20.0:
                    valid_weight = True
            else:
                valid_weight = True
            if muac is not None:
                # TODO i made these up. cm or mm??
                if 10.0 < float(muac) < 150.0:
                    valid_muac = True
            else:
                valid_muac = True
            return valid_height, valid_weight, valid_muac
        except Exception, e:
            self.debug('problem validating measurements:')
            self.debug(e)


    kw.prefix = ['report', 'rep', 'enq']
    @kw("(.*?) (.*?) (.*?) (.*)")
    def report(self, message, cluster_id, child_id, household_id, data_tokens):#, gender, bday, age, weight, height, oedema, muac):
        self.debug("reporting...")
        try:
            # find out who is submitting this report
            healthworker, created = self.__get_or_create_healthworker(message)
        except Exception, e:
            self.debug(e)
        if healthworker is None:
            # halt reporting process and tell sender to register first
            return message.respond("Please register before submitting survey: Send the word REGISTER followed by your Interviewer ID and your full name.", StatusCodes.APP_ERROR)

        token_labels = ['sex', 'date_of_birth', 'age_in_months', 'weight', 'height', 'oedema', 'muac']
        token_data = data_tokens.split()
        
        try:
            if len(token_data) > 7:
                self.debug("too much data")
                message.respond("Too much data!", StatusCodes.APP_ERROR)

            tokens = dict(zip(token_labels, token_data))

            for k,v in tokens.iteritems():
                print v
                # replace 'no data' shorthands with None
                if v.upper() in ['X', 'XX', 'XXX']:
                    tokens.update({k : None})

            # save record of survey submission before doing any processing
            # so we have all of the entries as they were submitted
            survey_entry = SurveyEntry(**tokens)
            if healthworker.interviewer_id is not None:
                survey_entry.healthworker_id=healthworker.interviewer_id
            survey_entry.cluster_id = cluster_id
            survey_entry.child_id = child_id
            survey_entry.household_id = household_id
            survey_entry.save()
        except Exception, e:
            self.debug(e)

        # check that all three id codes are numbers
        valid_ids, invalid_ids = self._validate_ids({'interviewer' : str(healthworker.interviewer_id),\
            'cluster' : cluster_id, 'household' : household_id, 'child' : child_id})
        # send responses for each invalid id, if any
        if len(invalid_ids) > 0:
            for k,v in invalid_ids.iteritems():
                message.respond("Sorry, ID code '%s' is not valid for a %s" % (v, k), StatusCodes.APP_ERROR)
            # halt reporting process if any of the id codes are invalid
            return True
        # TODO this is silly. move to reporters? logger? count logged messages?
        healthworker.message_count  = healthworker.message_count+1

        self.debug("getting patient...")
        # begin collecting valid patient arguments
        patient_kwargs = {'cluster_id' : cluster_id, 'household_id' :\
            household_id, 'code' : child_id}

        # no submitted bday
        if survey_entry.date_of_birth is None:
            patient_kwargs.update({'date_of_birth' : None})
        # make sure submitted bday is valid
        else:
            dob_str, dob_obj = self._validate_date(survey_entry.date_of_birth)
            if dob_obj is not None:
                self.debug(dob_obj)
                patient_kwargs.update({'date_of_birth' : dob_obj})
            else:
                patient_kwargs.update({'date_of_birth' : ""})
                message.respond("Sorry I don't understand '%s' as a child's date of birth. Please use YYYY-MM-DD" % (survey_entry.date_of_birth), StatusCodes.APP_ERROR)

        # make sure reported gender is valid
        good_sex = self._validate_sex(survey_entry.sex)
        if good_sex is not None:
            self.debug(good_sex)
            patient_kwargs.update({'gender' : good_sex})
        else:
            patient_kwargs.update({'gender' : ""}) 
            # halt reporting process if we dont have a valid gender.
            # this can't be unknown. check in their pants if you arent sure
            return message.respond("Sorry I don't understand '%s' as a child's gender. Please use M for male or F for female." % (survey_entry.sex), StatusCodes.APP_ERROR)

        # find patient or create a new one
        self.debug(patient_kwargs)
        patient, created = self.__get_or_create_patient(message, **patient_kwargs)

        # update age separately (should be the only volitile piece of info)
        self.debug(survey_entry.age_in_months)
        if survey_entry.age_in_months is not None:
            patient.age_in_months = survey_entry.age_in_months
        else:
            patient.age_in_months = util.sloppy_date_to_age_in_months(patient.date_of_birth)
        self.debug(patient.age_in_months)
        patient.save()

        # calculate age based on reported date of birth
        # respond if calcualted age differs from reported age
        # by more than 3 months TODO make this configurable
        #self.debug("getting sloppy age...")
        #sloppy_age_in_months = util.sloppy_date_to_age_in_months(patient.date_of_birth)
        #self.debug(sloppy_age_in_months)
        #if (abs(int(sloppy_age_in_months) - int(patient.age_in_months)) > 3):
        #    message.respond("Date of birth indicates Child ID %s's age (in months) is %s, which does not match the reported age (in months) of %s" % (patient.code, sloppy_age_in_months, patient.age_in_months))

        try:
            self.debug("making assessment...")
            # create nutritional assessment entry
            self.debug(survey_entry.height)
            self.debug(survey_entry.weight)
            self.debug(survey_entry.muac)

            valid_oedema = self._validate_bool(survey_entry.oedema)
            valid_height, valid_weight, valid_muac = self._validate_measurements(\
                survey_entry.height, survey_entry.weight, survey_entry.muac)

            self.debug(valid_height)
            self.debug(valid_weight)
            self.debug(valid_muac)

            if valid_height and valid_weight and valid_muac:
                ass = Assessment(healthworker=healthworker, patient=patient,\
                        height=survey_entry.height, weight=survey_entry.weight, muac=survey_entry.muac, oedema=valid_oedema)
            else:
                return message.respond('Measurement problem. Please try again.')
        except Exception, e:
            self.debug("problem making assessment:")
            self.debug(e)

        ass.save()
        self.debug("saved assessment")

        data = [
                "ClusterID=%s"      % (patient.cluster_id or "??"),
                "ChildID=%s"        % (patient.code or "??"),
                "HouseholdID=%s"    % (patient.household_id or "??"),
                "gender=%s"         % (patient.gender or "??"),
                "DOB=%s"            % (patient.date_of_birth or "??"),
                "age=%s"            % (patient.age_in_months or "??"),
                "height=%s"         % (ass.height or "??"),
                "weight=%s"         % (ass.weight or "??"),
                "oedema=%s"         % (ass.oedema or "??"),
                "MUAC=%s"           % (ass.muac or "??")]

        confirmation = "Thanks, %s. Received %s" %\
            (healthworker.full_name(), " ".join(data))

        message.respond(confirmation)
        self.debug('sent confirmation')

        # perform analysis based on cg instance from start()
        # TODO add to Assessment save method?
        results = ass.analyze(self.cg)
        self.debug(results)
        response_map = {
            'weight4age'    : 'Oops. I think weight or age is incorrect',
            'height4age'    : 'Oops. I think height or age is incorrect',
            'weight4height' : 'Oops. I think weight or height is incorrect'
        }
        for ind, z in results.iteritems():
            self.debug(str(ind) + " " + str(z))
            if z is not None:
                if abs(z) > 3:
                    message.respond(response_map[ind], StatusCodes.APP_ERROR)
                    # add one to healthworker's error tally
                    healthworker.errors = healthworker.errors + 1
                    healthworker.save()
                    # mark both the entry and the assessment as 'suspect'
                    survey_entry.flag = 'S'
                    survey_entry.save()
                    ass.status = 'S'
                    ass.save()

    def unmatched(self, message):
        message.respond("Sorry, I don't understand.", StatusCodes.APP_ERROR)

    kw.prefix = ['cancel', 'can']
    @kw("(\d+?) (\d+?) (\d+?)")
    def cancel_report(self, message, child, household, cluster):
        try:
            patient = Patient.objects.get(cluster_id=cluster,\
                        household_id=household, code=child)
            ass = patient.latest_assessment()
            if ass is not None:
                ass.cancel()
                message.respond("CANCELLED report submitted by %s (ID %s) on %s for Child ID %s (Household %s, Cluster %s)" % (ass.healthworker.full_name(), ass.healthworker.interviewer_id, ass.date, patient.code, patient.household_id, patient.cluster_id))
            else:
                message.respond("Sorry, unable to locate report for Child ID %s (Household %s, Cluster %s)" % (child, household, cluster))
        except ObjectDoesNotExist:
            message.respond("Sorry, unable to locate report for Child ID %s (Household %s, Cluster %s)" % (child, household, cluster))


    kw.prefix = ['register', 'reg']
    @kw("(\d+?) (.*?)")
    def register_healthworker(self, message, code, name):
        self.debug("register...")
        try:
            healthworker, created = self.__get_or_create_healthworker(message, code, name)
            if created:
                message.respond("Hello %s, thanks for registering as Interviewer ID %s!" % (healthworker.full_name(), healthworker.interviewer_id))
            else:
                message.respond("Hello again, %s. You are registered with RapidSMS" % (healthworker.full_name()))
                #message.respond("To register a different interviewer for this ID, please first text REMOVE followed by the interviewer ID.")
        except Exception, e:
            self.debug("oops! problem registering heathworker:")
            self.debug(e)
            pass

    @kw("remove (\d+?)")
    def remove_healthworker(self, message, code):
        self.debug("removing...")
        healthworker, created = self.__get_or_create_healthworker(message, code)
        try:
            if not created:
                healthworker.status = 'I'
                healthworker.save()
                message.respond("%s has been removed from Interviewer ID %s" % (healthworker.full_name(), healthworker.interviewer_id))
                message.respond("To register a new person as Interviewer ID %s, text REGISTER followed by %s and a new name." % (healthworker.interviewer_id, healthworker.interviewer_id))
                healthworker.interviewer_id = None 
                healthworker.save()
        except Exception, e:
            self.debug(e)
