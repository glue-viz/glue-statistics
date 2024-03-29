
******************************************
Glue Statistics Data Viewer Documentation
******************************************

    :keywords: Documentation

Author: Juna Kim

Requirements
============

Before the Statistics Viewer can be used, please download the Vispy Viewer for 3D graphs. Instructions on how to download the Vispy Viewer can be found at: https://github.com/glue-viz/glue-vispy-viewers/blob/master/README.rst

Introduction
============

This documentation will explain how to use the Glue Statistics Viewer.

Contents
=======================

This section describes the structure of documentation and its files.

#. Toolbar
#. Subset and Component Views
#. Calculations
#. Saving your Work
#. Warnings and Potential Issues



Toolbar
============================

.. image:: ../glue_statistics/icons/1.png

Save
-----------------
.. image:: ../glue_statistics/icons/glue_filesave.png
    :width: 35px

This button is used to export your work done on the Statistics Viewer. The current open tree viewer will be exported (Subset/Component Tree View) will all the calculated values. The data is in a csv machine-readable format.

Home
-----------------
.. image:: ../glue_statistics/icons/glue_home.png
    :width: 35px

This button resets the entire Statistics Viewer to its default state as it was first loaded with all data, subsets, and calculated values. This button is helpful for users who have sorted the data in the viewer and wish to revert to the original view.

Collapse
-----------------
.. image:: ../glue_statistics/icons/glue_collapse.png
    :width: 35px

Minimizes the rows of the Statistics Viewer in levels.

Expand
-----------------
.. image:: ../glue_statistics/icons/glue_expand.png
    :width: 35px

Maximizes the rows of the Statistics Viewer in levels.


Scientific/Decimal Notation
-------------------------------
.. image:: ../glue_statistics/icons/glue_decimal.png
    :width: 35px

This button is used to toggle the values of the Statistics Viewer from scientific/decimal notation. The calculated values are left-justified in scientific notation and right-justified in decimal notation so the values are lined up and more easily comparable at a glance.

Sorting
------------------
.. image:: ../glue_statistics/icons/glue_sort.png
    :width: 35px

Toggles the ability to sort. Click on each column name to sort by decreasing or increasing value. You are also able to drag rows and columns to your preference. 

Quick Export to Viewer
--------------------------
.. image:: ../glue_statistics/icons/glue_export.png
    :width: 35px

For users who wish to quickly export calculated data in the Statistics Viewer to another viewer in Glue. This prevents exporting the data to an external file, importing the file back into glue, and opening the new viewer.

Instructions
------------------
.. image:: ../glue_statistics/icons/glue_instructions.png
    :width: 35px

Press this button to see the instructions panel that showed up when creating the Statistics Viewer. 

Custom Column
------------------
.. image:: ../glue_statistics/icons/glue_addcolumn.png
    :width: 35px

Feature that allows the user to create input python code to calculate values of a new column. Current libraries already defined in the config file consist of numpy, math, pandas, and scipy. Other libraries can be imported in the custom config file.

Settings
------------------
.. image:: ../glue_statistics/icons/glue_settings.png
    :width: 35px

The Settings icon can be used (as of now) to modifiy the number of decimal points that calculated values have, or to toggle manual calculation(See Warnings and Potential Issues for more info). 




Subset and Component Views
==========================
There are two tabs under the toolbar that have the Subset view(open by default) and the Component View. The Subset View organizes the data into the datasets and subset categories. The Component View organizes the data by the components that are being calculated and contain all subsets under the calculated component. Both viewers are showing identical data in different formats.



Calculations
=======================

To calculate values, check the box next to the data row you wish to calculate. Pressing the calculate button on the toolbar will calculate all data rows. 


Linking Data
-----------------

Certain data rows in the Statistics Viewer may be grayed out. This is because not all subsets may make logical sense to calculate e.g(can't calculate statistics for a blank image). However, certain grayed/disabled out data rows should be able to calculate values after linking datasets using Glue's built in linking functions. The Statistics Viewer will automatically be listening for these changes and will enable any grayed data rows that are able to be calculated. Make sure to keep an eye out for data rows you enabled!


Updating Subsets
-----------------
Existing subsets that are modified will automatically update the values on the Statistics Viewer. On certain OS, the user must double-click the subset they have redrawn/updated for Glue to send the update message to the Statistics Viewer. 




Warnings and Potential Issues
==================================

Sorting
-----------------
To avoid any issues with sorting, it will be best to calculate all values you wish to sort BEFORE sorting rows by your desired attribute by clicking on the name of each column. Qt may contain bugs where calculating after sorting may re-shuffle and assign wrong values to rows. If this happens, exit and restart the Statistics Viewer.

Large Datasets
-----------------
There may be certain cases where the automatic calculation of values by clicking a group of data of a large dataset will freeze Glue for an extended period of time for calculations. To limit this, the Statistics Viewer will turn on manual calculation for any dataset with over 1 million values. This feature wil prompt the user to confirm calculation as it may take a while. To turn this feature off, navigate to the Settings menu at the toolbar. 

Subset Updates
-----------------
Make sure that any subsets that you update are accurately reflected in the Statistics Viewer. On some versions of Glue, double-clicking the updated subset is necessary for Glue to understand the subset has been fully modified. 
