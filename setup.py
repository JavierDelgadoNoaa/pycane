import os
import sys
from optparse import OptionParser
import logging
#from setuptools import find_packages
from setuptools import find_packages, setup

# If we use f2py libs in the future, use this and see nwpy setup.py for how to
# add Extensions
#from numpy.distutils.core import Extension

##
# DEFAULTS
##
# NOTHING to do

if __name__ == "__main__":
    # if we use f2py libs in the future, use this
    #from numpy.distutils.core import setup 
    
    setup(
          name              = "pycane",
          #ext_modules=ext_modules,
          #script_args=copy_args,
          version           = "0.6",
          description       = "Various hurricane research related tools",
          long_description  = """Contains tools for processing files containing
                                 TC Vitals data in various formats, visualizing
                                 this data, etc.""",
          author            = "Javier Delgado",
          author_email      = "Javier.Delgado@noaa.gov",
          platforms         = ["any"],
          keywords          = ["python","numerical weather prediction", "hurricanes", 
                               "tc vitals"],
                              # https://pypi.python.org/pypi?%3Aaction=list_classifiers
          classifiers       = ["Development Status :: 3 - Alpha",
                               "Intended Audience :: Science/Research",
                               "Programming Language :: Python",
                               "Topic :: Scientific/Engineering :: Visualization",
                               "Topic :: Scientific/Engineering :: Atmospheric Science",
                               "Operating System :: OS Independent"],
         # ** setup.py install will not include package_data in the MANIFEST.in
         #    (setup.py bdist will), so non-source files must be included here
         package_data = { "":["etc/*sh"] },
         include_package_data = True,
         requires=["nwpy"]
         )
