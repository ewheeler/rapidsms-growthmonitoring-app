#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

import datetime

from tables import stunting_boys, stunting_girls
from tables import weight_for_height as weight_for_height_table

####
#
#  TODO the below functions are from andymckay's malnutrition work
#       and the SAM/MAM stuff in childhealth/models.py (on the
#       Assessment model) should be ported to use these functions
#       as well as the flat data files rather than having the
#       overhead of a HealthTables app 
#
####

    @staticmethod
    def years_months(date):
        now = datetime.now().date()
        ymonths = (now.year - date.year) * 12
        months = ymonths + (now.month - date.month)
        return (now.year - date.year, months)
        
    @staticmethod
    def stunting(date, gender):
        assert gender.lower() in ["m", "f"]
        years, months = years_months(date)
        # we have a month eg: 9, so we assume that is 8.5, since
        # it can't be 9.5... assuming the .5's are there to make sure that
        if int(months) > 73:
            raise ValueError, "Stunting charts only go as high as 72.5 months"
        elif int(months) >= 1:
            months = str(int(months) - 0.5)
        else:
            # lowest bound
            months = 0
            
        if gender.lower() == "m":
            stunts = stunting_boys.data
        else:
            stunts = stunting_girls.data
        return stunts[months]

    @staticmethod
    def _dumb_round(number):
        # please improve
        assert isinstance(number, (float, int)), "Got a %s, which is a: %s" % (number, type(number)) # forget duck typing, this won't work on anything else
        remainder = number - int(number)
        if remainder >= 0.5:
            remainder = 0.5
        else:
            remainder = 0.0
        return int(number) + remainder

    range_strs = ["60%-", "70%-60%","75%-70%", "80%-75%","85%-80%","100%-85%"]

    @staticmethod
    def _get_range_str(value, targets):
        targets.reverse()
        result = "60%-"
        for text, target in zip(range_strs, targets):
            target = float(target)
            if value >= target:
                result = text
        return result
        
    @staticmethod
    def weight_for_height(height, weight):
        weight = float(weight)
        number = _dumb_round(height)
        
        if number < 49.0:
            # raise ValueError, "Weight for height charts only go as low as 85.0, got height %s." % height
            return None
        elif number > 130.0:
            # raise ValueError, "Weight for height charts only go as high as 130.0, got height %s." % height
            return None
            
        targets = weight_for_height_data.data[str(number)][:]
        return _get_range_str(weight, targets)
