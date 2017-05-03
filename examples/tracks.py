#!/usr/bin/env python
'''
Draw tracks using the track_plotter module.
This particular example draws 2 tracks on the same map. One is 
from a GFDL tracker output and the other from a Diapost output
'''

import sys
import os
import logging as log

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from nwpy.viz.map import bling
from pycane.postproc.viz.map import track_plotter
from pycane.postproc.tracker import utils as trkutils 

if __name__ == '__main__':

    hnr1_nolan_diapost = '../../../sample_datasets/hnr1_nolan_fcst_track.txt'
    hnr1_gfdltrk = '../../../sample_datasets/hnr1_gfdltrk_atcf.txt'

    # how frequently to mark the line showing the track
    TIME_MARKER_INTERVAL = 24 # daily

    log.basicConfig(level=log.DEBUG)
    
    # gfdl
    forecast_track = trkutils.get_gfdltrk_track_data(hnr1_gfdltrk)
    lons = [entry.lon for entry in forecast_track.tracker_entries]
    lats = [entry.lat for entry in forecast_track.tracker_entries]
    fhrs = [entry.fhr for entry in forecast_track.tracker_entries]
    maxwinds = [entry.maxwind_value for entry in forecast_track.tracker_entries]
    flagged = [entry.flagged for entry in forecast_track.tracker_entries]
    flagged_idc = [ i for i,v in enumerate(flagged) if v is True ]
    day_idc = [ idx for idx,val in enumerate(fhrs) if val%TIME_MARKER_INTERVAL == 0 ]
    m = track_plotter.plot_track(lats, lons, windspeeds=maxwinds, indicator_freq=day_idc,
                             line_color='black', ns_gridline_freq=10, we_gridline_freq=10,
                             flagged_idc=flagged_idc,
                             label = 'gfdl')
    # nolan (converted to diapost format)
    forecast_track = trkutils.get_diapost_track_data(hnr1_nolan_diapost)
    lons = [entry.lon for entry in forecast_track.tracker_entries]
    lats = [entry.lat for entry in forecast_track.tracker_entries]
    fhrs = [entry.fhr for entry in forecast_track.tracker_entries]
    maxwinds = [entry.maxwind_value for entry in forecast_track.tracker_entries]
    flagged = [entry.flagged for entry in forecast_track.tracker_entries]
    flagged_idc = [ i for i,v in enumerate(flagged) if v is True ]
    day_idc = [ idx for idx,val in enumerate(fhrs) if val%TIME_MARKER_INTERVAL == 0 ]
    track_plotter.plot_track(lats, lons, windspeeds=maxwinds, indicator_freq=day_idc,
                             line_color='red', ns_gridline_freq=10, we_gridline_freq=10,
                             line_style='--',
                             flagged_idc=flagged_idc,
                             basemap = m,
                             label = 'nolan')
    bling.decorate_map(m)
    # options worth testing: water_color='#99ffff',lake_color='#99ffff', 
    #continent_color='#cc9966'
    
    # plot legend. The skip_duplicates arg must be True since the plot_track()
    # function actually plots multiple lines for each track in order to vary 
    # the intensity of the color based on the max wind value
    bling.create_simple_legend(skip_duplicates=True)
    
    plt.savefig('hnr1_tracks.png')

