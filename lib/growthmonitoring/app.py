#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

from datetime import date, datetime
import decimal
from decimal import Decimal as D
import time
import gettext

from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.db.models import F
from django.conf import settings

from pygrowup import Calculator
from pygrowup import helpers

import rapidsms
from rapidsms.apps.base import AppBase
from keyworder import *

from people.models import PersonType

from models import *
from messages import *
#
# Module level translation calls so we don't have to prefix everything
# so we don't have to prefix _t() with 'self'!!
#

# Mutable globals hack 'cause Python module globals are WHACK
_G = {
    'SUPPORTED_LANGS': {
        # 'deb':u'Debug',
        'fr':[u'Français'],
        'en':['English'],
        },
    'TRANSLATORS': {"en": FAKE_GETTEXT["en"], "fr": FAKE_GETTEXT["fr"]},
    'DEFAULT_LANG':'en',
    }

# update default values with any project-level settings
_G.update(getattr(settings, 'GROWTHMONITORING_SETTINGS', {}))

########
# i18n #
########
#def _init_translators():
    #path = os.path.join(os.path.dirname(__file__),"locale")
    #for lang,name in _G['SUPPORTED_LANGS'].items():
    #    trans = gettext.translation('django',path,[lang,_G['DEFAULT_LANG']])
    #    _G['TRANSLATORS'].update( {lang:trans} )

def _t(locale, response_key):
    """translate text with default language"""
    translator=_G['TRANSLATORS'][_G['DEFAULT_LANG']]
    if locale in _G['TRANSLATORS']:
        translator=_G['TRANSLATORS'][locale]
    #return translator.ugettext(key)
    return translator[response_key]

def _(response_key):
    #if hasattr(message, 'reporter'):
    #    rep = getattr(message, 'reporter')
    #    if hasattr(rep, 'lang'):
    #        lang = getattr(rep, 'lang')
    #        return message.respond(_t(message.reporter.lang, key))
    return _t(_G['DEFAULT_LANG'], response_key)

class App(AppBase):
    #def __init__(self, router):
        # NB: this cannot be called globally
        # because of depencies between GNUTranslations (a -used here)
        # and DJangoTranslations (b -used in views)
        # i.e. initializing b then a is ok, but a then b fails
        #_init_translators()

    # lets use the Keyworder parser!
    kw = Keyworder()

    # patterns for dates
    datesep = r"(\.|\/|\\|\-)"
    date = r"\d\d?"
    month = r"\d\d?"
    year = r"\d{2}(\d{2})?"
    # expecting YYYY-MM-DD, YY-MM-DD, YY-M-D, YYYYMMDD, YYMMDD, etc
    datepattern = r"^\d{2}(\d{2})?(?:[\.|\/|\\|\-])?\d\d?(?:[\.|\/|\\|\-])?\d\d?$"

    def configure(self, **kwargs):
        try:
            _G['DEFAULT_LANG'] = kwargs.pop('default_lang')
        except:
            pass

    def start(self):
        # initialize pygrowup Calculator, which loads WHO tables
        # TODO is this the best place for this??
        # TODO make Calculator options configurable via config.py
        self.cg = Calculator(False, False)

    def parse(self, message):
        self.handled = False

    def respond(message,log={}):
        key = "OK"
        if "ERROR" in log: key = "ERROR"

        message.respond(log[key])

    def handle(self, message):
        # attempt to match tokens in this message
        # using the keyworder parser
        func, captures = self.kw.match(self, message.text.lower())
        if func and captures:
            self.debug(func)
            func(self, message, *captures)
            # short-circuit handler calls because
            # we are responding to this message
            return self.handled

    def __identify_healthworker(self, msg):
        # if healthworker is already registered on this connection, return him/her
        try:
            healthworker = msg.connection.contact
            return healthworker
        except ObjectDoesNotExist:
            return None

    def __register_healthworker(self, msg, interviewer_id, name, lang='fr'):
        self.debug('registering healthworker...')
        try:
            # find healthworker via interviewer_id and add new connection
            # (e.g., registering from a second connection)
            alias, first, last = Contact.parse_name(name)
            healthworker = Contact.objects.get(interviewer_id=interviewer_id,\
                first_name=first, last_name=last, name=name)
            msg.connection.contact=healthworker
            msg.connection.save()
            return healthworker, False
        except ObjectDoesNotExist, MultipleObjectsReturned:
            try:
                # TODO remove connection from previous hw
                # parse the name, and create a healthworker/reporter
                # (e.g., registering from first connection)
                alias, first, last = Contact.parse_name(name)
                healthworker = Contact(
                    first_name=first, last_name=last, alias=alias,
                    interviewer_id=interviewer_id, language=lang, name=name)
                healthworker.save()
                msg.connection.contact=healthworker
                msg.connection.save()
                return healthworker, True
            # something went wrong - at the
            # moment, we don't care what
            except Exception, e:
                self.exception('problem registering worker')



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
                patient = Person.objects.get(**id_kwargs)
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
                        #message.respond(_("gender-mismatch") % (reported_gender, patient.code, gender_on_file))
                if patient_args.has_key('date_of_birth'):
                    reported_bday = patient_args.get('date_of_birth')
                    if bday_on_file != reported_bday:
                        patient.date_of_birth = reported_bday
                        patient.save()
                        #message.respond(_("dob-mismatch") % (reported_bday, patient.code, bday_on_file))
                return patient, False
        except ObjectDoesNotExist, IndexError:
            # patient doesnt already exist, so create with all arguments
            self.debug("new patient!")
            patient, created  = Person.objects.get_or_create(**kwargs)
            return patient, created


    # Report 9 from outer space
    #@kw("help (.+?)")
    #def help(self, message, more=None):
    #    respond(message,{"OK":SMS_RESPONSE["HELP"]})

    def _validate_date(self, potential_date):
        self.debug("validate date...")
        self.debug(potential_date)
        try:
            #matches = re.match( self.datepattern, potential_date, re.IGNORECASE)
            #self.debug(matches)
            #if matches is not None:
            #    date = matches.group(0)
            self.debug(potential_date)
            good_date_str, good_date_obj = helpers.get_good_date(potential_date)
            self.debug(good_date_str)
            return good_date_str, good_date_obj
            #else:
            #    return None, None
        except Exception, e:
            self.exception('problem validating date')
            return None, None

    def _validate_sex(self, potential_sex):
        self.debug("validate sex...")
        self.debug(potential_sex)
        try:
            gender = helpers.get_good_sex(potential_sex)
            if gender is not None:
                return gender
            else:
                return None
        except Exception, e:
            self.exception('problem validating sex')

    def _validate_bool(self, potential_bool):
        self.debug("validate bool...")
        self.debug(potential_bool)
        try:
            if potential_bool is not None:
                if potential_bool[0].upper() in ["Y", "YES", "O", "OUI"]:
                    return "Y", 1
                elif potential_bool[0].upper() in ["N", "NO", "NON"]:
                    return "N", 0
                else:
                    return None
            else:
                return None, 0
        except Exception, e:
            self.exception('problem validating bool')

    def _validate_ids(self, id_dict):
        self.debug("validate ids...")
        try:
            valid_ids = {}
            invalid_ids = {}
            for k,v in id_dict.iteritems():
                if v.isdigit() or v.upper().startswith('X'):
                    valid_ids.update({k:v})
                else:
                    invalid_ids.update({k:v})
            return valid_ids, invalid_ids
        except Exception, e:
            self.exception('problem validating ids')

    def _validate_measurements(self, height, weight, muac):
        self.debug("validate measurements...")
        valid_height = False
        valid_weight = False
        valid_muac = False
        try:
            if height is not None:
                if 40.0 < float(height) < 125.0:
                    valid_height = True
            else:
                valid_height = True
            if weight is not None:
                if 1.5 < float(weight) < 35.0:
                    valid_weight = True
            else:
                valid_weight = True
            if muac is not None:
                if 10.0 < float(muac) < 22.0:
                    valid_muac = True
            else:
                valid_muac = True
            return valid_height, valid_weight, valid_muac
        except Exception, e:
            self.exception('problem validating measurements')


    kw.prefix = ['report', 'rep', 'enq']
    @kw("(.*?) (.*?) (.*?) (.*)")
    def report(self, message, cluster_id, child_id, household_id, data_tokens):#, gender, bday, age, weight, height, oedema, muac):
        self.debug("reporting...")
        try:
            survey = Survey.objects.get(begin_date__lte=datetime.now().date(),\
                end_date__gte=datetime.now().date())

        except ObjectDoesNotExist, MultipleObjectsReturned:
            return message.respond("No active survey at this date")

        # find out who is submitting this report
        healthworker = self.__identify_healthworker(message)

        if healthworker is None:
            # halt reporting process and tell sender to register first
            return message.respond(_("register-before-reporting"))

        token_labels = ['gender', 'date_of_birth', 'age_in_months', 'weight', 'height', 'oedema', 'muac']
        token_data = data_tokens.split()

        try:
            if len(token_data) > 7:
                self.debug("too much data")
                message.respond(_("too-many-tokens"))

            tokens = dict(zip(token_labels, token_data))

            for k,v in tokens.iteritems():
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
            self.exception()
            message.respond(_("invalid-measurement") %\
                (survey_entry.cluster_id, survey_entry.child_id, survey_entry.household_id))

        # check that all three id codes are numbers
        valid_ids, invalid_ids = self._validate_ids({'interviewer' : str(healthworker.interviewer_id),\
            'cluster' : cluster_id, 'household' : household_id, 'child' : child_id})
        # send responses for each invalid id, if any
        if len(invalid_ids) > 0:
            for k,v in invalid_ids.iteritems():
                message.respond(_("invalid-id") % (v, k))
            # halt reporting process if any of the id codes are invalid
            return True

        for k,v in valid_ids.iteritems():
            # replace 'no data' shorthands with None
            if v.upper().startswith('X'):
                tokens.update({k : None})

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
                message.respond(_("invalid-dob") % (survey_entry.date_of_birth))

        # make sure reported gender is valid
        good_sex = self._validate_sex(survey_entry.gender)
        if good_sex is not None:
            self.debug(good_sex)
            patient_kwargs.update({'gender' : good_sex})
        else:
            patient_kwargs.update({'gender' : ""})
            # halt reporting process if we dont have a valid gender.
            # this can't be unknown. check in their pants if you arent sure
            return message.respond(_("invalid-gender") % (survey_entry.gender))

        try:
            # find patient or create a new one
            self.debug(patient_kwargs)
            patient, created = self.__get_or_create_patient(message, **patient_kwargs)
        except Exception, e:
            self.exception('problem saving patient')

        try:
            # update age separately (should be the only volitile piece of info)
            self.debug(survey_entry.age_in_months)
            if survey_entry.age_in_months is not None:
                patient.age_in_months = int(survey_entry.age_in_months)
            else:
                patient.age_in_months = helpers.date_to_age_in_months(patient.date_of_birth)
            self.debug(patient.age_in_months)
            patient.save()
        except Exception, e:
            self.exception('problem saving age')
            return message.respond("On doit mettre le X pour les donnees manquantes par age")

        # calculate age based on reported date of birth
        # respond if calcualted age differs from reported age
        # by more than 3 months TODO make this configurable
        #self.debug("getting sloppy age...")
        #sloppy_age_in_months = helpers.date_to_age_in_months(patient.date_of_birth)
        #self.debug(sloppy_age_in_months)
        #if (abs(int(sloppy_age_in_months) - int(patient.age_in_months)) > 3):
        #    message.respond("Date of birth indicates Child ID %s's age (in months) is %s, which does not match the reported age (in months) of %s" % (patient.code, sloppy_age_in_months, patient.age_in_months))

        try:
            self.debug("making assessment...")
            # create nutritional assessment entry
            self.debug(survey_entry.height)
            self.debug(survey_entry.weight)
            self.debug(survey_entry.muac)

            measurements = {"height" : survey_entry.height,\
                "weight" : survey_entry.weight, "muac" : survey_entry.muac}
            for k,v in measurements.iteritems():
                # replace 'no data' shorthands with None
                if v.upper().startswith('X'):
                    tokens.update({k : None})

            human_oedema, bool_oedema = self._validate_bool(survey_entry.oedema)
            valid_height, valid_weight, valid_muac = self._validate_measurements(\
                measurements['height'], measurements['weight'], measurements['muac'])

            self.debug(valid_height)
            self.debug(valid_weight)
            self.debug(valid_muac)

            if valid_height and valid_weight and valid_muac:
                ass = Assessment(healthworker=healthworker, patient=patient,\
                        height=measurements['height'], weight=measurements['weight'],\
                        muac=measurements['muac'], oedema=bool_oedema, survey=survey)
            else:
                return message.respond(_("invalid-measurement") %\
                    (survey_entry.cluster_id, survey_entry.child_id, survey_entry.household_id))
        except Exception, e:
            self.exception("problem making assessment")
            message.respond(_("invalid-measurement") %\
                (survey_entry.cluster_id, survey_entry.child_id, survey_entry.household_id))

        ass.save()
        self.debug("saved assessment")

        try:
            data = {
                "name": healthworker.name,
                "cluster_id": patient.cluster_id or "??",
                "code": patient.code or "??",
                "household_id": patient.household_id or "??",
                "gender": patient.gender or "??",
                "date_of_birth": patient.date_of_birth or "??",
                "age_in_months": patient.age_in_months or "??",
                "weight": ass.weight or "??",
                "height": ass.height or "??",
                "human_oedema": ass.human_oedema or "??",
                "muac": ass.muac or "??",
            }

            self.debug('constructing confirmation')
            confirmation = _("report-confirm") % data
            self.debug('confirmation constructed')
        except Exception, e:
            self.exception('problem constructing confirmation')

        try:
            # perform analysis based on cg instance from start()
            # TODO add to Assessment save method?
            results = ass.analyze(self.cg)
            self.debug('analyzed!')
            self.debug(results)
            #response_map = {
            #    'weight4age'    : 'Oops. I think weight or age is incorrect',
            #    'height4age'    : 'Oops. I think height or age is incorrect',
            #    'weight4height' : 'Oops. I think weight or height is incorrect'
            #}
            self.debug('updating averages...')
            average_zscores = survey.update_avg_zscores()
            self.debug(average_zscores)
            context = decimal.getcontext()
            for ind, z in results.iteritems():
                self.debug(str(ind) + " " + str(z))
                if z is not None:
                    survey_avg = average_zscores[ind]
                    # TODO plus or minus!
                    survey_avg_limit = D(3)
                    if survey_avg is not None:
                        survey_avg_limit = context.add(D(3), abs(survey_avg))
                    if abs(z) > survey_avg_limit:
                        self.debug('BIG Z: ' + ind)
                        self.debug('sample z: ' + str(z))
                        self.debug('avg z: ' + str(survey_avg_limit))
                        # add one to healthworker's error tally
                        healthworker.errors = healthworker.errors + 1
                        healthworker.save()
                        # mark both the entry and the assessment as 'suspect'
                        survey_entry.flag = 'S'
                        survey_entry.save()
                        ass.status = 'S'
                        ass.save()
                        #message.respond(response_map[ind])
                        return message.respond(_("invalid-measurement") %\
                            (patient.cluster_id, patient.code, patient.household_id))
        except Exception, e:
            self.exception('problem with analysis')

        # send confirmation AFTER any error messages
        message.respond(confirmation)
        self.debug('sent confirmation')

    def unmatched(self, message):
        message.respond(_("invalid-message"))

    kw.prefix = ['cancel', 'can']
    @kw("(\d+?) (\d+?) (\d+?)")
    def cancel_report(self, message, cluster, child, household):
        try:
            patient = Person.objects.get(cluster_id=cluster,\
                        household_id=household, code=child)
            ass = patient.latest_assessment()
            if ass is not None:
                ass.cancel()
                message.respond(_("cancel-confirm") % (ass.healthworker.name, ass.healthworker.interviewer_id, ass.date, patient.cluster_id, patient.code, patient.household_id))
            else:
                message.respond(_("cancel-error") % (child, household, cluster))
        except ObjectDoesNotExist:
            message.respond(_("cancel-error") % (child, household, cluster))


    kw.prefix = ['register', 'reg']
    @kw("(\d+?) (.*?)")
    def register_healthworker(self, message, code, name):
        self.debug("register...")
        try:
            healthworker, created = self.__register_healthworker(message, code, name)
            if created:
                message.respond(_("register-confirm") % (healthworker.name, healthworker.interviewer_id))
            else:
                message.respond(_("register-again") % (healthworker.name))
        except Exception, e:
            self.exception("oops! problem registering healthworker")
            message.respond(_("invalid-message"))
            pass

    @kw("remove (\d+?)")
    def remove_healthworker(self, message, code):
        self.debug("removing...")
        try:
            healthworker = Contact.objects.get(interviewer_id=code)
            healthworker.status = 'I'
            healthworker.save()
            message.respond(_("remove-confirm") % (healthworker.name, healthworker.interviewer_id))
            healthworker.interviewer_id = None
            healthworker.save()
        except Exception, e:
            message.respond(_("invalid-message"))
            self.exception()
