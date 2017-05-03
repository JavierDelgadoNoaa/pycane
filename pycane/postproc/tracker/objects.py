import logging 
import operator as op
import math
from datetime import datetime as dtime
from datetime import timedelta as tdelta

from geopy.distance import great_circle

from pycane.postproc.tracker import utils as trkutils
from pycane.timing import conversions

'''
This module contains objects that encapsulate tracker data from
different trackers. It also contains objects that are essentially
structures for holding TC error stats and NatureRun track data.

The tracks are encapsulated in an object oriented fassion, as follows.

ForecastTrack
     |
     |___TrackerData array for each output time (currently limited to hourly)

Javier.Delgado@noaa.gov
'''

def to_datetime(tim):
    if isinstance(tim, dtime): return tim
    #import pdb ; pdb.set_trace()
    sd = dtime.fromtimestamp(float(tim)) #.strftime('%c')
    return sd

class ForecastTrack:
    '''
    This class encapsulates tracker data for a particular Forecast.
    Its parameter contains a list of TrackerData entries containing
    data for each output in the forecast that was processed by the tracker.
    e.g. if outputs were generated every 3 hours and the tracker was 
    set to read every 3 hours, the ATCF would have 3-hourly output and
    hence there would be (forecast_length/3) + 1 elements in 
    `tracker_entries' member variable.
    '''
    def __init__(self, startDate, center="NA", stormName="UNNAMED", 
                 stormNumber=99, stormBasin=" "):
        if isinstance(startDate, dtime):
             #datestr = "{0:%Y%m%d%H%M%S}".format(startDate)
             #self.start_date = conversions.yyyymmddHHMMSS_to_epoch(datestr)
             self.start_date = "{0:%s}".format(startDate)
        else:
            self.start_date = startDate
        self.tracker_entries = []
        self.originating_center = center
        self.storm_name = stormName
        self.storm_number = stormNumber
        self.basin = stormBasin
        
    def append_entry(self, atcf_linedat):
        '''
        Append a <TrackerData> object to the <data> array
        @param atcf_linedat Data from an entry (i.e. one line) of ATCF data
        '''
        self.tracker_entries.append(atcf_linedat)
    
    
    def get_tracker_entries(self):
        ''' 
        Return list of <TrackerData> associated with this ForecastTrack
        object
        '''
        return self.tracker_entries
    
    
    def absolute_times_dict(self):
        '''
        Return a dictionary that maps each absolute time of each tracker entry
        to the entry itself.
        '''
        d = {}
        for entry in self.tracker_entries:
            # TODO : minutes
            # TODO ; datetime
            d[self.start_date + entry.fhr*3600] = entry
        return d
        
    @property 
    def fhr_dict(self):
        '''
        Return a dictionary thta maps each forecast hour of each tracker entry
        to the entry itself
        '''
        d = {}
        for entry in self.tracker_entries:
            d[entry.fhr] = entry
        return d
        
    @property        
    def fcst_date_dict(self):
        d = {}
        for entry in self.tracker_entries:
            d[entry.fcst_date] = entry
        return d

    def __repr__(self):
        s = ''
        for d in self.tracker_entries:
            s += `d`
        return  s

    def dump_gfdltrk_fort12(self, outfile=None, fhr=0):
        """
        Dump the fort.12 file expected by the gfdl tracker, for the given
        `fhr' (default 0). This consists of a single line like so:
        AOML 01L ONEARW01L 20050801 0600 167N  400W -99 -99  998 -999 -999 -9 -99 -999 -999 -999 -999 X
        [center]   [storm name]     [hhmm]     [cenlon] [wind spd]        [rest will all be -9* (ignored)]
             [storm id]     [ymd]       [cenlat]   [wind dir] [mslp]
               
        See also: http://www.emc.ncep.noaa.gov/mmb/data_processing/tcvitals_description.htm
        """
        center = self.originating_center if self.originating_center else "ACME"
        basin = self.basin if self.basin else "99"
        storm_number = self.storm_number if self.storm_number else 0
        storm_name = self.storm_name if self.storm_name else "  UNNAMED"
        storm_name = storm_name.rjust(9)
        startDate = to_datetime(self.start_date) 
        fcstDate = startDate + tdelta(hours=fhr)
        fcstYMD = "{0:%Y%m%d}".format(fcstDate)
        fcstHHMM = "{0:%H%M}".format(fcstDate)
        trkentry = self.fcst_date_dict[fcstDate]
        latstr = str(abs(int(round(trkentry.lat*10,0))))
        lonstr = str(abs(int(round(trkentry.lon*10,0))))
        if trkentry.lat < 0 : latstr += "S"
        else: latstr += "N"
        if trkentry.lon < 0: lonstr += "W"
        else: lonstr += "E"
        latstr = latstr.rjust(4)
        lonstr = lonstr.rjust(5)
        
        windspeed_kts = trkentry.maxwind_value # TODO : assuming maxwind is in kts but this is not enforced by object
        windspeed_mps = windspeed_kts * 0.51444444444
        windspeed_str = str(int(round(windspeed_mps*10,0))).rjust(3)
        mslp = str(int(round(trkentry.mslp_value,0))).rjust(4)
        
        #import pdb ;pdb.set_trace()
        dataType = "03" # fcst data
        atcfName = "9999" #5
        s = "{center} {snum:02d}{basinId} {name} {fdate:%Y%m%d %H%M} {latstr} {lonstr}"\
            " {spd} -99 {mslp} -999 -999 -9 -99 -999 -999 -999 -999 X"\
            .format(center=center, snum=storm_number, basinId=basin, 
                    name=storm_name, fdate=fcstDate,
                    latstr=latstr, lonstr=lonstr, spd=windspeed_str, mslp=mslp)
        
        if outfile: 
            with open(outfile, 'w') as f:
                f.write(s + "\n")

        return s
        #s = []
        #for entry in self.tracker_entries:
        #    fcstOffset = entry.fhr * 100
        #    s.append("{center} {sid:02d}{basinId} {startDate:%Y%m%d%H} {dataType} {atcfName} {fcstOffset}"
        #             .format())
        #ret = "".join(s)

class ForecastTrackDiff(object):
    '''
    This class represents the difference of two ForecastTrack objects. 
    Internally, it behaves like a ForecastTrack object in that it contains
    a `start_date' and a list of `tracker_entries'
    '''
    def __init__(self, trackOne, trackTwo, absoluteTimeDiff=True,
                 operator=op.sub, include_flagged=True, log=None, 
                 absolute=False):
        '''
        Instantiate the object, taking the difference of `trackOne' and 
        `trackTwo'. 
        @param trackOne The first track
        @param trackTwo The second track, whose MSLP, maxwind, and position
               will be _subtracted from_ trackOne, for each tracker entry
               that exists in each
        @param absoluteTimeDiff if True, the difference will be relative 
            to the absolute time (i.e. analysis_date + fhr + fcst_min).
            If False, the difference will be relative to the forecast lead time
            (i.e. fhr + fcst_min)
        @param operator The operator to use to get the difference. By default,
                do a basic subtraction. Should point to a function that 
                has trackOne as the first arg and trackTwo as the second arg
        @param include_flagged If True, do not skip flagged tracker entries
        @param log Logger to use. If not passed, use the root logger
        @param absolute If True, calculate absolute value of the error
        '''
        self.track_one = trackOne
        self.track_two = trackTwo
        self.start_date = self.track_one.start_date
        self.absolute_time_difference = absoluteTimeDiff
        self.tracker_entries = []
        self.operator = operator
        self.absolute = absolute
        self.include_flagged = include_flagged
        if log is None:
            log = logging.getLogger()
        self.log = log
        self._get_track_diffs()

    def _get_track_diffs(self):
        '''
        Get a time-by-time difference of MSLP, maxwind, and position (in km)
        difference between self.track_one and self.track_two (trackOne - trackTwo)
        For position, use the great circle difference.
        If self.absolute_time_difference, time will be the absolute/wall time. 
        Otherwise, it will be the lead time.
        For each entry's corresponding TrackerDataDiff, the `fhr' field will 
        correspond to that of self.track_one. The `flagged' entry will be True
         if either of the tracker entries is. 
        '''
        for trkOneEntry in self.track_one.tracker_entries:
            # Get the corresponding entry for track_two
            if self.absolute_time_difference:
                trkTwoDict = self.track_two.absolute_times_dict()
                # TODO datetime - next two lines
                if not trkTwoDict.has_key(trkOneEntry.get_fhr_epoch()): 
                    timeStr = conversions.\
                        epoch_to_pretty_time_string(trkOneEntry.get_fhr_epoch())  
                    msg = "track_two does not have corresponding ATCF entry "\
                           "at time %s" %(timeStr)
                    self.log.debug(msg)
                    continue
                trkTwoEntry = trkTwoDict[trkOneEntry.get_fhr_epoch()]
            else: 
                # get difference relative to lead time
                trkTwoDict = self.track_two.fhr_dict()
                if not trkTwoDict.has_key[trkOneEntry.fhr]:
                    msg = "track_two does not have corresponding ATCF entry "\
                          "for forecast hour %s" %trkOneEntry.fhr 
                    self.log.debug(msg)
                    continue    
                trkTwoEntry = trkTwoDict[trkOneEntry.fhr]
            # check if it should be flagged
            flagged = False
            if trkTwoEntry.flagged or trkOneEntry.flagged:
                if not self.include_flagged:
                    continue
                flagged = True
            # calculate diff and append the TrackerDataDiff to tracker_entries
            latlonOne = (trkOneEntry.lat, trkOneEntry.lon)
            latlonTwo = (trkTwoEntry.lat, trkTwoEntry.lon)
            positionDiff = great_circle(latlonOne, latlonTwo).kilometers
            mslpDiff = self.operator(trkOneEntry.mslp_value,
                                     trkTwoEntry.mslp_value)
            maxwindDiff = self.operator(trkOneEntry.maxwind_value, 
                                        trkTwoEntry.maxwind_value)
            if self.absolute:
                mslpDiff = abs(mslpDiff)
                maxwindDiff = abs(maxwindDiff)

            self.tracker_entries.append(
                TrackerDataDiff(trkOneEntry.fhr,
                                flagged,
                                positionDiff,
                                mslpDiff,
                                maxwindDiff))
            
    
class TrackerData:
    '''
    This class encapsulates the data generated by the tracker for a
    particular output time. It is limited to hourly granularity
    '''
    def __init__(self, startDate, fhr, flagged, lat, lon, mslp, maxwind, 
                 fcstDate=None):
        self.start_date = startDate
        self.fhr = fhr
        if str(flagged) == '0' or str(flagged) == 'False':
            self.flagged = False
        elif str(flagged) == '1' or str(flagged) == 'True':
            self.flagged = True
        else:
            print 'Unable to determine Flag status'
            sys.exit(1)
        self.lat  = lat
        self.lon = lon
        self.mslp_value = mslp
        self.maxwind_value = maxwind
        #self.mslp = mslp
        #self.maxwind = maxwind

        if fcstDate:
            self.fcst_date = fcstDate
        elif fhr is not None:
            if not isinstance(self.start_date, dtime):
                # TODO : Shoudl be datetime going forward, so shouldn't need this
                #sd = dtime.fromtimestamp(self.start_date).strftime('%c')
                sd = dtime.fromtimestamp(self.start_date)
                self.fcst_date = sd + tdelta(hours=fhr)
            else:
                self.fcst_date = self.start_date + tdelta(hours=fhr)
            
    def get_fhr_epoch(self):
        '''
        Gets absolute time of this tracker entry, in seconds since epoch,
        using start_date and fhr
        '''
        return self.start_date + (self.fhr * 3600 )

    def __repr__(self):
        fhr = "n/a" if self.fhr is None else self.fhr
        #return '(fhr: %i, flagged: %s, lat: %s, lon: %s, mslp: %s, maxwind: %s)' %(fhr, self.flagged, self.lat, self.lon, self.mslp_value, self.maxwind_value)
        return '(fdate: %s, fhr: %s, flagged: %s, lat: %s, lon: %s, mslp: %s, maxwind: %s)'\
               %(self.fcst_date, fhr, self.flagged, self.lat, self.lon, self.mslp_value, self.maxwind_value)


class TrackerDataDiff(object):
    '''
    Structure to encapsulate the position, mslp, and maxwind differences 
    between two TrackerData objects
    '''
    def __init__(self, fhr, flagged, position, mslp, maxwind):
        self.fhr = fhr
        self.flagged = flagged
        self.track_error = position 
        self.mslp_error = mslp 
        self.maxwind_error = maxwind
        
    def __repr__(self):
        return 'flagged: %s , track error: %f , maxwind_error: %f, mslp error: %f' %(self.flagged, self.track_error, self.maxwind_error, self.mslp_error)
        
class ForecastTCVError:
    def __init__(self, startDate):
        self.start_date = startDate
        # These are generally TCVErrorData elements
        self.tracker_entries = []
    def append_entry(self, diapost_data):
        '''
        Append a <TCVErrorData> object to the <data> array
        '''
        self.tracker_entries.append(diapost_data)
    def get_tracker_entries(self):
        ''' Return list of <TCVErrorData> associated with this  object'''
        return self.tracker_entries

    def __repr__(self):
        s = ''
        for d in self.tracker_entries:
            s += `d`
        return  s


class TCVErrorData:
    ''' Simple  Class to store TC error statistics '''
    def __init__(self, cycle, fhr, flagged, trackError, maxwindError, mslpError):
        self.cycle = cycle
        self.fhr = fhr
        if str(flagged) == '0' or str(flagged) == 'False':
            self.flagged = False
        elif str(flagged) == '1' or str(flagged) == 'True':
            self.flagged = True
        else:
            raise ValueError('Unable to determine Flag status')
        self.track_error = trackError
        self.maxwind_error = maxwindError
        self.mslp_error = mslpError
    def __repr__(self):
        return 'flagged: %s , track error: %f , maxwind_error: %f, mslp error: %f' %(self.flagged, self.track_error, self.maxwind_error, self.mslp_error)

class NatureTrack:
    '''
    Designed for OSSE experiments, this class encapsulates the track parameters
    for a nature run
    '''
    def __init__(self, date, lat, lon, mslp, maxwind):
        self.output_date = date
        self.lat = lat
        self.lon = lon
        self.mslp_value = mslp
        self.maxwind_value = maxwind



