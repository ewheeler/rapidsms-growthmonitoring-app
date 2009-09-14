#!/usr/bin/env python
EXCEPT_MSG = {"NO_PERSON":"Person Not Found",
             "NO_REPORTER":"Reporter Not Found",
             "NO_CONNECTION":"Connection Not Found"}
         
ERROR_MSG = {}
RESPONSE_MSG = {}

CHILD_HEALTH_STATUS = [
		 ("NA","NA"),
		 ("NAM",""),
                 ("MAM","Moderate Malnutrition"),
                 ("SAM","Severe Malnutrition"),
                 ("W","Wasting"),
                 ("S","Stunting")]

CHILD_HEALTH_STATUS_BOOL={
	(True,False):"MAM",
	(False,True):"SAM",
	(False,False):"NAM"}
DATA_QUALITY_TYPES =[("None",1),
        ("Clean",2),
        ("Error",3)]

SMS_RESPONSE = {
    "HELP":\
           "<REPORT> gmc_id hsa_id child_id wt ht muac oedema(Y/N) diarrhea(Y/N)<br>\
            <CANCEL> gmc_id child_id<br>\
            <NEW> gmc_id child_id gender(M/F) age(month) contact#\
            <HSA> gmc_id hsa_id\
            <EXIT> gmc_id child_id",\
    "REPORT_SUCCESS":"",\
    "REPORT_FAIL":"",\
    "CANCEL_SUCCESS":"",\
    "CANCEL_FAIL":"",\
    "EXIT_SUCCESS":"",\
    "EXIT_FAIL":"",\
    "NEW_SUCCESS":"",\
    "NEW_FAIL":"",\
    "HSA_SUCCESS":"",\
    "HSA_FAIL":""}
