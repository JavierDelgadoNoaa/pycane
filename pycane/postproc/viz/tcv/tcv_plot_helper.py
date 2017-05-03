import os
import sys
import time
import logging
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates
from matplotlib.dates import DateFormatter, WeekdayLocator, DayLocator,\
                             MONDAY, HourLocator, date2num, num2date
import pytz
from tzlocal import get_localzone # $ pip install tzlocal
import datetime
#
# CONSTANTS
#

# set to the current timezone, since we use localtime() (note date is random
# since we just need the tz name)
#TIMEZONE = pytz.timezone( get_localzone().tzname( datetime.datetime(2012,1,1) ) )
TIMEZONE = pytz.utc

#
# FUNCTIONS
#
def tcv_plot_basic(x, y, ax=None, **kwargs):
    '''
    Wrapper for MPL::plot() that handles some of the typical functionality 
    for TCV plots.
        @param x x-axis list of values
        @param y y-axis list of values
        @param ax (optional) list of axes to plot on. Default: use gca()
        **kwargs - Optional args to pass to MPL::plot() 
    '''
    if ax is None:
        ax = plt.gca()
    ax.plot(x, y, **kwargs) # unpack dict to pass params to mpl::plot()


def plot_tcv_metric_vs_fhr(
            forecast_track, metric_name, axes=None,
            indicate_flagged=False, x_label=None, y_label=None, 
            time_axis_parameter='fhr', hline_at_zero=False,
            log=None,
            **kwargs):
    '''
    Using the given `forecast_track', plot the given `metric_name'.
    Specifically, for each tracker_entry in the `forecast_track', plot 
    its `metric_name' attribute against its "fhr" attribute.
    @param forecast_track The ForecastTrack or ForecastTrackDiff 
           object containing the tracker data to plot
           pycane.postproc.tracker.ForecastTrack object
    @param metric_name the metric to plot ('mslp', 'maxwind')
    @param axes (optional) Axes object to plot on. Default: gca()
    @param indicate_flagged (opt) If True, indicate marked tracker entries
        by circling the corresponding points on the plot
    @param x_label String containing the x-label text
    @param y_label String containing the y-label text
    @param time_axis_parameter if 'fhr' label on 'x' axis will be the
            forecast hours. If 'epoch_zeta', the date as "%m/%d@%Hz"
    @param hline_at_zero - if set, draw a line of this color at y=0
    @param log A Logger object to log on. If not passed in, use root logger
    @param kwargs - additional arguments to pass to matplotlib::plot()
    '''        
        
    # determine the time axis labels to use
    
    if not log:
        log = logging.getLogger()
        
    cycle = forecast_track.start_date
    tracker_entries = forecast_track.tracker_entries
    list_of_fcst_hours = [x.fhr for x in tracker_entries]
    
    # Populate values for the x axis
    if time_axis_parameter == 'fhr':
        time_axis_values = list_of_fcst_hours
    elif time_axis_parameter == 'epoch_zeta':
        if None in list_of_fcst_hours:
            # If working with 'atcf' that does not have forecast hours (e.g. nature run)
            time_axis_values = [trkentry.fcst_date for trkentry in tracker_entries]
        else:
            epoch_dates =[(fhr * 3600) + cycle for fhr in list_of_fcst_hours]
            time_axis_values = \
                [ num2date(matplotlib.dates.epoch2num(x),
                           tz=TIMEZONE) for x in epoch_dates]
    # get the y axis values
    values = [getattr(x,metric_name) for x in tracker_entries]
    if len(values) == 0:
        log.warn('No values for metric %s in dataset' %metric_name )

    # plot the data 
    if not axes: 
        axes = plt.gca()
    tcv_plot_basic(time_axis_values, values, axes, **kwargs)

    # do optional stuff
    if indicate_flagged:
        log.debug('Marking points with flagged tracker entries')
        circleX = []
        circleY = []
        flagged_idc = [i for i,x in enumerate(tracker_entries) if x.flagged]
        for j in range(len(tracker_entries)):
            if j in flagged_idc:
                circleX.append(time_axis_values[j])
                circleY.append(values[j])
        # TODO : figure out how to set size so that its always visible 
        # regardless of line width
        #scatter(circleX,circleY,facecolors='none',
        #        s=self.cfg.line_width*1.4,
        #        edgecolors=dataset.plot_options['line_color'])
        plt.scatter(circleX,circleY,
                    s=35,
                    zorder=4, # in case we're over land 
                    marker='o',
                    edgecolors=kwargs['color'],
                    facecolors='none')
    
    if time_axis_parameter == 'fhr':
        # MPL sometimes adds some padding
        plt.xlim(min(time_axis_values), max(time_axis_values) )

    # Draw a horizontal line if option passed in, 
    # but only if the max y value is less than 500,
    # otherwise plots like mslp_value may look bad  
    if hline_at_zero:
        if max(values) < 500:
            plt.axhline(y=0, color=hline_at_zero, ls='--')
        
    # set the labels
    if x_label:
        plt.xlabel(x_label, fontsize=20)
    else:
        if time_axis_parameter == 'fhr':
            plt.xlabel('AForecast Hour', fontsize=20)
        elif time_axis_parameter == 'epoch_zeta':
            log.debug('If doing subplots, x axis values may get trimmed')
            majorLocator = HourLocator(byhour=range(0,24,12), tz=TIMEZONE)  
            minorLocator = HourLocator(byhour=range(0,24,6), tz=TIMEZONE)
            axes.xaxis.set_major_locator(majorLocator) 
            axes.xaxis.set_minor_locator(minorLocator)
            #https://docs.python.org/2/library/time.html
            axes.xaxis.set_major_formatter( DateFormatter('%m/%d@%Hz') )
            axes.figure.autofmt_xdate()
            plt.xlabel('Date')
        else:
            log.warn('Unknown time_axis_parameter. Cannot label x-axis')

    if y_label: 
        plt.ylabel(y_label)
