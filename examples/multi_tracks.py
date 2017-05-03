#!/usr/bin/env python
'''
Draw tracks using the track_plotter module.
This particular example draws 2 tracks on the same map. One is 
from a GFDL tracker output and the other from a Diapost output
'''

import sys
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import logging as log
from pycane.postproc.viz.map import track_plotter
from nwpy.viz.map import bling
from pycane.postproc.tracker import utils as trkutils 

if __name__ == '__main__':

    names = ['NMM-B/NAM::3km',
             'HWRF-B::3km',
             'HWRF-B::18/6/2km',
             'HWRF',
             'GFDL',
             'AVNI',
             'BEST']
    topdir = '/home/Javier.Delgado/scratch/earl_comparo/fcst_track'
    storm = 'danielle'
    files = [ 'nmmbNamPhysics.txt',
              'nmmbHwrfPhysics.txt',
              'nmmb_nested.txt',
              'hwrf_track.txt',
              'gfdl_track.txt',
              'avni_track.txt',
              'best_track.txt']
    colors = ['blue',
              'red',
              'magenta',
              'orange',
              'green',
              'pink',
              'black']
    line_width = 2.0
    extents = [0, -85, 45, -35] 

    # how frequently to mark the line showing the track
    TIME_MARKER_INTERVAL = 6

    log.basicConfig(level=log.DEBUG)

    paths = []
    for i,fil in enumerate(files):
        paths.append(os.path.join(topdir, storm, fil))
   
    for i,label in enumerate(names):
        log.info("processing %s @ %s" %(names[i], paths[i]))
        forecast_track = trkutils.get_diapost_track_data(paths[i])
        lons = [entry.lon for entry in forecast_track.tracker_entries]
        lats = [entry.lat for entry in forecast_track.tracker_entries]
        fhrs = [entry.fhr for entry in forecast_track.tracker_entries]
        maxwinds = [entry.maxwind_value for entry in forecast_track.tracker_entries]
        flagged = [entry.flagged for entry in forecast_track.tracker_entries]
        flagged_idc = [ idx for idx,v in enumerate(flagged) if v is True ]
        day_idc = [ idx for idx,val in enumerate(fhrs) if val%TIME_MARKER_INTERVAL == 0 ]
        m = track_plotter.plot_track(lats, lons, 
                                 #windspeeds=maxwinds, 
                                 indicator_freq=day_idc,
                                 line_color=colors[i], ns_gridline_freq=10, we_gridline_freq=10,
                                 flagged_idc=flagged_idc,
                                 label=label, 
                                 extents=extents,
                                 line_width=line_width)
    bling.decorate_map(m)
    # options worth testing: water_color='#99ffff',lake_color='#99ffff', 
    #continent_color='#cc9966'
    
    # plot legend. The skip_duplicates arg must be True since the plot_track()
    # function actually plots multiple lines for each track in order to vary 
    # the intensity of the color based on the max wind value
    bling.create_simple_legend(skip_duplicates=True, position='upper right')
    
    plt.savefig('tracks.png')

