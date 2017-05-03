#!/usr/bin/env python

import os
import time
from math import sqrt, ceil
import math
import sys
import logging
import gzip
from datetime import datetime as dtime
from datetime import timedelta as tdelta

from pycane.timing import conversions

'''

Contains functions for reading tracker data from output files generated
by different trackers. The functions are designed to return the 
tracker-agnostic objects in the `objects' module

Javier.Delgado@noaa.gov

'''

#
# DEFINE CONSTANTS
#

# Diapost fcst_track file index values
DIAPOST_TRACK_FILE_START_DATE_IDX = 0
DIAPOST_TRACK_FILE_FHR_IDX = 1
DIAPOST_TRACK_FILE_FLAG_IDX = 3
DIAPOST_TRACK_FILE_LAT_IDX = 5
DIAPOST_TRACK_FILE_LON_IDX = 4
DIAPOST_TRACK_FILE_MSLP_IDX = 6
DIAPOST_TRACK_FILE_maxwind_KTS_IDX = 7

DIAPOST_MAXWIND_UNITS = 'kts'
DIAPOST_MSLP_UNITS = 'mb'


def _great_circle_distance(latlong_a, latlong_b):
    """
    Return the great circle distance between two lat/lon points,
    in meters.
    NOTE: This is no longer used. Using function built into geopy instead
    Copied from https://gist.github.com/gabesmed/1826175
    >>> coord_pairs = [
    ...     # between eighth and 31st and eighth and 30th
    ...     [(40.750307,-73.994819), (40.749641,-73.99527)],
    ...     # sanfran to NYC ~2568 miles
    ...     [(37.784750,-122.421180), (40.714585,-74.007202)],
    ...     # about 10 feet apart
    ...     [(40.714732,-74.008091), (40.714753,-74.008074)],
    ...     # inches apart
    ...     [(40.754850,-73.975560), (40.754851,-73.975561)],
    ... ]

    >>> for pair in coord_pairs:
    ...     great_circle_distance(pair[0], pair[1]) # doctest: +ELLIPSIS
    83.325362855055...
    4133342.6554530...
    2.7426970360283...
    0.1396525521278...
    """

    EARTH_RADIUS = 6378137 # meters

    lat1, lon1 = latlong_a
    lat2, lon2 = latlong_b

    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = (math.sin(dLat / 2) * math.sin(dLat / 2) +
            math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
            math.sin(dLon / 2) * math.sin(dLon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    d = EARTH_RADIUS * c

    return d

def _check_if_in_bounds(lat, lon, nswe_thresh):
    """
    Check if a given lat,lon point lies outside of a given threshold
    @return true if it is in bound, false otherwise
    """
    if nswe_thresh is None:
        return True
    (n,s,w,e) = nswe_thresh
    if n is not None:
        if lat > n: return False
    if s is not None:
        _lat = lat
        _s = s
        if lat < 0: _lat = 360 + lat
        if s < 0:   _s = 360 + s
        if _lat < _s: return False
    if w is not None:
        _lon = lon
        _w = w
        if lon < 0: _lon = 360 + lon
        if w < 0: _w = 360 + w
        if _lon < _w: return False
    if e is not None:
        if lon > e: return False
    return True


def get_diapost_track_data(path, include_flagged_entries=False, logger=None, 
                           duration=None, nswe_thresh=None, 
                           skip_land_points=False):
    '''
    Reads Diapost data from the given path. If include_flagged_entries=False,
    only return entries in which the
    value is not flagged (i.e. only return those whose flag value is 0)
    ARGS
      - path - path to diapost ATCF
      - include_flagged_entries - If True, process entries flagged by the tracker.
                                  Default: False
      - duration - Duration of forecast to process, in seconds. If not passed in,
                   process the entire file
      - nswe_thresh - 4-tupple specifying threshold for (North, South, East, West)
                     points. Any points that are outside of these bounds are not
                     added to the returned ForecastTrack. The tupple or individual
                     values may be None, in which case no filtering is done. 
                     **NOTE: This has not been well tested **
      - skip_land_points If True, do not include values that are over land. 
                         Will use BaseMap's is_land() method for this.
    RETURNS an array of [ForecastTrack] objects, one for each cycle.
    NOTE: Each ForecastTrack file contains the list of TrackerData objects, one for each
        entry in the track file (which should correspond with the history interval)
    '''
    # This must be imported here to avoid circular dependency
    from pycane.postproc.tracker.objects import ForecastTrack, TrackerData

    if logger is None:
        logger = logging.getLogger()
    if skip_land_points:
        from mpl_toolkits.basemap import Basemap
        map = Basemap(projection='cyl', resolution='c') # default: global
    elfile = open(path, 'r')
    track = ForecastTrack(-1) # this is hackish!
    for line in elfile.readlines():
        toks = line.split()
        if len(toks) != 8:
            logger.warn('Unrecognized line found in Diapost file, ignoring it:\n\t %s' %line)
            continue
        fhr = int(toks[DIAPOST_TRACK_FILE_FHR_IDX])

        if duration is not None and fhr > int(duration / 3600.0):
            logger.info("Skipping forecast hour %i since it is after the specified duration"
                    %fhr)
            continue

        if int(toks[DIAPOST_TRACK_FILE_FLAG_IDX]) == 0: flagged_entry = False
        else: flagged_entry = True
        start_date = conversions.yyyymmddHH_to_epoch(toks[DIAPOST_TRACK_FILE_START_DATE_IDX])
        track.start_date = start_date # this is hackish!
        lat = float(toks[DIAPOST_TRACK_FILE_LAT_IDX])
        lon = float(toks[DIAPOST_TRACK_FILE_LON_IDX])
        in_bounds = True
        if nswe_thresh is not None:
            in_bounds = _check_if_in_bounds(lat, lon, nswe_thresh)
            if not in_bounds:
                logger.info("Skipping tracker entry @ ({},{}) since it lies"
                            #" outside of threshold ({},{},{},{})"
                            " outside of threshold ({})"
                            .format(lat, lon, nswe_thresh))
        if skip_land_points and in_bounds: # only go in here if w/in nswe_thresh
            x,y = map(lon, lat)
            if map.is_land(x,y):
                in_bounds = False
                logger.info("Skipping tracker entry @ ({},{}) since it is in "
                            "land"
                            .format(lat, lon))
        if in_bounds and (include_flagged_entries or not flagged_entry):
            trackData = TrackerData( start_date,
                                fhr,
                                flagged_entry,
                                float(toks[DIAPOST_TRACK_FILE_LAT_IDX]),
                                float(toks[DIAPOST_TRACK_FILE_LON_IDX]),
                                float(toks[DIAPOST_TRACK_FILE_MSLP_IDX]),
                                float(toks[DIAPOST_TRACK_FILE_maxwind_KTS_IDX])
                                )
            logger.debug('Appending diapost entry %s' %trackData )
            track.append_entry( trackData )
        else:
            logger.info('Skipping flagged entry %s' %line.strip())
    return track


def get_gfdltrk_track_data(path, flagged_entries_file="",
                           include_flagged_entries=False, log=None, 
                           duration=None,
                           skip_land_points=False):
    '''
    Read the output file of the GFDL tracker and return the data as a 
    ForecastTrack object. If `include_flagged_entries=False', only return
    entries in which the value is not flagged.
    NOTE: The GFDL tracker may create up to three entries for a given forecast
    hour, in cases where it
    produces radii for 34, 50 and 64 kt winds.
    Since we are only concerned with position, maxwind, and
    MSLP here, we just pick the first entry for a given forecast hour, since 
    these are all the same regardless of radii.
    NOTE: The GFDL tracker may not produce an entry for one or more forecast 
    hours if it detects that the storm is too weak. In these cases, flag the
    entry and fill with zeros.
    @param path - Path to the ATCF file generated by the tracker (can be the 
             fort.64 or fort.69)
    @param flagged_entries_file file containing newline-separated forecast hours
                              that should be treated as flagged
    @param include_flagged_entries - should flagged entries be included?
     @param log logger to use. If None, just use the python built-in one
    @param duration Duration of the forecast to process, in seconds.
                  If None, read whatever is in the file
    @param skip_land_points If True, do not include values that are over land. 
                         Will use BaseMap's is_land() method for this.
    RETURNS
       A [ForecastTrack] object corresponding to the track file.
    NOTE: Each ForecastTrack contains the list of TrackerData objects, one for each
    entry in the track file (which should correspond with the history interval).
    '''
    # This must be imported here to avoid circular dependency
    from pycane.postproc.tracker.objects import ForecastTrack, TrackerData

    GFDLTRK_TRACK_FILE_START_DATE_IDX = 2
    GFDLTRK_TRACK_FILE_FHR_IDX = 5
    #GFDLTRK_TRACK_FILE_FLAG_IDX = 3
    GFDLTRK_TRACK_FILE_LAT_IDX = 6
    GFDLTRK_TRACK_FILE_LON_IDX = 7
    GFDLTRK_TRACK_FILE_MSLP_IDX = 9 #mb
    GFDLTRK_TRACK_FILE_maxwind_KTS_IDX = 8

    if log is None:
        import logging as log
    if skip_land_points:
        from mpl_toolkits.basemap import Basemap
        map = Basemap(projection='cyl', resolution='c') # default: global
    flagged_fhrs = []
    if include_flagged_entries:
        if os.path.exists( os.path.join(flagged_entries_file) ):
            flagged_fhrs = [ int(x) for x in open(flagged_entries_file).readlines() ]
        else:
            log.debug("The flagged_entries_file does not exist.")
    processed_fhrs = []

    elfile = open(path, 'r')
    cycle_track = ForecastTrack(-1) # hack!
    lines = elfile.readlines()
    for lineNbr,line in enumerate(lines):
        toks = [x.strip() for x in line.split(",") ]
        if len(toks) not in (43,20):
            log.warn('Unrecognized line found in GFDL tracker output file, ignoring it:\n\t %s' %line)
            continue
        if len(toks) == 20:
            log.debug("fort.69 file detected")
            is_fort69 = True
        elif len(toks) == 43:
            is_fort69 = False

        # since gfdltrk ATCF file may contain multiple entries per forecast hour...
        fhr = int(toks[GFDLTRK_TRACK_FILE_FHR_IDX])
        if is_fort69:
            fhr /= 100 # TODO verify fort.69 always gives fhr*100

        if fhr in processed_fhrs:
            continue

        #print path, fhr, duration
        if duration is not None and fhr > int(duration / 3600.0):
            #import pdb ; pdb.set_trace()
            log.info("Skipping forecast hour %i since it is after the specified duration"
                     %fhr)
            continue
        processed_fhrs.append(fhr)

        # check if entry is flagged
        if fhr in flagged_fhrs: flagged_entry = True
        else: flagged_entry = False

        log.debug("Parsing GFDL tracker entry: data values: %s" %toks)

        # populate the rest of the fields

        start_date = conversions.yyyymmddHH_to_epoch(toks[GFDLTRK_TRACK_FILE_START_DATE_IDX])
        # if tracker detects 850 mb winds < [threshold in NL] or if it cannot find a
        # "good" mslp gradient, it will not produce a value at that time
        # for position, mslp, or intensity.
        # In these cases, flag the entry and set the values such that they can be used
        if toks[GFDLTRK_TRACK_FILE_LAT_IDX] == '0':
            log.warn("Flagging fhr %i for forecast %s. Tracker was unsure about it"
            %(fhr, toks[GFDLTRK_TRACK_FILE_START_DATE_IDX]) )
            flagged_fhrs.append(fhr)
            flagged_entry = True
            toks[GFDLTRK_TRACK_FILE_LAT_IDX] = '000N'
            toks[GFDLTRK_TRACK_FILE_LON_IDX] = '000E'
            toks[GFDLTRK_TRACK_FILE_MSLP_IDX] = 0
            toks[GFDLTRK_TRACK_FILE_maxwind_KTS_IDX] = 0
        lat = int(toks[GFDLTRK_TRACK_FILE_LAT_IDX][:-1])/10.0
        if toks[GFDLTRK_TRACK_FILE_LAT_IDX][-1] == "S": lat = -lat
        lon = int(toks[GFDLTRK_TRACK_FILE_LON_IDX][:-1])/10.0
        if toks[GFDLTRK_TRACK_FILE_LON_IDX][-1] == "W": lon = -lon
        cycle_track.start_date = start_date # this is hackish!
        in_bounds = True
        if skip_land_points:
            x,y = map(lon, lat)
            if map.is_land(x,y):
                in_bounds = False
                log.info("Skipping tracker entry @ ({},{}) since it is in "
                            "land"
                            .format(lat, lon))
        if in_bounds and (include_flagged_entries or not flagged_entry):
            trackData = TrackerData(start_date, fhr, flagged_entry, lat, lon,
                                float(toks[GFDLTRK_TRACK_FILE_MSLP_IDX]),
                                float(toks[GFDLTRK_TRACK_FILE_maxwind_KTS_IDX]))
            log.debug('Appending GFDL tracker entry %s' %trackData )
            cycle_track.append_entry( trackData )
        else:
            log.info('Skipping flagged entry %s' %line.strip())

    return cycle_track

def get_nolan_track_data(trk_path, log=None):
    '''
    Read a track file formatted in the style used for Dave Nolan's 
    hnr1 track file and return a ForecastTrack object with the data.
    '''
   # This must be imported here to avoid circular dependency
    from pycane.postproc.tracker.objects import ForecastTrack, TrackerData
    
    date_idx = 0
    lat_idx = 4
    lon_idx = 5
    mslp_idx = 6 # will be divided by 100
    maxwind_idx = 7
    
    with open(trk_path, 'r') as trk_file:
        lines = trk_file.readlines()
        startDate = conversions.yyyymmddHHMMSS_to_epoch(lines[0][0:14])
        #TODO : datetime
        fcst_track = ForecastTrack(startDate)
        for line in lines:
            toks = line.strip().split()
            # TODO : datetime
            fcstDate = conversions.yyyymmddHHMMSS_to_epoch(toks[date_idx])
            fhr = (fcstDate - startDate) / 3600
            fcst_track.tracker_entries.append(
                TrackerData(startDate, 
                            fhr, 
                            False,
                            float(toks[lat_idx]),
                            float(toks[lon_idx]),
                            float(toks[mslp_idx])/100.0,
                            float(toks[maxwind_idx]))
                                            )
    return fcst_track

def get_geos5trk_track_data(trkPath, log=None):
    """
    Read tracker data from track files provided for g5nr
    e.g.:
        2006/09/12 03:30 ; 34.5000 ; 273.750 ; 0 ; 1001.50 ; 75.3543 ; 32.8331 ; 40.5677
    """
    # This must be imported here to avoid circular dependency
    from pycane.postproc.tracker.objects import ForecastTrack, TrackerData
    def dtime_for_line(line):
        y,m,d = [int(x) for x in line.split()[0].split("/")]
        hr,mn = [int(x) for x in line.split()[1].split(":")]
        return dtime(year=y, month=m, day=d, hour=hr, minute=mn)
    date_idx = 0 ; time_idx = 1
    lat_idx = 3 ; lon_idx = 5
    cat_idx = 5 ; mslp_idx = 9
    wind_850_idx = 11
    maxwind_idx = 13 # 10m
    with open(trkPath, "r") as trk_file:
        lines = trk_file.readlines()
        start_date = dtime_for_line(lines[0])
        fcst_track = ForecastTrack(start_date)
        for line in lines:
            toks = line.strip().split()
            fcst_date = dtime_for_line(line)
            # NOTE : No fhr since this is nature run
            [lat,lon,mslp,vmax] = [float(toks[i]) for i in \
                                   [lat_idx, lon_idx, mslp_idx, maxwind_idx]]
            trkdat = TrackerData(start_date, None, False, lat, lon, mslp, vmax,
                                 fcstDate=fcst_date)
            fcst_track.tracker_entries.append(trkdat)
    return fcst_track



def get_bdeck_track_data(atcfPath, stormID, startDate, log=None):
    """
    Process best track data from b-deck files from NHC archives.
    @param atcfPath Path to the ATCF
    @param stormID The storm's ID (e.g. 09L)
    @param startDate The starting date of the experiment. This is used
           as the reference analysis date, so that the ForecastTrack's
           TrackerData's `fhr' field is relative to this time
    @param log logging.Logger to use for logging
    @return a ForecastTrack object
    """
    from pycane.postproc.tracker.objects import ForecastTrack, TrackerData
    idxStormId = 1
    idxYMDH = 2
    idxTrackType = 4
    idxLat = 6
    idxLon = 7
    idxMaxwind = 8
    idxMslp = 9
    if log is None:
        import logging as log
    startYear = conversions.epoch_to_yyyymmddHHMM(startDate)[0:4]
    if stormID.upper()[-1] == "L":
        basinId = 'al'
    elif stormID.upper()[-1] == "E":
        basinId = 'ep'
    if stormID.upper()[-1] == "Q":
        basinId = 'sl'
    if stormID.upper()[-1] == "S":
        basinId = 'sp'
    if stormID.upper()[-1] == "C":
        basinId = 'cp'
    stormNum = stormID[0:2]
    fileName = "b{}{}{}.dat.gz".format(basinId, stormNum, startYear)
    #bal092012.dat.gz
    stormAtcfPath = os.path.join(atcfPath, fileName)
    log.info("Reading best track from: '{}'".format(stormAtcfPath))
    el_file = gzip.open(stormAtcfPath, "rb")
    lines = el_file.readlines()
    #startDate = conversions.yyyymmddHHMMSS_to_epoch(lines[idxYMDH])
    fcst_track = ForecastTrack(startDate)
    added_dates = [] # since B-decks have separate lines for different wind radii
    for line in lines:
        toks = line.split(", ")
        #log.debug("Best track line: {}".format(line))
        assert toks[idxLat][-1] in ('N','S')
        assert toks[idxLon][-1] in ('W','E')
        assert toks[idxTrackType] == 'BEST'
        lat = int(toks[idxLat][:-1])/10.0
        if toks[idxLat][-1] == "S": lat = -lat
        lon = int(toks[idxLon][:-1])/10.0
        if toks[idxLon][-1] == "W": lon = -lon
        currDate = conversions.yyyymmddHH_to_epoch(toks[idxYMDH])
        currDateStr = conversions.epoch_to_yyyymmddHHMM(currDate)
        if currDate in added_dates:
            continue
        if currDate < startDate:
            log.debug("Skipping earlier date {}".format(currDateStr))
            continue
        log.info("Setting fhr for best track to start_date - current_date")
        fhr = (currDate - startDate) / 3600
        trackData = TrackerData(startDate, fhr, False, lat, lon,
                                float(toks[idxMslp]),
                                float(toks[idxMaxwind]))
        log.debug('Appending B-Deck tracker entry %s' %trackData )
        fcst_track.append_entry( trackData )
        added_dates.append(currDate)
    return fcst_track


def get_track_data(atcfPath, stormID=None, startDate=None, logger=None):
    '''
    Guess the kind of tracker output format based on the length of the first
    line in the given ATCF and call the corresponding method to convert
    it to a ForecastTrack object.
    NOTE: Since some track files are comma-separated and others are space-
    separated, this function is not that reliable.
    FOr GFDL tracks in particular, fort.69 tends to work better
    @param atcfPath Full path to the ATCF
    @param stormID The stormID to analyze. This is only needed and used if
           `atcfPath' is for a B-deck best track or SYNDAT file
    @param startDate The starting date of the experiment. This is used
           as the reference analysis date, so that the ForecastTrack's
           TrackerData's `fhr' field is relative to this time.
           It is only used for Best track data from SYNDAT or NHC b-decks
    @param logger Logger to log to. If not present, use default
    @return ForecastTrack object with the data
    '''
    if logger is None:
        import logging as logger
    msg = lambda trkType: logger.debug("Assuming this is a {} ATCF based on "\
                                       " line length".format(trkType))
    if not os.path.exists(atcfPath):
        raise Exception("The ATCF does not exist: {}".format(atcfPath))
    if os.path.isdir(atcfPath):
        logger.warn("Since 'atcfPath'='{}' is a directory, assuming it is a "
                    "b-deck.".format(atcfPath))
        return get_bdeck_track_data(atcfPath, stormID, startDate)
    else:
        with open(atcfPath) as trkFile:
            lineDat = trkFile.readline().strip().split()
            if len(lineDat) == 13:
                msg('nolan')
                return get_nolan_track_data(atcfPath)
            elif len(lineDat) in (43,20):
                msg('gfdltrk')
                return get_gfdltrk_track_data(atcfPath)
            elif len(lineDat) == 8:
                msg("diapost")
                return get_diapost_track_data(atcfPath)
            elif len(lineDat) in (19,30):
                if stormID is None or startDate is None:
                    raise Exception("This looks like syndat data; need a stormID")
                msg("syndat")
                return get_syndat_track_data(atcfPath, stormID, startDate)
            elif len(lineDat) == 16:
                msg("geos5trk")
                return get_geos5trk_track_data(atcfPath)
            #elif len(lineDat) in (17, 35):
            #    msg("b-deck best track")
            #    if stormID is None or startDate is None:
            #        raise Exception("This looks like B-deck data; need stormID")
            #    return get_bdeck_track_data(atcfPath, stormID, startDate)
            else:
                raise Exception("Unable to determine the type of ATCF")
            

# TEST
if __name__ == '__main__':
    path = './sample_fort.64'
    gfdltrk = get_gfdltrk_track_data(path)
