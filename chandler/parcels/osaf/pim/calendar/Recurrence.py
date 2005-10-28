""" Classes used for recurrence"""

__revision__  = "$Revision$"
__date__      = "$Date$"
__copyright__ = "Copyright (c) 2003-2005 Open Source Applications Foundation"
__license__   = "http://osafoundation.org/Chandler_0.1_license_terms.htm"
__parcel__ = "osaf.pim.calendar"

from application import schema
from osaf.pim import items
from datetime import datetime, timedelta
import dateutil.rrule
from dateutil.rrule import rrule, rruleset
from repository.item.PersistentCollections import PersistentList
from PyICU import ICUtzinfo, DateFormat
from TimeZone import coerceTimeZone, forceToDateTime
from i18n import OSAFMessageFactory as _
from DateTimeUtil import datetimeOp

class FrequencyEnum(schema.Enumeration):
    """The base frequency for a recurring event."""
    schema.kindInfo(
        displayName=u"Frequency"
    )
    values="yearly","monthly","weekly","daily","hourly","minutely","secondly"


class WeekdayEnum(schema.Enumeration):
    """The names of weekdays."""
    schema.kindInfo(
        displayName=u"Weekdays"
    )
    #XXX[i18n] Should these values should come from PyICU?
    #          Are they used for lookup or display?
    values="monday","tuesday","wednesday","thursday","friday", \
           "saturday","sunday"

weekdayAbbrevMap = dict(monday    = _(u"Mo"),
                        tuesday   = _(u"Tu"),
                        wednesday = _(u"We"),
                        thursday  = _(u"Th"),
                        friday    = _(u"Fr"),
                        saturday  = _(u"Sa"),
                        sunday    = _(u"Su"))

singularFrequencyMap = dict(yearly  = _(u"year"),
                            monthly = _(u"month"),
                            weekly  = _(u"week"),
                            daily   = _(u"day"),
                            hourly  = _(u"hour"),
                            minutely = _(u"minute"),
                            secondly = _(u"second"))

pluralFrequencyMap =   dict(yearly  = _(u"years"),
                            monthly = _(u"months"),
                            weekly  = _(u"weeks"),
                            daily   = _(u"days"),
                            hourly  = _(u"hours"),
                            minutely = _(u"minutes"),
                            secondly = _(u"seconds"))


class WeekdayAndPositionStruct(schema.Struct):
    """Weekday and an integer selecting the first, last, etc. day.

    Use selector=0 for all days equal to weekday.

    """
    __slots__ = "weekday", "selector"
    # schema.kindInfo(
#         displayName=u"Weekday and position"
#     )

def toDateUtilWeekday(enum):
    return getattr(dateutil.rrule, enum[0:2].upper())

def toDateUtilFrequency(enum):
    return getattr(dateutil.rrule, enum.upper())

def toDateUtilStruct(structlist):
    outlist = []
    for struct in structlist:
        day=toDateUtilWeekday(struct.weekday)
        if struct.selector == 0: # dateutil's weekday doesn't like 0
            outlist.append(day)
        else:
            outlist.append(day(struct.selector))
    return outlist

def toDateUtil(val):
    #what's the proper way to dispatch, particularly for the struct?
    if type(val) == PersistentList: return toDateUtilStruct(val)
    elif val in FrequencyEnum.values: return toDateUtilFrequency(val)
    elif val in WeekdayEnum.values: return toDateUtilWeekday(val)

def fromDateUtilWeekday(val):
    #hack!
    return WeekdayEnum.values[val]

def fromDateUtilFrequency(val):
    #hack!
    return FrequencyEnum.values[val]

class RecurrenceRule(items.ContentItem):
    """One rule defining recurrence for an item."""
    freq = schema.One(
        FrequencyEnum,
        displayName=u"Frequency possibilities",
        defaultValue="weekly"
    )
    isCount = schema.One(
        schema.Boolean,
        displayName = u"isCount",
        doc = "If True, calculate and export count instead of until",
        defaultValue = False
    )
    until = schema.One(
        schema.DateTime,
        displayName=u"Until",
    )
    untilIsDate = schema.One(
        schema.Boolean,
        displayName = u"untilIsDate",
        doc = "If True, treat until as an inclusive date, use until + 23:59 "
              "for until",
        defaultValue = True
    )
    interval = schema.One(
        schema.Integer,
        displayName=u"Interval",
        defaultValue=1
    )
    wkst = schema.One(
        WeekdayEnum,
        displayName=u"Week Start Day",
        defaultValue=None
    )
    bysetpos = schema.Sequence(
        schema.Integer,
        displayName=u"Position selector",
        defaultValue=None
    )
    bymonth = schema.Sequence(
        schema.Integer,
        displayName=u"Month selector",
        defaultValue=None
    )
    bymonthday = schema.Sequence(
        schema.Integer,
        displayName=u"Ordinal day of month selector",
        defaultValue=None
    )
    byyearday = schema.Sequence(
        schema.Integer,
        displayName=u"Ordinal day of year selector",
        defaultValue=None
    )
    byweekno = schema.Sequence(
        schema.Integer,
        displayName=u"Week number selector",
        defaultValue=None
    )
    byweekday = schema.Sequence(
         WeekdayAndPositionStruct,
         displayName=u"Weekday selector",
        defaultValue=None
    )
    byhour = schema.Sequence(
        schema.Integer,
        displayName=u"Hour selector",
        defaultValue=None
    )
    byminute = schema.Sequence(
        schema.Integer,
        displayName=u"Minute selector",
        defaultValue=None
    )
    bysecond = schema.Sequence(
        schema.Integer,
        displayName=u"Second selector",
        defaultValue=None
    )
    rruleFor = schema.One('RecurrenceRuleSet', inverse='rrules')
    exruleFor = schema.One('RecurrenceRuleSet', inverse='exrules')

    schema.addClouds(
        sharing = schema.Cloud(freq, isCount, until, untilIsDate, interval,
            wkst, bysetpos, bymonth, bymonthday, byyearday, byweekno,
            byweekday, byhour, byminute, bysecond)
    )

    normalNames = "interval", "until"
    listNames = ("bysetpos", "bymonth", "bymonthday", "byyearday", "byweekno",
                 "byhour", "byminute", "bysecond")
    specialNames = "wkst", "byweekday", "freq"

    notSpecialNames = ("interval", "until", "bysetpos", "bymonth", "bymonthday",
                       "byyearday","byweekno", "byhour", "byminute", "bysecond")
    
    allNames = ("interval", "until", "bysetpos", "bymonth", "bymonthday",
                "byyearday","byweekno", "byhour", "byminute", "bysecond",
                "wkst", "byweekday", "freq")

    # dateutil automatically sets these from dtstart, we don't want these
    # unless their length is greater than 1.
    interpretedNames = "byhour", "byminute", "bysecond"

    def calculatedUntil(self):
        """
        Return until or until + 23:59, depending on untilIsDate. 
        Will return None if there's no 'until' (so don't assume you can
        compare this value with a datetime directly!)
        """
        try:
            until = self.until
        except AttributeError:
            return None

        if self.untilIsDate:
            return until.replace(hour=23, minute=59)
        else:
            return until
            

    def createDateUtilFromRule(self, dtstart):
        """Return an appropriate dateutil.rrule.rrule."""

        tzinfo = dtstart.tzinfo

        def coerceIfDatetime(value):
            if isinstance(value, datetime):
                value = coerceTimeZone(value, tzinfo)
            return value

        # TODO: more comments
        kwargs = dict((k, getattr(self, k, None)) for k in self.notSpecialNames)
        for key in self.specialNames:
            value = coerceIfDatetime(getattr(self, key))
            if value is not None:
                kwargs[key]=toDateUtil(value)
        if hasattr(self, 'until'):
            kwargs['until'] = coerceIfDatetime(self.calculatedUntil())
        rule = rrule(dtstart=dtstart, **kwargs)
        if not self.isCount or not hasattr(self, 'until'):
            return rule
        else:
            # modifying in place may screw up cache, fix when we turn
            # on caching
            rule._count =  rule.count()
            rule._until = None
            return rule       

    def setRuleFromDateUtil(self, rrule):
        """Extract attributes from rrule, set them in self."""
        self.untilIsDate = False
        until = None # assume no limit
        if rrule._count is not None:
            self.isCount = True
            until = rrule[-1]
        self.wkst = fromDateUtilWeekday(rrule._wkst)
        self.freq = fromDateUtilFrequency(rrule._freq)

        # ignore byweekday if freq is WEEKLY and day correlates with dtstart
        # because it was automatically set by dateutil
        if rrule._freq != dateutil.rrule.WEEKLY or \
           len(rrule._byweekday) != 1 or \
           rrule._dtstart.weekday() != rrule._byweekday[0]:
            listOfDayTuples = []
            if rrule._byweekday:
                # Day tuples are (dayOrdinal, n-th week of the month),
                # 0 means all weeks
                listOfDayTuples=[(day, 0) for day in rrule._byweekday]
            if rrule._bynweekday is not None:
                listOfDayTuples.extend(rrule._bynweekday)
            if len(listOfDayTuples) > 0:
                self.byweekday = []
                for day, n in listOfDayTuples:
                    day = fromDateUtilWeekday(day)
                    self.byweekday.append(WeekdayAndPositionStruct(day, n))
        if rrule._until is not None:
            until = rrule._until    
        if rrule._interval != 1:
            self.interval = rrule._interval
        if until is None:
            if self.hasLocalAttributeValue('until'):
                del self.until
        else:
            if until.tzinfo is None:
                self.until = until
            else:
                self.until = coerceTimeZone(until, ICUtzinfo.getDefault())
            
        for key in self.listNames:
            # TODO: cache getattr(rrule, '_' + key)
            if getattr(rrule, '_' + key) is not None and \
                                        (key not in self.interpretedNames or \
                                         len(getattr(rrule, '_' + key)) > 1):
                # cast tuples to list
                setattr(self, key, list(getattr(rrule, '_' + key)))
        # bymonthday and bymonth may be set automatically by dateutil, if so, 
        # unset them
        if rrule._freq in (dateutil.rrule.MONTHLY, dateutil.rrule.YEARLY):
            if len(rrule._bymonthday) == 1:
                if rrule._bymonthday[0] == rrule._dtstart.day:
                    del self.bymonthday
        if rrule._freq == dateutil.rrule.YEARLY:
            if len(rrule._bymonth) == 1:
                if rrule._bymonth[0] == rrule._dtstart.month:
                    del self.bymonth


    def onValueChanged(self, name):
        """If the rule changes, update any associated events."""
        if name in self.allNames:
            for ruletype in ('rruleFor', 'exruleFor'):
                if self.hasLocalAttributeValue(ruletype):
                    getattr(self, ruletype).onValueChanged('rrules')


class RecurrenceRuleSet(items.ContentItem):
    rrules = schema.Sequence(
        RecurrenceRule,
        displayName=u"Recurrence rules",
        inverse = RecurrenceRule.rruleFor,
        deletePolicy = 'cascade'
    )
    exrules = schema.Sequence(
        RecurrenceRule,
        displayName=u"Exclusion rules",
        inverse = RecurrenceRule.exruleFor,
        deletePolicy = 'cascade'
    )
    rdates = schema.Sequence(
        schema.DateTime,
        displayName=u"Recurrence Dates"
    )
    exdates = schema.Sequence(
        schema.DateTime,
        displayName=u"Exclusion Dates"
    )
    events = schema.Sequence(
        "osaf.pim.calendar.Calendar.CalendarEventMixin",
        displayName=u"Events",
        inverse="rruleset"
    )
 
    schema.addClouds(
        copying = schema.Cloud(rrules, exrules, rdates, exdates),
        sharing = schema.Cloud(exdates, rdates, byCloud = [exrules, rrules])
    )

    def addRule(self, rule, rrulesorexrules='rrules'):
        """Add an rrule or exrule, defaults to rrule."""
        try:
            getattr(self, rrulesorexrules).append(rule)
        except AttributeError:
            setattr(self, rrulesorexrules, [rule])
        
    def createDateUtilFromRule(self, dtstart):
        """Return an appropriate dateutil.rrule.rruleset."""
        ruleset = rruleset()
        for rtype in 'rrule', 'exrule':
            for rule in getattr(self, rtype + 's', []):
                getattr(ruleset, rtype)(rule.createDateUtilFromRule(dtstart))
        for datetype in 'rdate', 'exdate':
            for date in getattr(self, datetype + 's', []):
                date = coerceTimeZone(date, dtstart.tzinfo)
                getattr(ruleset, datetype)(date)
        return ruleset

    def setRuleFromDateUtil(self, ruleSetOrRule):
        """Extract rules and dates from ruleSetOrRule, set them in self.
        
        If a dateutil.rrule.rrule is passed in instead of an rruleset, treat
        it as the new rruleset.
        
        """
        if isinstance(ruleSetOrRule, rrule):
            set = rruleset()
            set.rrule(ruleSetOrRule)
            ruleSetOrRule = set
        elif not isinstance(ruleSetOrRule, rruleset):
            raise TypeError, "ruleSetOrRule must be an rrule or rruleset"
        for rtype in 'rrule', 'exrule':
            rules = getattr(ruleSetOrRule, '_' + rtype, [])
            if rules is None: rules = []
            itemlist = []
            for rule in rules:
                ruleItem=RecurrenceRule()
                ruleItem.setRuleFromDateUtil(rule)
                itemlist.append(ruleItem)
            setattr(self, rtype + 's', itemlist)
        for typ in 'rdate', 'exdate':
            datetimes = [forceToDateTime(d) for d in getattr(ruleSetOrRule, '_' + typ, [])]
            setattr(self, typ + 's', datetimes)
    
    def isComplex(self):
        if hasattr(self, 'rrules'):
            if len(self.rrules) != 1:
                return True # multiple rules
            for recurtype in 'exrules', 'rdates':
                if self.hasLocalAttributeValue(recurtype) and \
                       len(getattr(self, recurtype)) != 0:
                    return True # more complicated rules
            rule = self.rrules.first()
            for attr in RecurrenceRule.listNames:
                if getattr(rule, attr) not in (None, []):
                    return True
            if rule.byweekday is not None:
                # treat nth weekday of the month as complex
                for daystruct in rule.byweekday:
                    if daystruct.selector != 0:
                        return True
            return False 
        else:
            return True
        

    def isCustomRule(self):
        """Determine if this is a custom rule.
        
        For the moment, simple daily, weekly, or monthly repeating events, 
        optionally with an UNTIL date, or the abscence of a rule, are the only
        rules which are not custom.
        
        """
        if self.isComplex():
            return True
        # isComplex has already tested for most custom things, but
        # not intervals greater than 1 and multiple weekdays
        rule = self.rrules.first()
        if rule.interval != 1:
            return True
        elif rule.byweekday:
            return True
        else:
            return False

    def getCustomDescription(self):
        """Return a string describing custom rules."""
        if self.isComplex():
            return _(u"complex rule - no description available")
        else:
            rule = self.rrules.first()
            freq = rule.freq
            interval = rule.interval
            
            #@@@ This would be tricky to internationalize, bug 4464
            dct = {}
            dct['weekdays'] = u""
            if freq == 'weekly' and rule.byweekday is not None:
                daylist = [weekdayAbbrevMap[i.weekday] for i in rule.byweekday]
                if len(daylist) > 0:
                    daylist.append(u" ")
                    dct['weekdays'] = u"".join(daylist)
                    
            if rule.interval != 1:
                dct['interval'] = str(rule.interval)
                dct['freq'] = pluralFrequencyMap[freq]
            else:
                dct['interval'] = u""
                dct['freq'] = singularFrequencyMap[freq]
                
            until = rule.calculatedUntil()
            if until is None:
                dct['until'] = u""
            else:
                formatter = DateFormat.createDateInstance(DateFormat.kShort)
                dct['until'] = _(u"until ") + unicode(formatter.format(until))
            
            return "%(weekdays)severy %(interval)s %(freq)s %(until)s" % dct
            

    def moveDatesAfter(self, after, delta):
        """
        Move dates (later than "after") in exdates and rdates by delta.
        """
        self._ignoreValueChanges = True
        for datetype in 'rdates', 'exdates':
            datelist = getattr(self, datetype, None)
            if datelist is not None:
                l = []
                for dt in datelist:
                    if datetimeOp(dt, ">=", after):
                        l.append(dt + delta)
                    else:
                        l.append(dt)
                setattr(self, datetype, l)
        del self._ignoreValueChanges


    def removeDates(self, cmp, endpoint):
        """
        Remove dates in exdates and rdates before or after endpoint.
        """
        for datetype in 'rdates', 'exdates':
            datelist = getattr(self, datetype, None)
            if datelist is not None:
                for i, dt in enumerate(datelist):
                    if datetimeOp(dt, cmp, endpoint):
                        self._ignoreValueChanges = True
                        del datelist[i]
                        self._ignoreValueChanges = False

    def moveRuleEndBefore(self, end):
        """
        Make self's rules end one minute before end.
        """
        newend = end - timedelta(minutes=1)
        #change the rule, onValueChanged will trigger cleanRule for master
        for rule in getattr(self, 'rrules', []):
            if not rule.hasLocalAttributeValue('until') or \
               datetimeOp(rule.calculatedUntil(), '>', newend):
                rule.until = newend
                rule.untilIsDate = False
        self.removeDates('>', newend)

    RULENAMES = ('rrules', 'exrules', 'rdates', 'exdates')

    def onValueChanged(self, name):
        """If the RuleSet changes, update the associated event."""
        if name in self.RULENAMES and not getattr(self, '_ignoreValueChanges', False):
            if self.hasLocalAttributeValue('events'):
                for event in self.events:
                    event.getFirstInRule().cleanRule()
                    # assume we have only one conceptual event per rrule
                    break
                
