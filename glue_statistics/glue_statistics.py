import numpy as np
import sys
import pandas as pd

from qtpy import compat
from qtpy.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QTextEdit, QCheckBox, \
    QTreeWidget, QTreeWidgetItem, QAbstractItemView, QPushButton, QSpinBox, QMainWindow, \
    QLabel, QMessageBox, QRadioButton, QLineEdit, QComboBox
from PyQt5.QtCore import QVariant, QItemSelectionModel, Qt

from glue.viewers.common.qt.data_viewer import DataViewer
from glue.viewers.common.qt.toolbar import BasicToolbar
from glue.core import Data
from glue.core.message import SubsetUpdateMessage, DataUpdateMessage, \
    DataAddComponentMessage, DataRemoveComponentMessage, DataCollectionDeleteMessage,\
    SubsetDeleteMessage, EditSubsetMessage, LayerArtistVisibilityMessage, \
    ExternallyDerivableComponentsChangedMessage, DataRenameComponentMessage
from PyQt5.QtGui import QStandardItemModel
from PyQt5 import QtGui
from PyQt5.QtWidgets import QTabWidget
from glue.icons.qt import helpers

from glue_statistics.icons import NOTATION_LOGO, CALCULATE_LOGO, SORT_LOGO, \
    SETTINGS_LOGO, INSTRUCTIONS_LOGO, HOME_LOGO, SAVE_LOGO, EXPAND_LOGO, COLLAPSE_LOGO
showInstructions = True


class StatsDataViewer(DataViewer):
    """
    A class used to display and make the StatsDataViewer functional
    ----------
    Attributes
    ----------
    LABEL : str
        name of viewer that shows up on the Glue viewer menu
    _state_cls : ViewerState
        ViewerState object of the StatsDataViewer
    _options_cls : ViewerStateWidget
        ViewerStateWidge of the StatsDataViewer
    inherit_tools: boolean
        Sets the inheritance of default tools fromt the BasicToolbar to false
    _toolbar_cls: Toolbar
        The toolbar of the StatsDataViewer
    tools: array
        array of tool ids shown on the StatsDataViewer toolbar
    shortcut: char
        character that can toggle the tool from keyboard
    ----------
    """
    LABEL = 'Statistics viewer'
    # _state_cls = StatsViewerState
    # _options_cls = StatsViewerStateWidget
    inherit_tools = False

    tools = ['stats:save_tool', 'stats:home_tool', 'stats:calc_tool',
             'stats:collapse', 'stats:expand_tool', 'stats:notation_tool',
             'stats:sort_tool', 'stats:export_tool', 'stats:instructions',
             'stats:add_column', 'stats:settings']

    def __init__(self, *args, **kwargs):
        '''
        initializes the StatsDataViewer
        '''
        super(StatsDataViewer, self).__init__(*args, **kwargs)

        # xc is dc, or the DataCollection
        # DO NOT USE dc VARIABLE!
        # It will mess up the IPython Terminal as it already uses a dc refrence
        self.xc = self.session.data_collection
        self.no_update = False
        # self.calculatedSubsetViewList = np.array(["Subset, Dataset, Component, Mean,
        #                                           Median, Minimum, Maximum, Sum"])
        # self.calculatedComponentViewList = np.array(["Subset, Dataset, Component, Mean,
        #                                               Median, Minimum, Maximum, Sum"])

        self.headings = ['Name', 'Mean', 'Median', 'Minimum', 'Maximum', 'Sum']
        # Set up dict for caching
        self.cache_stash = dict()
        self.isSci = True
        self.num_sigs = 3
        # Set up past selected items
        self.past_selected = []

        # # Set component_mode to false, default is subset mode
        self.component_mode = False

        # # These will only be true when the treeview has to switch between views and a
        # # Change has been made in the other
        self.updateSubsetSort = False
        self.updateComponentSort = False
        self.selected_indices = []

        self.columnCount = 6

        # Set up tree widget item for the view
        self.subsetTree = ModifiedTreeWidget()
        self.subsetTree.setSelectionMode(QAbstractItemView.MultiSelection)
        self.subsetTree.setColumnCount(self.columnCount)
        self.subsetTree.setColumnWidth(0, 350)
        # self.subsetTree.header().setSortIndicator(0, 0)
        QTreeWidget.setHeaderLabels(self.subsetTree, self.headings)
        self.subsetTree.itemClicked.connect(self.check_status)
        self.sortBySubsets()
        self.subsetTree.expandToDepth(2)
        # self.subsetTree.sortByColumn(0)

        # component view tree Widget
        self.componentTree = ModifiedTreeWidget()
        self.componentTree.setSelectionMode(QAbstractItemView.MultiSelection)
        self.componentTree.setColumnCount(self.columnCount)
        self.componentTree.setColumnWidth(0, 300)
        self.componentTree.header().setSortIndicator(1, 0)
        QTreeWidget.setHeaderLabels(self.componentTree, self.headings)
        self.sortByComponents()
        self.componentTree.itemClicked.connect(self.check_status)
        self.componentTree.expandToDepth(1)

        # set up the tabs for each of the two tree views
        self.tabs = QTabWidget()
        self.tabs1 = self.subsetTree
        self.tabs2 = self.componentTree
        self.tabs.addTab(self.tabs1, "Subset View")
        self.tabs.addTab(self.tabs2, "Component View")
        self.setCentralWidget(self.tabs)

        # Set up dicts for row indices
        self.subset_dict = dict()
        self.component_dict = dict()
        self.selected_dict = dict()

        # keeps track of how much data and subsets are loaded in
        self.dc_count = len(self.xc)
        self.subset_count = len(self.xc.subset_groups)

        # store the data and subsets, if any in the viewer at creation
        self.data_names = self.xc.labels
        # print(self.data_names)
        self.subset_names = self.subsetNames()

        self.subset_set = set()

        self.componentViewExportCache = set()
        self.subsetViewExportCache = set()

        self.isCalcAutomatic = not self.hasLargeData()
        self.confirmedCalc = False
        self.alreadyChecked = []

        # Creates the window used to edit decimal points shown on the stats viewer
        self.createEditDecimalWindow()
        # create the window used to toggle manual/automatic calculation
        self.createManualCalcWindow()

        # minimize grayed data
        self.minimizeGrayedData()

        # show instruction pop up message
        global showInstructions
        if showInstructions:
            # instruction pop up message
            self.cb = QCheckBox("Do not show again")
            msgbox = QMessageBox()
            msgbox.setWindowTitle("Statistics Viewer Instructions")
            # Rich Text format for styling
            msgbox.setTextFormat(1)
            msgbox.setText("<h2 style=\"text-align: center;\"><img src=" + str(INSTRUCTIONS_LOGO) + " width=\"46\" height=\"46\" />&nbsp;<strong>Instructions:</strong></h2><p>Tick the rows to calculate basic statistics</p><p>Click between Subset and Component views</p><p><img src=" + str(SAVE_LOGO) + " width=\"30\" height=\"30\" />&nbsp;Exports the current open tree view</p><p><img src=" + str(HOME_LOGO)+" width=\"30\" height=\"30\" />&nbsp;Resets the viewer to default layout</p><p><img src=" + str(CALCULATE_LOGO)+" width=\"30\" height=\"30\"/>&nbsp;Calculate entire view</p><p><img src=" + str(COLLAPSE_LOGO) + " width=\"30\" height=\"30\"/>&nbsp;Minimize a level</p><p><img src=" + str(EXPAND_LOGO) + " width=\"30\" height=\"30\"/>&nbsp;Expand a level</p><p><img src=" + str(NOTATION_LOGO) + " width=\"30\" height=\"30\" />&nbsp;Toggles scientific notation and decimal form</p><p><strong><img src=" + str(SORT_LOGO)+" width=\"30\" height=\"30\" />&nbsp;</strong>Enables sorting, selecting a column will sort rows accordingly</p><p><img src=" + str(INSTRUCTIONS_LOGO) + " width=\"30\" height=\"30\" />&nbsp;Read instructions</p><p><img src=" + str(SETTINGS_LOGO)+" width=\"30\" height=\"30\" />&nbsp;Change # of decimal points, instructions, etc</p><p>&nbsp;</p>")
            # msgbox.setText("<h2 style=\"text-align: center;\"><strong>Instructions:</strong></h2><p>Check the rows to calculate basic statistics</p><p>Cycle between Subset and Component views with the tabs</p><p><span style=\"color: #ff0000;\"><strong>Save</strong></span> Exports the current open tree view</p><p><span style=\"color: #ff0000;\"><strong>Home</strong></span> Resets viewer to default state</p><p><span style=\"color: #ff0000;\"><strong>Notation</strong></span> Toggles scientific notation and decimal form</p><p><span style=\"color: #ff0000;\"><strong>Sort</strong></span> Enables sorting, selecting a column will sort rows accordingly</p><p><span style=\"color: #ff0000;\"><strong>Instructions</strong></span> See how the viewer works</p><p><span style=\"color: #ff0000;\"><strong>Settings</strong></span> Change # of decimal points or toggle manual mode</p>")
            # msgbox.setText("<h2 style=\"text-align: center;\"><img src=\"https://github.com/jk31768/glue-statistics/blob/master/StatsDataViewer/glue_instructions.png?raw=true\" width=\"46\" height=\"46\" />&nbsp;<strong>Instructions:</strong></h2><p>Check the rows to calculate basic statistics<p><p>Cycle between Subset and Component views with the tabs<p><p><img src=GLUE_HOME />&nbsp; Resets viewer to default state<p><p><img src=GLUE_REFRESH width=\"30\" height=\"30\"/>&nbsp; Checks for possible calculations after linking data<p><p><span style=\"color: #ff0000;\"><strong><img src=GLUE_SORT width=\"30\" height=\"30\"/>&nbsp;</strong></span>Enables sorting, selecting a column will sort rows accordingly<p><p><img src=GLUE_SCIENTIFIC_NOTATION width=\"30\" height=\"30\"/>&nbsp;Toggles scientific notation and decimal form<p><p><img src='glue_filesave' width=\"30\" height=\"30\"/>Exports the current open tree view<p><p><img src=GLUE_SETTINGS width=\"30\" height=\"30\" />&nbsp;to change # of decimal points or to read more instructions<p>")
            # msgbox.setText("<h2 style=\"text-align: center;\"><img src=\"/Users/jk317/Glue/icons/glue_instructions.png\" width=\"46\" height=\"46\" />&nbsp;<strong>Instructions:</strong></h2><ul><li>Check the rows to calculate basic statistics</li><li>Cycle between Subset and Component views with the tabs</li><li><img src=\"/glue/icons/glue_home\" />&nbsp; Collapses all rows</li><li><img src=\"/Users/jk317/Glue/icons/glue_refresh.png\" width=\"30\" height=\"30\"/>&nbsp; Checks for possible calculations after linking data</li><li><span style=\"color: #ff0000;\"><strong><img src=\"/Users/jk317/Glue/icons/glue_sort.png\" width=\"30\" height=\"30\"/>&nbsp;</strong></span>Enables sorting, selecting a column will sort rows accordingly</li><li><img src=\"/Users/jk317/Glue/icons/glue_scientific_notation.png\" width=\"30\" height=\"30\"/>&nbsp;Toggles scientific notation and decimal form</li><li><img src='glue_filesave' width=\"30\" height=\"30\"/>Exports the current open tree view</li><li><img src=\"/Users/jk317/Glue/icons/glue_settings.png\"width=\"30\" height=\"30\" />&nbsp;to change # of decimal points or to read more instructions</li></ul>")
            # msgbox.setText("Instructions:\nCheck the rows to calculate basic statistics\nPress Home to collapse all rows\nPress Refresh after linking data to check for possible calculations\nPress Sort to enable sorting, selecting a column will sort rows accordingly\nPress Convert to toggle scientific notation and decimal form\nExport button exports the opened tree view\nPress Settings to change # of decimal points or to read instructions\nCycle between Subset and Component view with the tabs" )
            # msgbox.setIcon(QMessageBox::Icon::Question);
            msgbox.setStandardButtons(QMessageBox.Ok)
            # msgbox.addButton(QMessageBox::Cancel);
            # msgbox.setDefaultButton(QMessageBox::Cancel);
            msgbox.setCheckBox(self.cb)
            msgbox.buttonClicked.connect(self.showAgainUpdate)
            msgbox.exec()

        if not self.isCalcAutomatic:
            self.showLargeDatasetWarning()

        # print(self.state.layers)
        self.state.add_callback('layers', self._on_layers_changed)

        self.plot_layers, self.plotlayer_names = self.plotLayerNames()
        self.activePlotLayerList = []

        # self.subsetTree.setSortingEnabled(True)
        # self.componentTree.setSortingEnabled(True)
        self.subsetTree.viewport().setAcceptDrops(True)
        self.subsetTree.setDragEnabled(True)
        self.subsetTree.setDropIndicatorShown(True)
        # self.subsetTree.DropIndicatorPosition = (QAbstractItemView.BelowItem)
        self.subsetTree.setDragDropMode(QAbstractItemView.InternalMove)

        self.componentTree.viewport().setAcceptDrops(True)
        self.componentTree.setDragEnabled(True)
        self.componentTree.setDropIndicatorShown(True)
        self.componentTree.setDragDropMode(QAbstractItemView.InternalMove)

        self.stCalculatedItems = []
        self.ctCalculatedItems = []

        self.component_names = self.componentNames()
        self.notYetManualWarned = True

        # variables for expanding and collapsing in levels
        self.componentViewLevel = 2
        self.subsetViewDataLevel = 1
        self.subsetViewSubsetLevel = 3

        self.currentColumns = ["{Mean}", "{Median}", "{Minimum}", "{Maximum}", "{Sum}"]

    def addColumn(self):
        '''
        Function that is called when user presses new column button on toolbar.
        Creates a new column with a mathematical expression.
        '''
        self.widget = QWidget()
        self.widget.setWindowFlags(Qt.WindowContextHelpButtonHint | Qt.WindowCloseButtonHint)
        self.widget.setWhatsThis("To see information on how to use this feature, go to Glue's"
                                 "documentation at https://github.com/glue-viz/glue")
        self.widget.setFixedWidth(700)
        # self.widget.setFixedSize(700, 450)
        # self.widget.setWindowFlag(Qt.WindowContextHelpButtonHint, True)
        # title = "New Column"
        # message = "Enter new column name"
        instr = QLabel("<p><strong>Note: </strong>Attribute names in the expression should be "
                       "surrounded <br> by { } brackets (e.g. {Component}), and you can use Numpy "
                       "functions using np.<function>, Pandas, <br> math or any library defined in "
                       "the config file</p>")
        instr.setTextFormat(1)
        self.expressionEditor = QTextEdit()
        # self.expressionEditor.setFixedSize(650, 175)
        # self.expressionEditor.resize(50, 60)
        self.expressionEditor.setPlaceholderText(
            "Type any mathematical expression here - you can include attribute names from "
            "the drop-down below by selecting them and clicking 'Insert'. Press the ? button "
            "for examples of valid expressions and more information.")
        self.expressionEditor.textChanged.connect(self.highlightAttributes)

        self.columnNameLine = QLineEdit()
        # self.columnNameLine.setFixedWidth(300)
        self.columnNameLine.setPlaceholderText("New column name")
        self.columnNameLine.textChanged.connect(self.checkColumnNameExists)
        equalsLabel = QLabel("=")

        layoutName = QHBoxLayout()
        layoutName.addWidget(self.columnNameLine)
        layoutName.addWidget(equalsLabel)
        layoutName.setAlignment(Qt.AlignTop)

        insert = QPushButton("Insert Column: ")
        insert.clicked.connect(self.insertAttribute)

        layout = QHBoxLayout()
        layout.addWidget(instr)

        layout2 = QHBoxLayout()
        layout2.setAlignment(Qt.AlignTop)

        # layout2.addWidget(QLabel("Arthimetic Expression:"))
        layout2.addWidget(self.expressionEditor)

        self.statsCombo = QComboBox()

        for statistic in self.headings:
            if statistic != "Name":
                self.statsCombo.addItem(statistic)

        # self.statsCombo.addItem("Size")

        layout3 = QHBoxLayout()
        layout3.setAlignment(Qt.AlignTop)

        insertComp = QPushButton("Insert Component")
        insertComp.clicked.connect(lambda: self.expressionEditor.insertPlainText("{Component}"))
        # layout9 = QHBoxLayout()
        # layout3.addWidget(QLabel("Insert Component:"))
        layout3.addWidget(insertComp)

        # layout3.addWidget(QLabel("Insert Column:"))
        layout3.addWidget(insert)
        layout3.addWidget(self.statsCombo)
        # layout3.setAlignment(Qt.AlignTop)

        layoutExamples = QHBoxLayout()
        layoutExamples.setAlignment(Qt.AlignTop)
        exampleExpr = QLabel()
        exampleExpr.setTextFormat(1)
        exampleExpr.setText("<p><strong>Example Expressions:</strong><br>- np.std({Component})<br>"
                            "- np.sum({Maximum}-{Minimum})*2</p>")
        layoutExamples.addWidget(exampleExpr)

        layout4 = QHBoxLayout()

        self.setNameLabel = QLabel()
        self.setNameLabel.setTextFormat(1)
        self.setNameLabel.setText("<p><span style=\"color: #ff0000;\">"
                                  "Attribute name not set"
                                  "</span></p>")
        self.submit = QPushButton("Ok")
        self.submit.setEnabled(False)
        self.submit.clicked.connect(self.createNewColumn)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.widget.close)
        layout4.addWidget(self.setNameLabel)
        layout4.addWidget(cancel)
        layout4.addWidget(self.submit)
        # layout4.setAlignment(Qt.AlignTop)
        # layout.addRow(submit, cancel)

        mainLayout = QVBoxLayout()
        mainLayout.setAlignment(Qt.AlignTop)
        mainLayout.addLayout(layoutName)
        mainLayout.addLayout(layout2)
        mainLayout.addLayout(layout3)
        mainLayout.addLayout(layout)
        mainLayout.addLayout(layoutExamples)
        mainLayout.addLayout(layout4)

        self.widget.setLayout(mainLayout)
        self.widget.setWindowTitle("Add Custom Column")
        self.widget.show()

        # layout.addRow(QInputDialog.getItem(widget, title, message))

        # self.le = QLineEdit()
        # layout.addRow(instr, self.le)
        # layout.addRow(QInputDialog.getItem(widget, title, message), self.le)
        # le = QLineEdit()

        # btn1 = QPushButton("get name")
        # btn1.clicked.connect(gettext)

    def checkColumnNameExists(self):
        '''
        Sets the red text at bottom left screen of add column menu to red or makes it go away
        '''
        if self.columnNameLine.text() == "":
            self.setNameLabel.setText("<p><span style=\"color: #ff0000;\">" + "Attribute name not set" + "</span></p>")
            self.submit.setEnabled(False)

        elif self.columnNameLine.text() in self.headings:
            self.setNameLabel.setText("<p><span style=\"color: #ff0000;\">" + "Column already defined" + "</span></p>")
            self.submit.setEnabled(False)

        else:
            self.setNameLabel.setText('')
            self.submit.setEnabled(True)

    def highlightAttributes(self):
        self.expressionEditor.blockSignals(True)
        cursorLocation = self.expressionEditor.textCursor()
        print(cursorLocation)
        text = self.expressionEditor.toPlainText()

        html = "<p>"
        print(text)
        for headings in self.headings:
            if '{' + headings + '}' in text:
                text = text.replace('{' + headings + '}', "<span style=\"color: #3366ff;\"><strong>" + '{' + headings + '}' + "</strong></span>")
            if "{Component}" in text:
                text = text.replace("{Component}", "<span style=\"color: #3366ff;\"><strong>" + "{Component}" + "</strong></span>")
        html += text

        html += "</p>"
        print(html)
        self.expressionEditor.clear()
        self.expressionEditor.insertHtml(html)
        # self.expressionEditor.setTextCursor(cursorLocation)
        self.expressionEditor.blockSignals(False)

    def createNewColumn(self, expression):
        print("made new column")
        columnName = self.columnNameLine.text()
        expr = str(self.expressionEditor.toPlainText())
        try:
            columnValues, subsetValues = self.calculateNewColumn(expr)
            # columnValues = [1, 2, 3, 4, 5] test values
            print("Done!", columnValues)

            # Add column to viewer
            # subset view

            self.headings.append(str(columnName))
            self.subsetTree.setColumnCount(len(self.headings))
            self.componentTree.setColumnCount(len(self.headings))
            QTreeWidget.setHeaderLabels(self.subsetTree, self.headings)
            QTreeWidget.setHeaderLabels(self.componentTree, self.headings)

            self.populateNewColumn(columnValues, subsetValues)

        except Exception as e:
            print(e)
            np.set_printoptions(threshold=False)
            QMessageBox.warning(None, 'Error', 'Could not evaluate code: ' + str(e))
            return

    def populateNewColumn(self, columnValues, subsetValues):
        '''For Data'''
        # Subset View
        data_branch = self.subsetTree.invisibleRootItem().child(0)
        print('okk', columnValues)
        for data_i in range(0, data_branch.childCount()):
            for comp_i in range(0, data_branch.child(data_i).childCount()):
                value = self.changeNotationForCustomColumnValues(columnValues[comp_i])
                # print(type(columnValues[comp_i]))
                temp = self.subsetTree.indexFromItem(data_branch.child(data_i).child(comp_i))
                self.subsetTree.itemFromIndex(temp).setData(len(self.headings)-1, 0, value)
                print("subset view added")
        # Component View
        data_branch = self.componentTree.invisibleRootItem()
        for data_i in range(0, data_branch.childCount()):
            for comp_i in range(0, data_branch.child(data_i).childCount()):
                value = self.changeNotationForCustomColumnValues(columnValues[comp_i])
                # print(type(columnValues[comp_i]))
                # adds values for All Data rows in datasets
                temp = self.componentTree.indexFromItem(data_branch.child(data_i).child(comp_i).child(0))
                self.componentTree.itemFromIndex(temp).setData(len(self.headings)-1, 0, value)
                print("component view added")

        '''For Subsets'''
        # Subset View
        index = 0
        data_branch = self.subsetTree.invisibleRootItem().child(1)
        for subset_i in range(0, data_branch.childCount()):
            for data_i in range(0, data_branch.child(subset_i).childCount()):
                for comp_i in range(0, data_branch.child(subset_i).child(data_i).childCount()):
                    if not data_branch.child(subset_i).child(data_i).child(comp_i).foreground(0) == QtGui.QBrush(Qt.gray):
                        value = self.changeNotationForCustomColumnValues(subsetValues[index])
                        temp = self.subsetTree.indexFromItem(data_branch.child(subset_i).child(data_i).child(comp_i))
                        self.subsetTree.itemFromIndex(temp).setData(len(self.headings)-1, 0, value)
                        index += 1
                        print("Subset view subset added")

        # Component View
        index = 0
        data_branch = self.componentTree.invisibleRootItem()
        for data_i in range(0, data_branch.childCount()):
            for subset_i in range(0, len(self.xc.subset_groups)):
                subset_i += 1
                for comp_i in range(0, data_branch.child(data_i).childCount()):
                    if not data_branch.child(data_i).child(comp_i).child(subset_i).foreground(0) == QtGui.QBrush(Qt.gray):
                        value = self.changeNotationForCustomColumnValues(subsetValues[index])
                        temp = self.componentTree.indexFromItem(data_branch.child(data_i).child(comp_i).child(subset_i))
                        self.componentTree.itemFromIndex(temp).setData(len(self.headings)-1, 0, value)
                        index += 1
                        print("component view subset added")

    def calculateNewColumn(self, expr):
        '''
        TODO: This method is super laggy. split() method is slow and eval itself is slow.
        '''
        columnValues = []
        subsetValues = []
        np.set_printoptions(threshold=sys.maxsize)

        # start loading screen
        # self.animation_label = QLabel("Loading...")
        # self.animation_layout = QVBoxLayout()
        # self.animation_layout.addWidget(self.animation_label)
        # self.loadingScreen = QWidget()
        # self.loadingScreen.setFixedSize(200, 200)
        # self.loadingScreen.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.CustomizeWindowHint)
        # self.loadingScreen.setLayout(self.animation_layout)
        self.loadingScreen = QMessageBox()
        self.loadingScreen.setWindowFlags(Qt.CustomizeWindowHint | Qt.WindowTitleHint | Qt.FramelessWindowHint)
        self.loadingScreen.setFixedSize(200, 200)
        self.loadingScreen.setInformativeText("Loading...")
        # self.loadingScreen.setStandardButtons(QMessageBox.close)
        self.loadingScreen.exec()

        # self.loadingMovie = QMovie('jk317/glue/icons/glue_buffering.png')
        # if not self.loadingMovie.isValid():
        #    print("not valid")
        # self.pixmap = QPixmap('jk317/glue/icons/glue_buffering.png')
        # self.animation_label.setPixmap(self.pixmap)
        # self.animation_label.setMovie(self.loadingMovie)
        # self.loadingMovie.start()d

        currentlyActiveDatasets = self.getActiveDatasetsInPlotLayer()
        # Uses component variable
        for dataset in self.xc:
            if dataset.label in currentlyActiveDatasets:
                for comp in range(0, len(dataset.components)):
                    code = expr
                    # uses predefined columns
                    for index in range(0, len(self.headings)):
                        if "{" + self.headings[index]+"}" in expr:
                            columnArray = self.getColumnArray(index)
                            # columnArray = np.array(columnArray)
                            code = code.replace("{" + self.headings[index]+"}", str(columnArray[comp]))
                            # print(code)
                            # columnValues.append(answer)
                            # if Component is not used, then we can exit early
                            # if not "{Component}" in expr:
                            #    answer = eval(org.replace("{" + self.headings[index]+"}", "np.array(" + str(columnArray)+")"))
                            #    np.set_printoptions(threshold=False)
                            #    self.widget.close()
                            #    return answer

                    import timeit

                    if "{Component}" in expr:
                        # print("Calculating" , dataset.components[comp], "...")
                        start = timeit.default_timer()

                        # str(array) results in an array without commas, which cannot be evaluated.
                        # Need to manipulate array string so it has commas.

                        # print(type(dataset["PRIMARY"]))
                        dataList = dataset[str(dataset.components[comp])]
                        # dataList = np.ndarray([elem for elem in dataList if type(elem) == int or type(elem) == np.double or type(elem) ==float])
                        dataList = np.array2string(dataList, separator=',')
                        '''
                        print("converting ...")
                        dataList = str(dataList)
                        print("splitting ...")
                        dataList = ", ".join(dataList.split())
                        print("replacing ...")
                        dataList = dataList.replace("[, ", "[")
                        # need to create a copy of expr because each {Component} will be different component for the loop
                        '''
                        code = code.replace("{Component}", dataList)
                        code = code.replace("nan, ", "")
                        code = code.replace("nan", "")
                        # print(code)
                        try:
                            print("evaluating ...")
                            answer = eval(code)
                        except:
                            print("Did not calculate")
                            answer = "NAN"
                            # break
                        stop = timeit.default_timer()
                        print('Time: ', stop - start)
                        columnValues.append(answer)

                    # No components or predefined columns used: these are simple expressions like 1+1 or "test value"
                    else:
                        answer = eval(code)
                        columnValues.append(answer)

        # subsets
        for subset_i in range(0, len(self.xc.subset_groups)):
            for data_i in range(0, len(self.xc)):
                if self.xc[data_i].label in currentlyActiveDatasets:
                    for comp_i in self.xc.subset_groups[subset_i].subsets[data_i].components:
                        code = expr
                        print("DOING SUBSETS", comp_i)
                        for index in range(0, len(self.headings)):
                            if "{" + self.headings[index]+"}" in expr:
                                columnArray = self.getSubsetArray(index)
                                # columnArray = np.array(columnArray)
                                code = code.replace("{" + self.headings[index]+"}", str(columnArray[comp]))

                        if "{Component}" in expr:
                            start = timeit.default_timer()
                            try:
                                print("Calculating", self.xc.subset_groups[subset_i].subsets[data_i][comp_i], "...")
                            except:
                                break
                            start = timeit.default_timer()

                            # str(array) results in an array without commas, which cannot be evaluated.
                            # Need to manipulate array string so it has commas.

                            # print(type(dataset["PRIMARY"]))
                            # get values of subset and modify it
                            dataList = np.array2string(self.xc.subset_groups[subset_i].subsets[data_i][comp_i], separator=',')

                            code = code.replace("{Component}", dataList)
                            code = code.replace("nan, ", "")
                            code = code.replace("nan", "")
                            # print(code)
                            try:
                                print("evaluating ...")
                                answer = eval(code)
                            except:
                                print("Did not calculate")
                                answer = "NAN"
                            stop = timeit.default_timer()
                            print('Time: ', stop - start)
                            subsetValues.append(answer)

                        # No components or predefined columns used:
                        # these are simple expressions like 1+1 or "test value"
                        else:
                            answer = eval(code)
                            subsetValues.append(answer)

        # self.loadingMovie.stop()
        self.loadingScreen.setInformativeText("Done!")
        self.loadingScreen.close()

        '''
        subset_branch = self.subsetTree.invisibleRootItem().child(1)
        for subset_i in range(0, len(self.xc.subset_groups)):
            for data_i in range(0, len(self.xc)):
                for comp_i in range(0, len(self.xc[data_i].components)):
                    d
        '''
        np.set_printoptions(threshold=False)
        print(subsetValues)
        self.widget.close()
        print(self.state.layers)
        return columnValues, subsetValues

    def getActiveDatasetsInPlotLayer(self):
        '''
        Returns the list of datasets in the Plotlayer of the stats viewer
        '''
        names = []
        # if 0, then return datasets

        for message in self.state.layers:
            print(message)
            # get the data name
            if "label: " in str(message):
                index1 = str(message).index("label: ") + len("label: ")
                index2 = str(message).index(")\nvisible: ")
                names.append(str(message)[index1:index2])
            elif "data: " in str(message):
                index1 = str(message).index("data: ") + len("data: ")
                index2 = str(message).index(")\nvisible: ")
                names.append(str(message)[index1:index2])

        print(names)
        return names

    def changeNotationForCustomColumnValues(self, value):
        if type(value) == str:
            return value
        if self.isSci:
            # Format in scientific notation
            string = "%." + str(self.num_sigs) + 'E'
        else:
            string = "%." + str(self.num_sigs) + 'F'

        return string % value

    def getSubsetArray(self, columnIndex):
        temp = []
        st = self.subsetTree.invisibleRootItem().child(1)
        for x in range(0, st.childCount()):
            for y in range(0, st.child(x).childCount()):
                for z in range(0, st.child(x).child(y).childCount()):
                    item = self.subsetTree.indexFromItem(st.child(x).child(y).child(z))
                    if self.subsetTree.itemFromIndex(item).data(3, 0) is not None:
                        temp.append(self.subsetTree.itemFromIndex(item).data(columnIndex, 0))
        temp = [float(x.strip(' "')) for x in temp]
        return temp

    def getColumnArray(self, columnIndex):
        '''
        return the calculated data for a custom column with columnIndex
        '''
        temp = []
        st = self.subsetTree.invisibleRootItem().child(0)
        for x in range(0, st.childCount()):
            for y in range(0, st.child(x).childCount()):
                item = self.subsetTree.indexFromItem(st.child(x).child(y))

                if self.subsetTree.itemFromIndex(item).data(3, 0) is not None:
                    temp.append(self.subsetTree.itemFromIndex(item).data(columnIndex, 0))
        # subset
        # st = self.subsetTree.invisibleRootItem().child(1)
        # for x in range(0, st.childCount()):
        #    for y in range(0, st.child(x).childCount()):
        #        for z in range(0, st.child(x).child(y).childCount()):
        #            item = self.subsetTree.indexFromItem(st.child(x).child(y).child(z))
        #            if self.subsetTree.itemFromIndex(item).data(3, 0) is not None:
        #                temp.append(self.subsetTree.itemFromIndex(item).data(columnIndex, 0))
        # print(temp)
        temp = [float(x.strip(' "')) for x in temp]
        return temp

    def insertAttribute(self):
        print("insert attribute")

        attribute = "{" + str(self.statsCombo.currentText()) + "}"

        # string  = QString(attribute)
        # string.setTextColor(Qt.blue)
        self.expressionEditor.insertPlainText(attribute)
        '''
        text = self.expressionEditor.toPlainText()
        self.expressionEditor.clear()

        html =""
        addText = False
        for index in range(0, len(text)):
            if text[index] == "{":
                html += "<p><span style=\"color: #3366ff;\"><strong>"
            html+= text[index]
            if text[index] == "}":
                html += "</strong></span></p>"

        self.expressionEditor.insertHtml(html)
        '''

    def expandLevel(self):
        # subset view: tricky, there are only three levels for subsets but 4 for subsets
        if self.tabs.currentIndex() == 0:

            st = self.subsetTree.invisibleRootItem().child(0)
            for x in range(0, st.childCount()):
                st.child(x).setExpanded(True)
                for y in range(0, st.child(x).childCount()):
                    st.child(x).child(y).setExpanded(True)

            st = self.subsetTree.invisibleRootItem().child(1)
            for x in range(0, st.childCount()):
                st.child(x).setExpanded(True)
                for y in range(0, st.child(x).childCount()):
                    st.child(x).child(y).setExpanded(False)

        # component view
        elif self.tabs.currentIndex() == 1:
            if self.componentViewLevel >= 2:
                return
            self.componentViewLevel += 1
            self.expandLevelHelper(self.componentViewLevel, self.componentTree.invisibleRootItem())

    def expandLevelHelper(self, level, view):
        '''
        Heler method for minimizeLevel(self), recursive function to determine how deep the levels are
        @param: level - the int of the current level of the viewer that is expanded
        @param: view - the structure/viewtype that is being expanded
        '''

        if level > 0:
            for i in range(0, view.childCount()):
                view.child(i).setExpanded(True)
                self.expandLevelHelper(level-1, view.child(i))

        # else:
            # for i in range(0, view.childCount()):
                # view.child(i).setExpanded(True)

    def minimizeLevel(self):
        '''
        Minimizes a level of nodes in the current view
        '''
        # subset view: tricky, there are only three levels for subsets but 4 for subsets
        if self.tabs.currentIndex() == 0:

            st = self.subsetTree.invisibleRootItem().child(0)
            for x in range(0, st.childCount()):
                st.child(x).setExpanded(False)

            st = self.subsetTree.invisibleRootItem().child(1)
            for x in range(0, st.childCount()):
                st.child(x).setExpanded(False)
                for y in range(0, st.child(x).childCount()):
                    st.child(x).child(y).setExpanded(False)
                    for z in range(0, st.child(x).child(y).childCount()):
                        st.child(x).child(y).child(z).setExpanded(False)

        # component view
        elif self.tabs.currentIndex() == 1:
            if self.componentViewLevel <= 0:
                return
            self.componentViewLevel -= 1
            self.minimizeLevelHelper(self.componentViewLevel, self.componentTree.invisibleRootItem())

    def minimizeLevelHelper(self, level, view):
        '''
        Heler method for minimizeLevel(self), recursive function to determine how deep the levels are
        @param: level - the int of the current level of the viewer that is expanded
        @param: view - the structure/viewtype that is being minimized
        '''

        if level > 0:
            for i in range(0, view.childCount()):
                self.minimizeLevelHelper(level-1, view.child(i))
        else:
            for i in range(0, view.childCount()):
                view.child(i).setExpanded(False)

    def pressedEventExportToViewer(self):
        '''
        self.exportViewerWindow = QMainWindow()
        self.exportViewerWindow.resize(500, 250)
        self.exportViewerWindow.setWindowTitle("Data Viewer")
        self.exportViewerLabel = QLabel()
        self.exportViewerLabel.setText("Choose a new data viewer")
        self.exportViewerLabel.
        self.exportViewerWindow.setCentralWidget(self.exportViewerLabel)
        self.exportViewerWindow.layout().setContentsMargins(10, 10, 20, 20)
        self.exportViewerWindow.setContentsMargins(10, 10, 20, 20)
        self.exportViewerWindow.show()
        '''

        df = self.getCurrentCalculated()
        if len(df) > 1:

            from glue.config import qt_client

            self.chooseViewerWidget = QWidget()

            self.viewerCombo = QComboBox()
            for viewer_type in qt_client.members:
                self.viewerCombo.addItem(viewer_type.LABEL, viewer_type)

            label = QLabel("Choose a new data viewer:")

            layout1 = QHBoxLayout()
            layout1.addWidget(label)
            layout1.addWidget(self.viewerCombo)

            okButton = QPushButton("Ok")
            cancelButton = QPushButton("Cancel")

            okButton.clicked.connect(self.openNewViewer)
            cancelButton.clicked.connect(self.chooseViewerWidget.close)

            self.newStatsDatasetName = QLineEdit()
            label2 = QLabel("Name your new dataset:")

            layout2 = QHBoxLayout()
            layout2.addWidget(label2)
            layout2.addWidget(self.newStatsDatasetName)

            layout3 = QHBoxLayout()
            layout3.addWidget(okButton)
            layout3.addWidget(cancelButton)

            mainLayout = QVBoxLayout()
            mainLayout.addLayout(layout1)
            mainLayout.addLayout(layout2)
            mainLayout.addLayout(layout3)

            self.chooseViewerWidget.setLayout(mainLayout)
            self.chooseViewerWidget.setWindowTitle("Export to Viewer")
            self.chooseViewerWidget.show()

    def pressedEventSaveToDC(self):

        df = self.getCurrentCalculated()
        if len(df) > 1:

            self.saveStatsWidget = QWidget()

            okButton = QPushButton("Ok")
            cancelButton = QPushButton("Cancel")

            okButton.clicked.connect(self.saveToDC)
            cancelButton.clicked.connect(self.saveStatsWidget.close)

            self.newStatsDatasetName = QLineEdit()
            label1 = QLabel("Name your new dataset:")

            layout1 = QHBoxLayout()
            layout1.addWidget(label1)
            layout1.addWidget(self.newStatsDatasetName)

            layout2 = QHBoxLayout()
            layout2.addWidget(okButton)
            layout2.addWidget(cancelButton)

            mainLayout = QVBoxLayout()
            mainLayout.addLayout(layout1)
            mainLayout.addLayout(layout2)

            self.saveStatsWidget.setLayout(mainLayout)
            self.saveStatsWidget.setWindowTitle("Save Statistics to Data Collection")
            self.saveStatsWidget.show()

    def saveToDC(self):
        df = self.getCurrentCalculated()
        # viewerToOpen = self.viewerCombo.currentText()
        datasetname = self.newStatsDatasetName.text()

        if datasetname == '':
            QMessageBox.warning(None, 'Error', 'Must enter a name for new dataset')
            return
        if self.hasSameDatasetName(datasetname):
            QMessageBox.warning(None, 'Error', 'Dataset with this name already exists')
            return

        data = Data(label=str(datasetname))
        df = np.array(df)
        # transpose list
        df = df.T

        for row in df:
            data.add_component(row[1:], label=row[0])

        self.xc.append(data)
        self.saveStatsWidget.close()

    def openNewViewer(self):
        df = self.getCurrentCalculated()
        viewerToOpen = self.viewerCombo.currentData()
        datasetname = self.newStatsDatasetName.text()

        if datasetname == '':
            QMessageBox.warning(None, 'Error', 'Must enter a name for new dataset')
            return
        if self.hasSameDatasetName(datasetname):
            QMessageBox.warning(None, 'Error', 'Dataset with this name already exists')
            return

        data = Data(label=datasetname)
        df = np.array(df)
        # transpose list
        df = df.T

        for row in df:
            data.add_component(row[1:], label=row[0])

        self.xc.append(data)

        viewer = self.session.application.new_data_viewer(viewerToOpen)
        viewer.add_data(data)

        self.chooseViewerWidget.close()

    def hasSameDatasetName(self, name):
        for dataname in self.xc:
            if name == dataname.label:
                return True
        return False

    def calculateAll(self):
        if self.tabs.currentIndex() == 0:
            # self.subsetTree.selectAll()
            data_branch = self.subsetTree.invisibleRootItem().child(0)
            data_branch.setCheckState(0, 2)
            for data_i in range(0, data_branch.childCount()):
                data_branch.child(data_i).setCheckState(0, 2)
                for comp_i in range(0, data_branch.child(data_i).childCount()):
                    data_branch.child(data_i).child(comp_i).setCheckState(0, 2)
            subset_branch = self.subsetTree.invisibleRootItem().child(1)
            subset_branch.setCheckState(0, 2)
            self.check_status_helper(2, subset_branch)

        elif self.tabs.currentIndex() == 1:
            cTree = self.componentTree.invisibleRootItem()
            for data_i in range(0, cTree.childCount()):
                cTree.child(data_i).setCheckState(0, 2)
                self.check_status_helper(2, cTree.child(data_i))

        self.pressedEventCalculate()

    def plotLayerNames(self):
        '''
        returns the current list of plot layers in the glue session
        '''
        new_names = []
        only_names = []
        for message in self.state.layers:
            # get the data name
            index1 = str(message).index("layer: ") + len("layer: ")
            index2 = str(message).index("\nvisible: ")
            plot_name = str(message)[index1:index2]
            # get visiblity
            index1 = str(message).index("visible: ") + len("visible: ")
            index2 = str(message).index("\nzorder: ")
            visibility_status = str(message)[index1:index2]
            # get zorder
            index1 = str(message).index("zorder: ") + len("zorder: ")
            zorder_rank = str(message)[index1:]
            # append the information
            new_names.append((plot_name, visibility_status, zorder_rank))
            only_names.append(plot_name)
        # print(np.array(new_names))
        return np.array(new_names), np.array(only_names)

    def setdiff2d(self, A, B):
        '''
        Set difference of 2d arrays: code copied from user from post:
        https://stackoverflow.com/questions/64414944/hot-to-get-the-set-difference-of-two-2d-numpy-arrays-or-equivalent-of-np-setdif
        '''
        nrows, ncols = A.shape
        dtype = {'names': ['f{}'.format(i) for i in range(ncols)], 'formats': ncols * [A.dtype]}
        C = np.setdiff1d(A.copy().view(dtype), B.copy().view(dtype))
        return C

    def homeButtonEvent(self):
        '''
        Method that activates when the home button is pressed. This method will reset the statsviewer to its original state if any values are dragged around
        and out of order. Also a good button to press when a bug stops the viewer so it resets everything.
        '''
        # print("Homebutton event")
        # clear activePlotLayerList so it redraws everything
        self.activePlotLayerList = []
        # clear subsets so it redraws subsets properly
        self.subset_set = set()
        self.sortBySubsets()
        self.sortByComponents()


        updatedPlotLayers, updatedPlotLayerNames = self.plotLayerNames()
        for layerInfo in updatedPlotLayers:
            # each layerInfo has data, visibility, and zorder
            # print(layerInfo[0]+ ": " + layerInfo[2])

            # check visibility change
            if layerInfo[1] == 'True' and not layerInfo[0] in self.activePlotLayerList:
                # print("Homeevent info: " + layerInfo[0])
                # print("add data to viewer")
                if "Subset" in layerInfo[0]:
                    self.subsetCreatedMessage(layerInfo[0])
                else:
                    self.newDataAddedMessage(layerInfo[0])

                self.activePlotLayerList.append(layerInfo[0])
                # repopulate data that was already calculated

            elif layerInfo[1] == 'False' and layerInfo[0] in self.activePlotLayerList:
                # print("delete data from viewer")
                if "Subset" in layerInfo[0]:
                    self.deletePlotLayers('subset', layerInfo[0])
                else:
                    self.deletePlotLayers('dataset', layerInfo[0])

                self.activePlotLayerList.remove(layerInfo[0])

            # check if layer was deleted in the plot layer


            # print(layerInfo)
        dummy, self.plotlayer_names = self.plotLayerNames()
        self.repopulateViewer()

    def _on_layers_changed(self, callbacklist):
        '''
        Method called whenever a plot layer (the side panel that controls what shows up on the viewer) is changed
        @callbacklist - the callback list that contains the plotlayers (this method doesn't use this instead calls self.state to access plot layers)
        '''

        # Things that happen in a layer change: Data/subset added or removed, zorder change, and visibility toggled
        # color or name can be changed, but this functionality already added in message listeners, no need to implement here
        # print("detected layer change")
        updatedPlotLayers, updatedPlotLayerNames = self.plotLayerNames()
        # print("self ", self.plotlayer_names)
        # print("updated ", updatedPlotLayerNames)
        toBeRemovedLayer = np.setdiff1d(self.plotlayer_names, updatedPlotLayerNames)

        # print("to be removed ", toBeRemovedLayer)

        if len(toBeRemovedLayer) != 0:
            # print("removal started")
            toBeRemovedLayer = toBeRemovedLayer[0]
            # remove data/subset if it was removed in the plot layer
            if "Data (label: " in toBeRemovedLayer:
                # if dataset was removed
                index1 = str(toBeRemovedLayer).index("Data (label: ") + len("Data (label: ")
                index2 = str(toBeRemovedLayer).index(")")
                remove_name = str(toBeRemovedLayer)[index1:index2]
                # print(remove_name)
                # subset view
                data_branch = self.subsetTree.invisibleRootItem().child(0)
                for data_i in range(0, data_branch.childCount()):
                    # print("comp ", data_branch.child(data_i).child(comp_i).data(0, 0))
                    if data_branch.child(data_i).data(0, 0) == remove_name:
                        data_branch.removeChild(data_branch.child(data_i))
                # component view
                cTree = self.componentTree.invisibleRootItem()
                for data_i in range(0, cTree.childCount()):
                    if cTree.child(data_i).data(0, 0) == remove_name:
                        cTree.removeChild(cTree.child(data_i))


            elif "Subset: " in toBeRemovedLayer:
                # if subset was removed
                index1 = str(toBeRemovedLayer).index("Subset: ") + len("Subset: ")
                index2 = str(toBeRemovedLayer).index("(data: ")
                new_name = str(toBeRemovedLayer)[index1:index2]
                index3 = str(toBeRemovedLayer).index("(data: ") + len("(data: ")
                index4 = str(toBeRemovedLayer).index(")")
                remove_name = new_name + "(" + str(toBeRemovedLayer)[index3:index4] + ")"
                # print(remove_name)
                # subset view
                subset_branch = self.subsetTree.invisibleRootItem().child(1)
                for subset_i in range(0, subset_branch.childCount()):
                    for data_i in range(0, subset_branch.child(subset_i).childCount()):
                        if subset_branch.child(subset_i).child(data_i).data(0, 0) == remove_name:
                            subset_branch.removeChild(subset_branch.child(subset_i).child(data_i))
                # component view
                cTree = self.componentTree.invisibleRootItem()
                for data_i in range(0, cTree.childCount()):
                    for comp_i in range(0, cTree.child(data_i).childCount()):
                        for subset_i in range(0, cTree.child(data_i).child(comp_i).childCount()):
                            if cTree.child(data_i).child(comp_i).child(subset_i).data(0, 0) == new_name[:-1]:
                                cTree.removeChild(cTree.child(data_i).child(comp_i).child(subset_i))

            self.activePlotLayerList.remove(toBeRemovedLayer)

        # print("modified layer: items in callbacklist:")
        for layerInfo in updatedPlotLayers:
            # each layerInfo has data, visibility, and zorder
            # print(layerInfo[0]+ ": " + layerInfo[2])

            # check visibility change
            if layerInfo[1] == 'True' and not layerInfo[0] in self.activePlotLayerList:
                # print("layerinfo: " + layerInfo[0])
                # print("add data to viewer")

                if "Subset" in layerInfo[0]:
                    self.subsetCreatedMessage(layerInfo[0])
                else:
                    self.newDataAddedMessage(layerInfo[0])

                self.activePlotLayerList.append(layerInfo[0])
                # repopulate data that was already calculated
                self.repopulateViewer()
                # self.homeButtonEvent()

            elif layerInfo[1] == 'False' and layerInfo[0] in self.activePlotLayerList:
                # print("delete data from viewer")
                if "Subset" in layerInfo[0]:
                    self.deletePlotLayers('subset', layerInfo[0])
                else:
                    self.deletePlotLayers('dataset', layerInfo[0])

                self.activePlotLayerList.remove(layerInfo[0])

            # check if layer was deleted in the plot layer
            # self.disableNASubsets()

            # print(layerInfo)
        dummy, self.plotlayer_names = self.plotLayerNames()
        # self.disableNASubsets()
        # self.homeButtonEvent()
        # print("done")

    def repopulateViewer(self):
        """
        Repoplulates the Tree with values that are already calculated
        """
        newly_selected = self.stCalculatedItems
        # print(newly_selected)
        for index in range(0, len(newly_selected)):
            # print("input: " , newly_selected[index][1], newly_selected[index][2], newly_selected[index][3] )
            # Finds index of the needed data that is in the data collection. The index of the tree and the data collection is not necessarily the same.
            subset_i, data_i, comp_i = self.findIndexInDc(newly_selected[index][1], newly_selected[index][2], newly_selected[index][3])
            is_subset = (subset_i != -1)

            # Check if its a subset and if so run subset stats
            if is_subset:
                new_data = self.runSubsetStats(subset_i, data_i, comp_i)
            else:
                # Run standard data stats
                new_data = self.runDataStats(data_i, comp_i)
            # populate the subset view
            for col_index in range(3, len(new_data)):
                # print(new_data[0], new_data[1], new_data[2])
                indexItem = self.findIndexItem(new_data[0], new_data[1], new_data[2], 'subsetView')
                if not indexItem == "Not in viewer":
                    if new_data[col_index] == "NAN":
                        self.subsetTree.itemFromIndex(indexItem).setData(col_index-2, 0, "Error")
                    else:
                        self.subsetTree.itemFromIndex(indexItem).setData(col_index-2, 0, new_data[col_index])

        # component view
        newly_selected = self.ctCalculatedItems
        # print("length: ", len(newly_selected))
        for index in range(0, len(newly_selected)):
            # Check which view mode the tree is in to get the correct indices
            # print(newly_selected[index][1])
            subset_i, data_i, comp_i = self.findIndexInDc(newly_selected[index][1], newly_selected[index][2], newly_selected[index][3])
            is_subset = (subset_i != -1)

            # Check if its a subset and if so run subset stats
            if is_subset:
                new_data = self.runSubsetStats(subset_i, data_i, comp_i)
            else:
                # Run standard data stats
                new_data = self.runDataStats(data_i, comp_i)

            # populate the Component Tree
            for col_index in range(3, len(new_data)):

                indexItem = self.findIndexItem(new_data[0], new_data[1], new_data[2], 'componentView')
                if not indexItem == "Not in viewer":
                    # print(new_data[0], new_data[1], new_data[2])
                    if new_data[col_index] == "NAN":
                        self.componentTree.itemFromIndex(indexItem).setData(col_index-2, 0, "Error")
                    else:
                        self.componentTree.itemFromIndex(indexItem).setData(col_index-2, 0, new_data[col_index])

    def findIndexItem(self, subsetName, dataName, compName, view):
        # print("find ", subsetName)
        if view == 'subsetView':
            # subset
            subset_branch = self.subsetTree.invisibleRootItem().child(1)
            for subset_i in range(0, subset_branch.childCount()):
                if subsetName == subset_branch.child(subset_i).data(0, 0):
                    # if subset is same, then modify dataname to fit subset name in subset branch since this is a subset
                    dataName = subsetName + " (" + dataName + ")"
                    for data_i in range(0, subset_branch.child(subset_i).childCount()):
                        if dataName == subset_branch.child(subset_i).child(data_i).data(0, 0):
                            for comp_i in range(0, subset_branch.child(subset_i).child(data_i).childCount()):
                                if compName == subset_branch.child(subset_i).child(data_i).child(comp_i).data(0, 0):
                                    return self.subsetTree.indexFromItem(subset_branch.child(subset_i).child(data_i).child(comp_i))
            # data
            data_branch = self.subsetTree.invisibleRootItem().child(0)
            for d in range(0, data_branch.childCount()):
                if data_branch.child(d).data(0, 0) == dataName:
                    for c in range(0, data_branch.child(d).childCount()):
                        if data_branch.child(d).child(c).data(0, 0) == compName and subsetName == "All data":
                            return self.subsetTree.indexFromItem(data_branch.child(d).child(c))

        elif view == 'componentView':
            # print(subsetName, dataName, compName, view)
            cTree = self.componentTree.invisibleRootItem()
            if subsetName == "All data":
                subsetName = "All data (" + dataName + ")"
            for data_i in range(0, cTree.childCount()):
                if cTree.child(data_i).data(0, 0) == dataName:
                    for comp_i in range(0, cTree.child(data_i).childCount()):
                        if cTree.child(data_i).child(comp_i).data(0, 0) == compName:
                            for subset_i in range(0, cTree.child(data_i).child(comp_i).childCount()):
                                if cTree.child(data_i).child(comp_i).child(subset_i).data(0, 0) == subsetName:
                                    return self.componentTree.indexFromItem(cTree.child(data_i).child(comp_i).child(subset_i))

        return "Not in viewer"

    def deletePlotLayers(self, deletedType, message):
        # print(message)
        # index1 = str(message).index("(label: ") + len("(label: ")
        # index2 = str(message).index(")")
        # dataname = str(message)[index1:index2]
        # print("deletePlotLayers")
        temp = -1
        if deletedType == 'dataset':
            temp = 0
            index1 = str(message).index("(label: ") + len("(label: ")
            index2 = str(message).index(")")
            dataname = str(message)[index1:index2]
            # creates a list of the current values in the data_collection
            # for ds in self.xc:
            #     current_list = np.append(current_list, ds.label)
        elif deletedType == 'subset':
            temp = 1
            index1 = str(message).index("Subset: ") + len("Subset: ")
            index2 = str(message).index(" (data:")
            index3 = str(message).index(" (data: ") + len(" (data: ")
            index4 = str(message).index(")") + len(")")
            dataname = str(message)[index1:index2]
            datasetname = str(message)[index3:index4-1]
            message = dataname + " (" + datasetname + ")"

            # current_list = self.subsetNames()
        else:
            raise Exception("Invalid deleted type, method deletePlotLayers wasnt called correctly")

        try:
            '''Subset view'''
            # data branch of tree
            data_branch = self.subsetTree.invisibleRootItem().child(temp)
            child_count = data_branch.childCount()
            # creates a list of the values in the outdated tree
            past_list = []
            for i in range(child_count):
                past_list.append(data_branch.child(i))

            if len(past_list) != 0:
                # toBeRemovedQItem = ''
                # print(dataname)
                for i in range(0, len(past_list)):
                    # print(past_list[i].data(0, 0))

                    # if a dataset is being deleted
                    # if deletedType == 'dataset':
                    if past_list[i].data(0, 0) == dataname:
                        data_branch.removeChild(past_list[i])
                        break

                    # if subset, delete the subset of the corresponding dataset
                    # else:
                    #     for subdata in range(0, data_branch.child(i).childCount()):
                    #         print(message)
                    #         if data_branch.child(i).child(subdata).data(0, 0) == message:
                    #            data_branch.child(i).removeChild(data_branch.child(i).child(subdata))
                    #            break

            '''Component View'''
            # data branch of tree
            data_branch = self.componentTree.invisibleRootItem()
            child_count = data_branch.childCount()
            # print(dataname)

            if deletedType == 'dataset':
                # since removing in a loop, indexes will skip. So loop and remove backwards
                for data_i in range(data_branch.childCount()-1, -1, -1):
                    if data_branch.child(data_i).data(0, 0) == dataname:
                        data_branch.removeChild(data_branch.child(data_i))

            elif deletedType == 'subset':
                # print("removing data: ", dataname)
                # since removing in a loop, indexes will skip. So loop and remove backwards
                for data_i in range(data_branch.childCount()-1, -1, -1):
                    # if data_branch.child(data_i).data(0, 0) == datasetname:
                    for comp_i in range(data_branch.child(data_i).childCount()-1, -1, -1):
                        for subset_i in range(data_branch.child(data_i).child(comp_i).childCount()-1, -1, -1):
                            # dTemp = data_branch.child(data_i).data(0, 0)
                            # cTemP = data_branch.child(data_i).child(comp_i).data(0, 0)
                            # STemp = data_branch.child(data_i).child(comp_i).child(subset_i).data(0, 0)
                            # print("HERE", dTemp, cTemP, STemp)
                            if data_branch.child(data_i).child(comp_i).child(subset_i).data(0, 0) == dataname:
                                data_branch.child(data_i).child(comp_i).removeChild(data_branch.child(data_i).child(comp_i).child(subset_i))
                                # print("DELETED ^")
                            # print("done")

            if deletedType == 'subset':
                self.subset_set.remove(dataname)
        except:
            pass
            # self.subset_set.remove(message)

            # self.subset_set.remove(str(toBeRemoved))
            # self.subset_dict.pop(str(toBeRemovedQItem))

    def closeAllWindows(self):
        '''
        Closes all open pop-up windows if open
        '''
        # print("closed stats")
        self.decimalWindow.destroy()
        self.manualCalcWindow.destroy()
        self.instructionWindow.destroy()

    def showLargeDatasetWarning(self):
        '''
        shows the QMessageBox popup warning if it has a large dataset
        '''
        manualWarning = QMessageBox()  # .question(self, "Warning", "Confirm multiple large dataset calculations", QMessageBox.Yes , QMessageBox.Cancel )
        manualWarning.setText("There is a dataset with over 1 million values. Manual calculation has been turned on.")
        manualWarning.setInformativeText("Turn off Manual Calculation in Settings")
        manualWarning.setWindowTitle("Large Dataset Warning")
        manualWarning.addButton(QMessageBox.Ok)
        manualWarning.setDefaultButton(QMessageBox.Ok)
        # temp = manualWarning.exec()
        self.isCalcAutomatic = False

    def hasLargeData(self):
        '''
        returns true if there is a dataset with size > 1 million. Used to set the default mode for automatic/manual calculation (if large then manual, else automatic)
        '''
        for data in self.xc:
            if data.size > 1000000:
                return True  # has large data
        return False

    def createEditDecimalWindow(self):
        '''
        Creates the window used to edit decimal points shown on the stats viewer
        '''
        self.decimalWindow = QMainWindow()
        self.decimalWindow.resize(500, 250)
        self.decimalWindow.setWindowTitle("Modify Decimal Places")
        self.decLayout = QHBoxLayout()
        self.decButton = QPushButton()

        self.siglabel = QLabel()
        self.siglabel.setText('Number of decimals:')
        self.decLayout.addWidget(self.siglabel)

        self.sigfig = QSpinBox()
        self.sigfig.setRange(0, 10)
        self.sigfig.setValue(self.num_sigs)
        self.sigfig.valueChanged.connect(self.sigchange)
        self.decLayout.addWidget(self.sigfig)

        widget = QWidget()
        widget.setLayout(self.decLayout)
        self.decimalWindow.setCentralWidget(widget)

    def createManualCalcWindow(self):
        '''
        Shows the Manual Calculation toggle window from the settings menu
        '''
        # Instructions window in the settings menu, this can be more detailed about features since its not a pop up
        self.manualCalcWindow = QMainWindow()
        self.manualCalcWindow.resize(500, 250)
        self.manualCalcWindow.setWindowTitle("Toggle Manual Calculation")
        self.hManualCalcLayout = QHBoxLayout()
        self.vManualCalcLayout = QHBoxLayout()

        manualCalcLabel = QLabel("Select Calculation Type:")
        self.vManualCalcLayout.addWidget(manualCalcLabel)
        self.vManualCalcLayout.addSpacing(15)

        rb1 = QRadioButton("Automatic", self)
        rb1.toggled.connect(self.updateToAuto)
        rb2 = QRadioButton("Manual", self)
        rb2.toggled.connect(self.updateToManual)
        if self.isCalcAutomatic:
            rb1.setChecked(True)
        else:
            rb2.setChecked(True)

        self.hManualCalcLayout.addWidget(rb1)
        self.hManualCalcLayout.addWidget(rb2)

        self.vManualCalcLayout.addLayout(self.hManualCalcLayout)

        widget = QWidget()
        widget.setLayout(self.vManualCalcLayout)
        self.manualCalcWindow.setCentralWidget(widget)

    def updateToManual(self):
        '''
        Updates the calculation boolean to manual
        '''
        self.isCalcAutomatic = False

    def updateToAuto(self):
        '''
        Updates the calculation boolean to automatic
        '''
        self.isCalcAutomatic = True

    def showManualCalc(self):
        '''
        Shows the Manual Calculation toggle window from the settings menu
        '''
        self.manualCalcWindow.show()

    def showInstructions(self):
        '''
        Shows the instructions window from the settings menu
        '''
        # Instructions window in the settings menu, this can be more detailed about features since its not a pop up
        self.instructionWindow = QMainWindow()
        self.instructionWindow.resize(500, 250)
        self.instructionWindow.setWindowTitle("Instructions")
        self.instructionLabel = QLabel()
        self.instructionLabel.setTextFormat(1)
        self.instructionLabel.setText("<h2 style=\"text-align: center;\"><img src=" + str(INSTRUCTIONS_LOGO) + " width=\"46\" height=\"46\" />&nbsp;<strong>Instructions:</strong></h2><p>Tick the rows to calculate basic statistics</p><p>Click between Subset and Component views</p><p><img src=" + str(SAVE_LOGO) + " width=\"30\" height=\"30\" />&nbsp;Exports the current open tree view</p><p><img src=" + str(HOME_LOGO) + " width=\"30\" height=\"30\" />&nbsp;Resets the viewer to default layout</p><p><img src=" + str(CALCULATE_LOGO) + " width=\"30\" height=\"30\"/>&nbsp;Calculate entire view</p><p><img src=" + str(COLLAPSE_LOGO) + " width=\"30\" height=\"30\"/>&nbsp;Minimize a level</p><p><img src=" + str(EXPAND_LOGO) + " width=\"30\" height=\"30\"/>&nbsp;Expand a level</p><p><img src=" + str(NOTATION_LOGO) + " width=\"30\" height=\"30\" />&nbsp;Toggles scientific notation and decimal form</p><p><strong><img src=" + str(SORT_LOGO)+" width=\"30\" height=\"30\" />&nbsp;</strong>Enables sorting, selecting a column will sort rows accordingly</p><p><img src=" + str(INSTRUCTIONS_LOGO) + " width=\"30\" height=\"30\" />&nbsp;Read instructions</p><p><img src=" + str(SETTINGS_LOGO) + " width=\"30\" height=\"30\" />&nbsp;Change # of decimal points, instructions, etc</p><p>&nbsp;</p>")
        # self.instructionLabel.setText("<h2 style=\"text-align: center;\"><strong>Instructions:</strong></h2><p>Check the rows to calculate basic statistics</p><p>Cycle between Subset and Component views with the tabs</p><p><span style=\"color: #ff0000;\"><strong>Save</strong></span> Exports the current open tree view</p><p><span style=\"color: #ff0000;\"><strong>Home</strong></span> Resets viewer to default state</p><p><span style=\"color: #ff0000;\"><strong>Notation</strong></span> Toggles scientific notation and decimal form</p><p><span style=\"color: #ff0000;\"><strong>Sort</strong></span> Enables sorting, selecting a column will sort rows accordingly</p><p><span style=\"color: #ff0000;\"><strong>Instructions</strong></span> See how the viewer works</p><p><span style=\"color: #ff0000;\"><strong>Settings</strong></span> Change # of decimal points or toggle manual mode</p>")

        # self.instructionLabel.setText("<h2 style=\"text-align: center;\"><img src=glue_instructions.png width=\"46\" height=\"46\" />&nbsp;<strong>Instructions:</strong></h2><p>Check the rows to calculate basic statistics<p><p>Cycle between Subset and Component views with the tabs<p><p><img src=\"glue_home\" />&nbsp; Resets the viewer to default layout<p><p><span style=\"color: #ff0000;\"><strong><img src=\"SORT_LOGO\" width=\"30\" height=\"30\"/>&nbsp;</strong></span>Enables sorting, selecting a column will sort rows accordingly<p><p><img src=\"/Users/jk317/Glue/icons/glue_scientific_notation.png\" width=\"30\" height=\"30\"/>&nbsp;Toggles scientific notation and decimal form<p><p><img src='glue_filesave' width=\"30\" height=\"30\"/>Exports the current open tree view<p><p><img src=\"/Users/jk317/Glue/icons/glue_settings.png\"width=\"30\" height=\"30\" />&nbsp;to change # of decimal points or to read more instructions<p>")
        # self.instructionLabel.setText("<h2 style=\"text-align: center;\"><img src=\"/Users/jk317/Glue/icons/glue_instructions.png\" width=\"46\" height=\"46\" />&nbsp;<strong>Instructions:</strong></h2> <ul><li>Check the rows to calculate basic statistics</li><li>Cycle between Subset and Component views with the tabs</li><li>Press <span style=\"color: #ff0000;\"><strong><em>Home</em></strong></span> to collapse all rows</li><li>Press <span style=\"color: #ff0000;\"><strong><em>Refresh</em></strong></span> after linking data to check for possible calculations</li><li>Press <span style=\"color: #ff0000;\"><strong><em>Sort</em> </strong></span>to enable sorting, selecting a column will sort rows accordingly</li><li>Press <span style=\"color: #ff0000;\"><strong><em>Convert</em></strong></span> to toggle scientific notation and decimal form</li><li>Press <strong><span style=\"color: #ff0000;\"><em>Export</em></span></strong> to export the current open tree view</li><li>Press <strong><span style=\"color: #ff0000;\"><em>Settings</em></span></strong> to change # of decimal points or to read more instructions</li></ul>")
        self.instructionWindow.setCentralWidget(self.instructionLabel)

        self.instructionWindow.layout().setContentsMargins(10, 10, 20, 20)
        self.instructionWindow.setContentsMargins(10, 10, 20, 20)
        self.instructionWindow.show()

    def showNANPopup(self):
        '''
        Shows the NAN warning - subset was too small/did not intersect valid points , so there is no data to calculate. It is still technically "calculable" but no data to do so.
        '''
        # Instructions window in the settings menu, this can be more detailed about features since its not a pop up
        self.showNANWindow = QMainWindow()
        self.showNANWindow.resize(500, 250)
        self.showNANWindow.setWindowTitle("Error")
        self.showNANLabel = QLabel()
        self.showNANLabel.setTextFormat(1)
        self.showNANLabel.setText("<h2 style=\"text-align: center;\"><span style=\"color: #ff0000;\"><strong>Error</strong></span></h2><p style=\"text-align: center;\"><strong>The selected subset is too small in area/does not</strong></p><p style=\"text-align: center;\"><strong>intersect and does not contain any data to calculate.</strong></p><p style=\"text-align: center;\"><strong>Try reselecting your subset area.</strong></p>")
        self.showNANWindow.setCentralWidget(self.showNANLabel)

        self.showNANWindow.layout().setContentsMargins(10, 10, 20, 20)
        self.showNANWindow.setContentsMargins(10, 10, 20, 20)
        self.showNANWindow.show()

    def showAgainUpdate(self, buttonInfo):
        '''
        Function for the "Do not show again" logic in the instructions pop up
        @param buttonInfo: Button that triggered the function, in this case the only button (Ok button)
        '''
        global showInstructions
        # if do not show again is checked
        if self.cb.checkState() == 2:
            showInstructions = False

    def showDecimalWindow(self):
        '''
        Shows the decimal point changer window
        '''
        self.decimalWindow.show()

    def sigchange(self, i):
        '''
        Function for the decimal places change logic
        @param i: value of the integer in the QSpinBox determining decimal places
        '''
        self.num_sigs = i
        # getcontext().prec = self.num_sigs
        self.pressedEventCalculate()

    def refresh(self, message):
        '''
        action connected to Refresh Tool, enables subsets that were previously
        uncalculable to be calculated once linked
        '''

        if self.tabs.currentIndex() == 0:
            # get list of grayed out subset components
            list = []
            subset_branch = self.subsetTree.invisibleRootItem().child(1)
            for subset_i in range(0, len(self.xc.subset_groups)):
                for data_i in range(0, len(self.xc)):
                    for comp_i in range(0, len(self.xc[data_i].components)):
                        # this try statement is for if a subset is created with 1 dataset, and then another dataset is added and a new subset is created.
                        # This will mean one subeset will only have child relating to 1 data set while the other has 2 children for both datasets.
                        # If you wish to fix this by updating each subset when a dataset is added so each subset has all the dataset values, this
                        # try statement is not necessary. However, this is unnecessarily complicated (for now), so this is the solution.
                        # This is not a complete fix, as if there are subsets that need to be shown after data insertion the only way to update is to close and reopen statsviewer.
                        try:
                            if subset_branch.child(subset_i).child(data_i).child(comp_i).foreground(0) == QtGui.QBrush(Qt.gray):
                                list.append(self.subsetTree.indexFromItem(subset_branch.child(subset_i).child(data_i).child(comp_i)))
                            else:
                                break  # so it only checks one if comp isnt grayed out
                        except:
                            pass

            # checks if any of the disabled components are now linkable and re-enables it
            for index in range(0, len(list)):
                # Subsets
                data_i = list[index].parent().row()
                comp_i = list[index].row()
                subset_i = list[index].parent().parent().row()

                try:
                    # median_val = self.xc[data_i].compute_statistic('median', self.xc[data_i].subsets[subset_i].components[comp_i], subset_state=self.xc.subset_groups[subset_i].subset_state)
                    self.subsetTree.itemFromIndex(list[index]).setForeground(0, QtGui.QBrush(Qt.black))
                    # self.subsetTree.itemFromIndex(list[index]).setData(0, 0)
                    self.subsetTree.itemFromIndex(list[index]).setCheckState(0, 0)
                    self.subsetTree.itemFromIndex(list[index]).setExpanded(True)

                    self.subsetTree.itemFromIndex(list[index].parent()).setForeground(0, QtGui.QBrush(Qt.black))
                    self.subsetTree.itemFromIndex(list[index].parent()).setCheckState(0, 0)
                    self.subsetTree.itemFromIndex(list[index].parent()).setExpanded(True)
                except:
                    pass

        elif self.tabs.currentIndex() == 1:
            # print("tab")
            # get list of grayed out subset components
            list = []
            for data_i in range(0, len(self.xc)):
                for subset_i in range(0, len(self.xc[data_i].components)):
                    for comp_i in range(0, len(self.xc.subset_groups) + 1):
                        if self.componentTree.invisibleRootItem().child(data_i).child(subset_i).child(comp_i).foreground(0) == QtGui.QBrush(Qt.gray):
                            list.append(self.componentTree.indexFromItem(self.componentTree.invisibleRootItem().child(data_i).child(subset_i).child(comp_i)))
                        else:
                            pass
            # checks if any of the disabled components are now linkable and re-enables it
            for index in range(0, len(list)):
                data_i = list[index].parent().parent().row()
                comp_i = list[index].parent().row()
                subset_i = list[index].row() - 1

                try:
                    # median_val = self.xc[data_i].compute_statistic('median', self.xc[data_i].subsets[subset_i].components[comp_i], subset_state=self.xc.subset_groups[subset_i].subset_state)
                    self.componentTree.itemFromIndex(list[index]).setForeground(0, QtGui.QBrush(Qt.black))
                    # self.subsetTree.itemFromIndex(list[index]).setData(0, 0)
                    self.componentTree.itemFromIndex(list[index]).setCheckState(0, 0)
                    self.componentTree.itemFromIndex(list[index]).setExpanded(True)
                except:
                    pass

    def register_to_hub(self, hub):
        '''
        connects the StatsDataViewer to Messages that listen for changes to
        the viewer
        @param hub: takes in a HubListener object that can be connected with a Message for listening for changes
        '''
        super(StatsDataViewer, self).register_to_hub(hub)
        hub.subscribe(self, ExternallyDerivableComponentsChangedMessage, handler=self.refresh)
        hub.subscribe(self, DataCollectionDeleteMessage, handler=self.dataDeleteMessage)
        # hub.subscribe(self, SubsetCreateMessage, handler=self.subsetCreatedMessage)
        hub.subscribe(self, SubsetDeleteMessage, handler=self.subsetDeleteMessage)
        hub.subscribe(self, DataUpdateMessage, handler=self.dataUpdateMessage)
        hub.subscribe(self, SubsetUpdateMessage, handler=self.subsetUpdateMessage)
        hub.subscribe(self, EditSubsetMessage, handler=self.editSubsetMessage)
        hub.subscribe(self, LayerArtistVisibilityMessage, handler=self.layerArtistVisibilityMessage)
        hub.subscribe(self, DataAddComponentMessage, handler=self.dataAddComponentMessage)
        hub.subscribe(self, DataRenameComponentMessage, handler=self.dataRenameComponentMessage)
        hub.subscribe(self, DataRemoveComponentMessage, handler=self.dataRemoveComponentMessage)

        # hub.subscribe(self, DataCollectionAddMessage, handler=self.newDataAddedMessage)
        # hub.subscribe(self, LayerArtistDisabledMessage, handler=self.layerArtistDisabledMessage)

    def dataRemoveComponentMessage(self, message):
        '''
        Removes the data component from the stats viewer if applicable
        @param message: the message sent from the dataRemoveComponentMessage
        '''
        # print("data component removed")
        # print(message)

        new_component_names = self.componentNames()

        # print("self ", self.component_names)
        # print("new ", new_component_names)

        old_name = np.setdiff1d(self.component_names, new_component_names)[0]

        # print("old name ", old_name)

        data_branch = self.subsetTree.invisibleRootItem().child(0)

        # subset view
        for data_i in range(0, data_branch.childCount()):
            for comp_i in range(0, data_branch.child(data_i).childCount()):
                # print("comp ", data_branch.child(data_i).child(comp_i).data(0, 0))
                if data_branch.child(data_i).child(comp_i).data(0, 0) == old_name:
                    data_branch.removeChild(data_branch.child(data_i).child(comp_i))

        subset_branch = self.subsetTree.invisibleRootItem().child(1)
        for subset_i in range(0, subset_branch.childCount()):
            for data_i in range(0, subset_branch.child(subset_i).childCount()):
                for comp_i in range(0, subset_branch.child(subset_i).child(data_i).childCount()):
                    if subset_branch.child(subset_i).child(data_i).child(comp_i).data(0, 0) == old_name:
                        subset_branch.removeChild(subset_branch.child(subset_i).child(data_i).child(comp_i))

        # component view
        cTree = self.componentTree.invisibleRootItem()
        for data_i in range(0, cTree.childCount()):
            for comp_i in range(0, cTree.child(data_i).childCount()):
                if cTree.child(data_i).child(comp_i).data(0, 0) == old_name:
                    cTree.removeChild(cTree.child(data_i).child(comp_i))

        # update component list
        self.component_names = self.componentNames()

    def dataRenameComponentMessage(self, message):
        print("data component renamed")
        print(message)

        index1 = str(message).index("Derived components:") + len("Derived components:")
        index2 = str(message).index("\nCoordinate components:")
        new_name = str(message)[index1:index2]
        new_name = new_name[4:]
        # print(new_name)

        data_branch = self.subsetTree.invisibleRootItem().child(0)
        # update the new component names list
        new_component_names = self.componentNames()

        # print("self ", self.component_names)
        # print("new ", new_component_names)

        old_name = np.setdiff1d(self.component_names, new_component_names)[0]

        # print("old name ", old_name)

        # subset view
        for data_i in range(0, data_branch.childCount()):
            for comp_i in range(0, data_branch.child(data_i).childCount()):
                # print("comp ", data_branch.child(data_i).child(comp_i).data(0, 0))
                if data_branch.child(data_i).child(comp_i).data(0, 0) == old_name:
                    data_branch.child(data_i).child(comp_i).setData(0, 0, new_name)

        subset_branch = self.subsetTree.invisibleRootItem().child(1)
        for subset_i in range(0, subset_branch.childCount()):
            for data_i in range(0, subset_branch.child(subset_i).childCount()):
                for comp_i in range(0, subset_branch.child(subset_i).child(data_i).childCount()):
                    if subset_branch.child(subset_i).child(data_i).child(comp_i).data(0, 0) == old_name:
                        subset_branch.child(subset_i).child(data_i).child(comp_i).setData(0, 0, new_name)

        # component view
        cTree = self.componentTree.invisibleRootItem()
        for data_i in range(0, cTree.childCount()):
            for comp_i in range(0, cTree.child(data_i).childCount()):
                if cTree.child(data_i).child(comp_i).data(0, 0) == old_name:
                    cTree.child(data_i).child(comp_i).setData(0, 0, new_name)

        self.component_names = self.componentNames()

    def componentNames(self):
        '''
        returns a list of every component in the stats viewer
        '''
        return np.array([c.label for data in self.xc for c in data.components])

    def dataAddComponentMessage(self, message):

        '''
        Updates the stats viewer if a component is added to a data set in the viewer.
        @param message: Message given by the event, contains details about how it was triggered
        '''

        # if the component's dataset is in the stats viewer, add compoenent
        if dataname in self.data_names:

            # subset view
            sTree = self.subsetTree.invisibleRootItem().child(0)
            for x in range(0, sTree.childCount()):
                if sTree.child(x).data(0, 0) == dataname:
                    sParentItem = sTree.child(x)
                    # the index of the component in dc
                    j = sTree.child(x).childCount()
            # the index of the dataset in dc
            i = self.data_names.index(dataname)
            # print(j, self.data_names)
            childItem = QTreeWidgetItem(sParentItem)
            childItem.setCheckState(0, 0)
            childItem.setData(0, 0, '{}'.format(str(self.xc[i].components[j])))
            childItem.setIcon(0, helpers.layer_icon(self.xc[i]))

            # component view
            # print("started component view")
            cTree = self.componentTree.invisibleRootItem()
            # find parent item
            for x in range(0, cTree.childCount()):
                if cTree.child(x).data(0, 0) == dataname:
                    cParentItem = cTree.child(x)
                    # print("found parent")
                    # the index of the component in dc
                    k = cTree.child(x).childCount()

            # add the component to the viewer
            child = QTreeWidgetItem(cParentItem)
            child.setData(0, 0, '{}'.format(str(self.xc[i].components[j])))
            # child.setIcon(0, helpers.layer_icon(self.xc[i]))
            child.setCheckState(0, 0)
            child.setExpanded(True)

            # add the all data section to the component
            childtwo = QTreeWidgetItem(child)
            childtwo.setData(0, 0, '{}'.format('All data (' + self.xc.labels[i] + ')'))
            childtwo.setIcon(0, helpers.layer_icon(self.xc[i]))
            childtwo.setCheckState(0, 0)

            # if there are subsets, then add to the new component
            if not len(self.xc.subset_groups) == 0:
                disableSubset = False
                temp = False
                for j in range(0, len(self.xc.subset_groups)):
                    childtwo = QTreeWidgetItem(child)
                    childtwo.setData(0, 0, '{}'.format(self.xc.subset_groups[j].label))
                    childtwo.setIcon(0, helpers.layer_icon(self.xc.subset_groups[j]))
                    childtwo.setCheckState(0, 0)
                    if (not disableSubset) and (not temp):
                        try:
                            self.xc[i].compute_statistic('minimum', self.xc[i].subsets[j].components[k], subset_state=self.xc.subset_groups[j].subset_state)
                            temp = True
                        except:
                            disableSubset = True
                    if disableSubset:
                        childtwo.setData(0, Qt.CheckStateRole, QVariant())
                        childtwo.setForeground(0, QtGui.QBrush(Qt.gray))
                    self.num_rows = self.num_rows + 1
            # print("ended component view")
        self.component_names = self.componentNames()

    def layerArtistDisabledMessage(self, message):
        print("Layer artist disabled")
        # print(message)

    def layerArtistVisibilityMessage(self, message):
        '''
        detects when a plot layer becomes checked/unchecked
        '''
        # print("layer artist check/uncheck detected")

        # print(message)
        # print("hi")

    def editSubsetMessage(self, message):
        '''
        Clears calculated subsets of edited subsets in the viewer so they
        can be recalculated
        @param message: Message given by the event, contains details about how it was triggered
        '''
        # print("edit detected")
        editedSubset = ''
        # the sender._edit_subset is a list that has only one element, but use for loop just in case
        # print(message.sender._edit_subset)
        for x in message.sender._edit_subset:
            editedSubset = x.label

        # print("subset name: " + str(editedSubset))
        if not editedSubset == '':
            # update the subset view
            # list = []
            subset_branch = self.subsetTree.invisibleRootItem().child(1)
            # j = ''
            # grandparent = ''
            for subset_i in range(0, subset_branch.childCount()):
                subset_group = subset_branch.child(subset_i)
                if subset_branch.child(subset_i).data(0, 0) == editedSubset:
                    for data in range(0, subset_group.childCount()):
                        for component in range(0, subset_group.child(data).childCount()):
                            item = self.subsetTree.indexFromItem(subset_branch.child(subset_i).child(data).child(component))
                            # print(subset_group.child(data).child(component).data(0, 0))
                            # print(self.subsetTree.itemFromIndex(item).data(1, 0))
                            # print(self.subsetTree.itemFromIndex(item).data(2, 0))
                            if self.subsetTree.itemFromIndex(item).data(1, 0) is None:
                                # print("empty")
                                break  # nothing is calculated, automatically updated
                            elif subset_group.data(0, 0) == editedSubset and self.subsetTree.itemFromIndex(item).data(1, 0) is not None:
                                # print("remove values")
                                # item = self.subsetTree.indexFromItem(subset_branch.child(subset_i).child(data).child(component))

                                data_i = item.parent().row()
                                comp_i = item.row()
                                subset_i = item.parent().parent().row()

                                subset_label = self.xc[data_i].subsets[subset_i].label
                                data_label = self.xc[data_i].label
                                comp_label = self.xc[data_i].components[comp_i].label  # add to the name array to build the table
                                # Build the cache key
                                cache_key = subset_label + data_label + comp_label

                                self.cache_stash.pop(cache_key)
                                for col in range(1, 6):
                                    self.subsetTree.itemFromIndex(item).setData(col, 0, None)

            # update the component view
            ct = self.componentTree.invisibleRootItem()
            for d in range(0, ct.childCount()):
                for c in range(0, ct.child(d).childCount()):
                    for s in range(0, ct.child(d).child(c).childCount()):
                        item = self.componentTree.indexFromItem(self.componentTree.invisibleRootItem().child(d).child(c).child(s))
                        if self.componentTree.itemFromIndex(item).data(1, 0) is None:
                            break
                        elif ct.child(d).child(c).child(s).data(0, 0) == editedSubset and self.componentTree.itemFromIndex(item).data(1, 0) is not None:
                            data_i = item.parent().parent().row()
                            comp_i = item.parent().row()
                            subset_i = item.row() - 1

                            subset_label = self.xc[data_i].subsets[subset_i].label
                            data_label = self.xc[data_i].label
                            comp_label = self.xc[data_i].components[comp_i].label

                            # Build the cache key
                            cache_key = subset_label + data_label + comp_label
                            self.cache_stash.pop(cache_key)
                            for col in range(1, 6):
                                self.componentTree.itemFromIndex(item).setData(col, 0, None)
            self.pressedEventCalculate()

    def check_status(self, item, col):
        '''
        Enables hierachial box checks and unchecks
        @param item: QTreewidgetItem that has been checked/unchecked
        @param col: Column number of the action
        '''
        if self.isCalcAutomatic:
            # if being checked
            if item.checkState(0):
                # print("checked")
                # if the data branch is selected, check everything under data branch
                # print("AIUEFAIWEB")
                self.check_status_helper(2, item)

            # being unchecked
            else:
                # print("OH NO")
                # print("unchecked")
                # 0 means to uncheck NOTE: This is different then checkState. 0 for checkState means it is checked
                self.check_status_helper(0, item)
            self.pressedEventCalculate()

        # if calculation in in manual mode
        else:
            # if item.childCount() == 0 and

            if item.checkState(0):
                # if checked before, or has no children(single component calculation) then act like automatic
                if item in self.alreadyChecked or item.childCount() == 0:
                    self.check_status_helper(2, item)
                    self.pressedEventCalculate()

                # if not already checked, show warning
                elif item not in self.alreadyChecked:
                    self.showManualWarning()
                    # if the calc was confirmed by user
                    if self.confirmedCalc:
                        self.alreadyChecked.append(item)
                        self.check_status_helper(2, item)
                        self.pressedEventCalculate()
                    # calc was cancelled by user, undo check and return
                    else:
                        item.setCheckState(0, 0)
                        return
            # if being unchecked
            else:
                self.check_status_helper(0, item)

    def check_status_helper(self, state, dataset):
        '''
        Helper method for check_status(self, item , col)
        @param state: Number representing whether the action was check/uncheck
        @param dataset: QTreewidgetItem that has been checked/unchecked
        '''
        dataset_count = dataset.childCount()
        if state == 2:
            dataset.setExpanded(True)
        if state == 0:
            dataset.setExpanded(False)
        for x in range(dataset_count):
            attribute_count = dataset.child(x).childCount()
            # If not grayed out, check box
            if not dataset.child(x).foreground(0) == QtGui.QBrush(Qt.gray):
                dataset.child(x).setCheckState(0, state)
                # if checked, expand
                if state == 2:
                    if not dataset.child(x) in self.alreadyChecked:
                        self.alreadyChecked.append(dataset.child(x))
                    dataset.child(x).setExpanded(True)
                else:
                    dataset.child(x).setExpanded(False)
            for y in range(attribute_count):
                sub_attribute_count = dataset.child(x).child(y).childCount()
                if not dataset.child(x).child(y).foreground(0) == QtGui.QBrush(Qt.gray):
                    dataset.child(x).child(y).setCheckState(0, state)
                    if state == 2:
                        if not dataset.child(x).child(y) in self.alreadyChecked:
                            self.alreadyChecked.append(dataset.child(x).child(y))
                        dataset.child(x).child(y).setExpanded(True)
                    else:
                        dataset.child(x).child(y).setExpanded(False)
                # Only the subset section of the tree should be able to reach here
                for z in range(sub_attribute_count):
                    if not dataset.child(x).child(y).child(z).foreground(0) == QtGui.QBrush(Qt.gray):
                        dataset.child(x).child(y).child(z).setCheckState(0, state)
                        if state == 2:
                            if not dataset.child(x).child(y).child(z) in self.alreadyChecked:
                                self.alreadyChecked.append(dataset.child(x).child(y).child(z))
                            dataset.child(x).child(y).child(z).setExpanded(True)
                        else:
                            dataset.child(x).child(y).child(z).setExpanded(False)

    def showManualWarning(self):
        '''
        Shows the Manual Calculation confirmation
        '''
        if self.notYetManualWarned:
            manualWarning = QMessageBox()  # .question(self, "Warning", "Confirm multiple large dataset calculations", QMessageBox.Yes , QMessageBox.Cancel )
            manualWarning.setText("Confirm Calculation of multiple large datasets")
            manualWarning.setInformativeText("Turn off Manual Calculation in Settings")
            manualWarning.setStandardButtons(QMessageBox.Cancel)
            manualWarning.addButton(QMessageBox.Ok)
            manualWarning.setDefaultButton(QMessageBox.Cancel)
            temp = manualWarning.exec()
            # print(temp)
            if temp == QMessageBox.Ok:
                # print("ok")
                self.confirmedCalc = True
            if temp == QMessageBox.Cancel:
                # print("cancel")
                self.confirmedCalc = False
            self.notYetManualWarned = False

    def subsetNames(self):
        '''
        returns the current list of subsets in the glue session
        '''
        new_names = []
        for x in self.xc.subset_groups:
            new_names.append(x.label)
        return np.array(new_names)

    def subsetUpdateMessage(self, message):
        '''
        Updates the attributes of the edited subset (glue's left side panel info - names and color)
        @param message: Message given by the event, contains details about how it was triggered
        '''
        # print(message)
        # print("update detected")
        index1 = str(message).index("Subset: ") + len("Subset: ")
        index2 = str(message).index(" (data: ")
        index3 = str(message).index(")")
        new_name = str(message)[index1:index2]
        data_name = str(message)[index2:index3]

        new_names = self.subsetNames()
        new_names = np.array(new_names)
        old_name = np.setdiff1d(self.subset_names, new_names)
        # print(self.subset_names)

        # update both tree views
        self.subsetViewSubsetUpdateHelper(self.subsetTree.invisibleRootItem().child(1), old_name, new_name, data_name)
        self.componentViewSubsetUpdateHelper(self.componentTree.invisibleRootItem(), old_name, new_name, data_name)

        self.subset_names = self.subsetNames()

    def componentViewSubsetUpdateHelper(self, viewType, old_name, new_name, data_name):
        '''
        Updates the component view if a subset atrribute is changed
        @param viewType: the QTreeWidget Tree that is being modified (subsetTree, componentTree)
        @param old_name: old name of the edited subset
        @param new_name: new name of the edited subset
        '''
        # for subset view
        subset_branch = viewType
        child_count = subset_branch.childCount()
        if len(old_name) == 0:
            # the name has not changed, so changed color
            old_name = "name is the same"
            # print(old_name)
            # print(self.xc[0])

            referenceTree = self.subsetTree.invisibleRootItem().child(1)
            indexOfSubset = ''
            for i in range(referenceTree.childCount()):
                if referenceTree.child(i).data(0, 0) == new_name:
                    indexOfSubset = i
                    break

            for i in range(child_count):
                component_count = subset_branch.child(i)
                for x in range(component_count.childCount()):
                    data_groups = subset_branch.child(i).child(x)
                    for y in range(data_groups.childCount()):
                        if subset_branch.child(i).child(x).child(y).data(0, 0) == new_name:
                            subset_branch.child(i).child(x).child(y).setIcon(0, helpers.layer_icon(self.xc.subset_groups[indexOfSubset]))
                            break
        else:
            # update the dataset name in the statsviewer
            old_name = old_name[0]
            # print("old Name:")
            # print(old_name)
            for i in range(child_count):
                component_count = subset_branch.child(i)
                for x in range(component_count.childCount()):
                    data_groups = subset_branch.child(i).child(x)
                    for y in range(data_groups.childCount()):
                        # print(old_name)
                        # print(subset_branch.child(i).child(x).data(0, 0))
                        if subset_branch.child(i).child(x).child(y).data(0, 0) == old_name:
                            subset_branch.child(i).child(x).child(y).setData(0, 0, new_name)
                            break

    def subsetViewSubsetUpdateHelper(self, viewType, old_name, new_name, data_name):
        '''
        Updates the subset view if a subset atrribute is changed
        @param viewType: the QTreeWidget Tree that is being modified (subsetTree, componentTree)
        @param old_name: old name of the edited subset
        @param new_name: new name of the edited subset
        '''
        # for subset view
        subset_branch = viewType
        child_count = subset_branch.childCount()
        if len(old_name) == 0:
            # the name has not changed, so changed color
            old_name = "name is the same"
            # print(old_name)
            # print(self.xc[0])
            for i in range(child_count):
                subset_branch.child(i).setIcon(0, helpers.layer_icon(self.xc.subset_groups[i]))
                component_count = subset_branch.child(i).childCount()
                for x in range(component_count):
                    subset_branch.child(i).child(x).setIcon(0, helpers.layer_icon(self.xc.subset_groups[i]))
                    sub_component = subset_branch.child(i).child(x).childCount()
                    for y in range(sub_component):  # only subset edits reach here
                        subset_branch.child(i).child(x).child(y).setIcon(0, helpers.layer_icon(self.xc.subset_groups[i]))
        else:
            # update the dataset name in the statsviewer
            old_name = old_name[0]
            # print("old Name:")
            # print(old_name)
            for i in range(child_count):
                component_count = subset_branch.child(i).childCount()
                if subset_branch.child(i).data(0, 0) == old_name:
                    subset_branch.child(i).setData(0, 0, new_name)
                    for x in range(component_count):
                        # print(old_name)
                        # print(subset_branch.child(i).child(x).data(0, 0))
                        if str(old_name) in str(subset_branch.child(i).child(x).data(0, 0)):
                            # print("asdf")
                            new_label = str(subset_branch.child(i).child(x).data(0, 0)).replace(str(old_name), str(new_name))
                            subset_branch.child(i).child(x).setData(0, 0, new_label)

            # for x in self.activePlotLayerList:
                # print(x)
            # print("name - Subset: " + old_name+ data_name +")")

            # for x in self.activePlotLayerList:
                # if "(data: " + str(old_name) + ")" in x:
                #    x= x.replace(str(old_name), str(new_name))
            # update the info on the active plot layers
            self.activePlotLayerList.remove("Subset: " + old_name + data_name + ")")
            self.activePlotLayerList.append("Subset: " + new_name + data_name + ")")

    def dataUpdateMessage(self, message):
        '''
        Updates the attributes of the edited dataset (glue's left side panel info - names and color), size doesnt matter for this viewer
        @param message: Message given by the event, contains details about how it was triggered
        '''
        # print(message)

        # For subset view
        # first section of changing name
        index1 = str(message).index("Data Set: ") + len("Data Set: ")
        index2 = str(message).index("Number of dimensions: ") - 1
        new_name = str(message)[index1:index2]

        new_names = self.xc.labels
        old_name = np.setdiff1d(self.data_names, new_names)

        # update both views
        self.subsetViewDataUpdateHelper(self.subsetTree.invisibleRootItem().child(0), old_name, new_name)
        self.componentViewDataUpdateHelper(self.componentTree.invisibleRootItem(), old_name, new_name)
        # print(new_names)
        # print(self.data_names)
        # print(old_name)

        self.data_names = self.xc.labels

    def subsetViewDataUpdateHelper(self, viewType, old_name, new_name):
        '''
        Updates the subset view if a data atrribute is changed
        @param viewType: the QTreeWidget Tree that is being modified (subsetTree, componentTree)
        @param old_name: old name of the edited subset
        @param new_name: new name of the edited subset
        '''
        data_branch = viewType
        child_count = data_branch.childCount()
        # print("aaa")
        if len(old_name) == 0:
            # the name has not changed, so changed color
            # print("bbb")
            old_name = "name is the same"
            for i in range(child_count):
                data_branch.child(i).setIcon(0, helpers.layer_icon(self.xc[i]))
                component_count = data_branch.child(i).childCount()
                for x in range(component_count):
                    data_branch.child(i).child(x).setIcon(0, helpers.layer_icon(self.xc[i]))
        else:
            # update the dataset name in the statsviewer
            # print('aaa')
            old_name = old_name[0]
            # print(old_name)
            for i in range(child_count):
                if data_branch.child(i).data(0, 0) == old_name:
                    data_branch.child(i).setData(0, 0, new_name)

            # update the subsets that contain the old name, if any
            if len(self.xc.subset_groups) != 0:
                # print(old_name)
                # print(new_name)
                subset_branch = self.subsetTree.invisibleRootItem().child(1)
                child_count = subset_branch.childCount()
                for i in range(child_count):
                    component_count = subset_branch.child(i).childCount()
                    for x in range(component_count):
                        # print(old_name)
                        # print(subset_branch.child(i).child(x).data(0, 0))
                        if "(" + str(old_name) + ")" in str(subset_branch.child(i).child(x).data(0, 0)):
                            new_label = str(subset_branch.child(i).child(x).data(0, 0)).replace(str(old_name), str(new_name))
                            subset_branch.child(i).child(x).setData(0, 0, new_label)

            # update calculated values name
            for x in range(0, len(self.stCalculatedItems)):
                for y in range(0, len(self.stCalculatedItems[x])):
                    if isinstance(self.stCalculatedItems[x][y], str) and old_name in self.stCalculatedItems[x][y]:
                        self.stCalculatedItems[x][y] = self.stCalculatedItems[x][y].replace(str(old_name), str(new_name))

            for i in range(0, len(self.activePlotLayerList)):
                if old_name in self.activePlotLayerList[i]:
                    self.activePlotLayerList[i] = self.activePlotLayerList[i].replace(old_name, new_name)

            # for x in self.activePlotLayerList:
                # print(x)
            # self.activePlotLayerList.remove("Data (label: " + old_name + ")")
            # self.activePlotLayerList.append("Data (label: " + new_name + ")")

    def componentViewDataUpdateHelper(self, viewType, old_name, new_name):
        '''
        Updates the component view if a data atrribute is changed
        @param viewType: the QTreeWidget Tree that is being modified (subsetTree, componentTree)
        @param old_name: old name of the edited subset
        @param new_name: new name of the edited subset
        '''
        data_branch = viewType
        child_count = data_branch.childCount()
        # print("aaa")
        if len(old_name) == 0:
            # the name has not changed, so changed color
            # print("bbb")
            old_name = "name is the same"

            referenceTree = self.subsetTree.invisibleRootItem().child(0)
            indexOfSubset = ''
            for i in range(referenceTree.childCount()):
                if referenceTree.child(i).data(0, 0) == new_name:
                    indexOfSubset = i
                    break
            # print(indexOfSubset)
            # for i in range(child_count): # data
            #    component_count = data_branch.child(i)
            #    if data_branch.child(i).data(0, 0) == new_name:

            for i in range(child_count):
                component_count = data_branch.child(i).childCount()
                if data_branch.child(i).data(0, 0) == new_name:
                    data_branch.child(i).setIcon(0, helpers.layer_icon(self.xc[indexOfSubset]))
                for x in range(component_count):
                    # data_branch.child(i).child(x).setIcon(0, helpers.layer_icon(self.xc.subset_groups[indexOfSubset]))
                    data_groups = data_branch.child(i).child(x)
                    for y in range(data_groups.childCount()):
                        if "(" + str(new_name) + ")" in str(data_branch.child(i).child(x).child(y).data(0, 0)):
                            data_branch.child(i).child(x).child(y).setIcon(0, helpers.layer_icon(self.xc[indexOfSubset]))
                            break
        else:
            # update the dataset name in the statsviewer
            # print('aaa')
            old_name = old_name[0]
            # print(old_name)

            for i in range(child_count):  # data
                component_count = data_branch.child(i)
                if data_branch.child(i).data(0, 0) == old_name:
                    data_branch.child(i).setData(0, 0, new_name)
                for x in range(component_count.childCount()):
                    data_groups = data_branch.child(i).child(x)
                    for y in range(data_groups.childCount()):
                        if "(" + str(old_name) + ")" in str(data_branch.child(i).child(x).child(y).data(0, 0)):
                            new_label = str(data_branch.child(i).child(x).child(y).data(0, 0)).replace(str(old_name), str(new_name))
                            data_branch.child(i).child(x).child(y).setData(0, 0, new_label)
                            break

            # update calculated values dataset name
            for x in range(0, len(self.ctCalculatedItems)):
                for y in range(0, len(self.ctCalculatedItems[x])):
                    if isinstance(self.ctCalculatedItems[x][y], str) and old_name in self.ctCalculatedItems[x][y]:
                        self.ctCalculatedItems[x][y] = self.ctCalculatedItems[x][y].replace(str(old_name), str(new_name))

        '''    # update the subsets that contain the old name, if any
            if len(self.xc.subset_groups) != 0:
                print(old_name)
                print(new_name)
                subset_branch = self.subsetTree.invisibleRootItem().child(1)
                child_count = subset_branch.childCount()
                for i in range(child_count):
                    component_count = subset_branch.child(i).childCount()
                    for x in range(component_count):
                        # print(old_name)
                        # print(subset_branch.child(i).child(x).data(0, 0))
                        if "(" + str(old_name) + ")" in str(subset_branch.child(i).child(x).data(0, 0)):
                            new_label = str(subset_branch.child(i).child(x).data(0, 0)).replace(str(old_name), str(new_name))
                            subset_branch.child(i).child(x).setData(0, 0, new_label)'''

    def newDataAddedMessage(self, message):
        '''
        Adds a new dataset to the viewer when new dataset is dragged onto the viewer
        @param message: Message given by the event, contains details about how it was triggered
        '''
        # print(message)
        index1 = str(message).index("(label: ") + len("(label: ")
        index2 = str(message).index(")")
        name = str(message)[index1:index2]
        self.data_names = self.xc.labels
        '''For subset view'''

        parentItem = QTreeWidgetItem(self.dataItem)
        parentItem.setCheckState(0, 0)
        i = self.data_names.index(name)
        parentItem.setData(0, 0, '{}'.format(self.xc.labels[i]))
        parentItem.setIcon(0, helpers.layer_icon(self.xc[i]))

        # Make all the data components be children, nested under their parent
        for j in range(0, len(self.xc[i].components)):

            childItem = QTreeWidgetItem(parentItem)
            childItem.setCheckState(0, 0)
            childItem.setData(0, 0, '{}'.format(str(self.xc[i].components[j])))
            childItem.setIcon(0, helpers.layer_icon(self.xc[i]))

            # Add to the subset_dict
            # key = self.xc[i].label + self.xc[i].components[j].label + "All data" + self.xc[i].label
            self.num_rows = self.num_rows + 1

        '''For component view'''

        grandparent = QTreeWidgetItem(self.componentTree)
        grandparent.setData(0, 0, '{}'.format(self.xc.labels[i]))
        grandparent.setIcon(0, helpers.layer_icon(self.xc[i]))
        grandparent.setCheckState(0, 0)

        for k in range(0, len(self.xc[i].components)):
            parent = QTreeWidgetItem(grandparent)
            parent.setData(0, 0, '{}'.format(str(self.xc[i].components[k])))
            parent.setCheckState(0, 0)

            child = QTreeWidgetItem(parent)
            child.setData(0, 0, '{}'.format('All data (' + self.xc.labels[i] + ')'))
            child.setIcon(0, helpers.layer_icon(self.xc[i]))
            child.setCheckState(0, 0)

            self.num_rows = self.num_rows + 1
            # disableSubset = False
            # temp = False
            '''
            for j in range(0, len(self.xc.subset_groups)):
                childtwo = QTreeWidgetItem(parent)
                childtwo.setData(0, 0, '{}'.format(self.xc.subset_groups[j].label))
                # child.setEditable(False)
                childtwo.setIcon(0, helpers.layer_icon(self.xc.subset_groups[j]))
                childtwo.setCheckState(0, 0)
                if (not disableSubset) and (not temp):
                    try:
                         self.xc[i].compute_statistic('minimum', self.xc[i].subsets[j].components[k], subset_state=self.xc.subset_groups[j].subset_state)
                         temp = True
                    except:
                        disableSubset = True
                if disableSubset:
                    childtwo.setData(0, Qt.CheckStateRole, QVariant())
                    childtwo.setForeground(0, QtGui.QBrush(Qt.gray))
                self.num_rows = self.num_rows + 1
            '''
        self.dc_count += 1
        self.data_names = self.xc.labels
        self.subsetTree.expandToDepth(1)
        self.componentTree.expandToDepth(1)
        self.subsetViewDataLevel = 1
        self.componentViewLevel = 2
        self.minimizeGrayedData()
        if self.xc[i].size > 1000000:
            self.showLargeDatasetWarning()
        self.component_names = self.componentNames()
        dummy, self.plotlayer_names = self.plotLayerNames()

    def subsetCreatedMessage(self, message):
        '''
        Adds a new subset to the viewer when new subset is created
        @param message: Message given by the event, contains details about how it was triggered
        '''

        # print("detected new subset creation:", message)
        # print(message)
        # print("Before:")
        # print(self.state.layers)

        index1 = str(message).index("Subset: ") + len("Subset: ")
        index2 = str(message).index(" (data: ")
        # index3 = str(message).index(" (data: ") + len(" (data: ")
        # index4 = str(message).index(")") + len(")")

        current_subset = str(message)[index1:index2]
        # datasetname = str(message)[index3:index4-1]
        # current_subdataset = current_subset + " (" + datasetname + ")"

        # print(current_subset, datasetname, current_subdataset)

        self.subset_names = self.subsetNames()

        s = self.subset_names.tolist()
        j = s.index(current_subset)

        if current_subset not in self.subset_set:
            # print("subset set:", self.subset_set)
            # print("made subset:", current_subset)
            grandparent = QTreeWidgetItem(self.subsetItem)
            grandparent.setData(0, 0, '{}'.format(self.xc.subset_groups[j].label))
            grandparent.setIcon(0, helpers.layer_icon(self.xc.subset_groups[j]))
            grandparent.setCheckState(0, 0)
            grandparent.setExpanded(True)
        # for subset view
        # if (not current_subdataset in self.subset_set) and current_subset in self.subset_set:
            # print("Current subdataset:", current_subdataset)
            # print("data ", datasetname)
            # grandparent = self.findSubsetItem(current_subset)

            for i in range(0, len(self.xc)):

                # if self.xc[i].label == datasetname:

                parent = QTreeWidgetItem(grandparent)
                parent.setData(0, 0, '{}'.format(self.xc.subset_groups[j].label) + ' (' + '{}'.format(self.xc[i].label) + ')')
                parent.setIcon(0, helpers.layer_icon(self.xc.subset_groups[j]))
                parent.setCheckState(0, 0)
                parent.setExpanded(True)

                disableSubset1 = False
                temp1 = False

                for k in range(0, len(self.xc[i].components)):
                    # print("added:", i, j, k)
                    child = QTreeWidgetItem(parent)
                    child.setData(0, 0, '{}'.format(str(self.xc[i].components[k])))
                    child.setIcon(0, helpers.layer_icon(self.xc.subset_groups[j]))
                    child.setCheckState(0, 0)
                    child.setExpanded(True)

                    if (not disableSubset1) and (not temp1):
                        try:
                            # x = self.xc[i].compute_statistic('minimum', self.xc[i].subsets[j].components[k], subset_state=self.xc.subset_groups[j].subset_state)
                            temp1 = True

                        except:
                            parent.setData(0, Qt.CheckStateRole, QVariant())
                            parent.setForeground(0, QtGui.QBrush(Qt.gray))
                            parent.setExpanded(False)
                            disableSubset1 = True
                    if disableSubset1:
                        # print("disabled subsetview")
                        child.setData(0, Qt.CheckStateRole, QVariant())
                        child.setForeground(0, QtGui.QBrush(Qt.gray))

            # print("component view making")
            '''Component View'''

            for i in range(0, self.componentTree.invisibleRootItem().childCount()):
                # if self.xc[i].label == datasetname:
                parent = self.componentTree.invisibleRootItem().child(i)
                disableSubset2 = False
                temp2 = False

                for k in range(0, parent.childCount()):
                    # print("component made")
                    component = parent.child(k)

                    childtwo = QTreeWidgetItem(component)
                    childtwo.setData(0, 0, '{}'.format(current_subset))
                    childtwo.setIcon(0, helpers.layer_icon(self.xc.subset_groups[j]))
                    childtwo.setCheckState(0, 0)

                    if (not disableSubset2) and (not temp2):
                        try:
                            self.xc[i].compute_statistic('minimum', self.xc[i].subsets[j].components[k], subset_state=self.xc.subset_groups[j].subset_state)
                            temp2 = True
                        except:
                            disableSubset2 = True
                    if disableSubset2:
                        # print("disabled compview")
                        childtwo.setData(0, Qt.CheckStateRole, QVariant())
                        childtwo.setForeground(0, QtGui.QBrush(Qt.gray))

            self.subset_set.add(current_subset)
            # self.subset_set.add(current_subdataset)
            self.subset_names = self.subsetNames()
            # self.subset_dict.update({current_subset : count})
            self.subset_count += 1
            # print("done making subset")
            # print(self.state.layers)
        self.minimizeGrayedData()
        # self.disableNASubsets()

    def disableNASubsets(self):
        # print("disable NA Subsets")
        subset_branch = self.subsetTree.invisibleRootItem().child(1)
        for subset_i in range(0, subset_branch.childCount()):
            for data_i in range(0, subset_branch.child(subset_i).childCount()):
                disableSubset = False
                temp = False
                for comp_i in range(0, subset_branch.child(subset_i).child(data_i).childCount()):
                    if (not disableSubset) and (not temp):
                        try:

                            mean_val = self.xc[data_i].compute_statistic('mean', self.xc[data_i].subsets[subset_i].components[comp_i], subset_state=self.xc[data_i].subsets[subset_i].subset_state)
                            print(mean_val)
                            if str(mean_val) == "nan":
                                raise Exception()
                            temp = True
                        except:
                            parent = subset_branch.child(subset_i).child(data_i)
                            parent.setData(0, Qt.CheckStateRole, QVariant())
                            parent.setForeground(0, QtGui.QBrush(Qt.gray))
                            parent.setExpanded(False)
                            disableSubset = True
                    if disableSubset:
                        child = subset_branch.child(subset_i).child(data_i).child(comp_i)
                        child.setData(0, Qt.CheckStateRole, QVariant())
                        child.setForeground(0, QtGui.QBrush(Qt.gray))

        cTree = self.subsetTree.invisibleRootItem().child(0)
        for data_i in range(0, cTree.childCount()):
            for comp_i in range(0, cTree.child(data_i).childCount()):
                disableSubset =False
                temp = False
                for subset_i in range(0, cTree.child(data_i).child(comp_i).childCount()):
                    if (not disableSubset) and (not temp):
                        try :
                            # self.newSubsetStats(subset_i, data_i, comp_i)
                            mean_val = self.xc[data_i].compute_statistic('mean', self.xc[data_i].subsets[subset_i].components[comp_i], subset_state=self.xc[data_i].subsets[subset_i].subset_state)
                            # print(mean_val)
                            if mean_val == 'nan':
                                raise Exception("nan")
                            temp = True
                        except:
                            parent = cTree.child(data_i).child(comp_i)
                            parent.setData(0, Qt.CheckStateRole, QVariant())
                            parent.setForeground(0, QtGui.QBrush(Qt.gray))
                            parent.setExpanded(False)
                            disableSubset = True
                    if disableSubset:
                        child = subset_branch.child(data_i).child(comp_i).child(subset_i)
                        child.setData(0, Qt.CheckStateRole, QVariant())
                        child.setForeground(0, QtGui.QBrush(Qt.gray))

    def findSubsetItem(self, subsetName):

        '''
        Finds the item of the general subset. Ex. "Subset 1" is general subset of "Subset 1 (w5)"
        '''
        subset_branch = self.subsetTree.invisibleRootItem().child(1)
        for subset_i in range(0, subset_branch.childCount()):
            if subsetName == subset_branch.child(subset_i).data(0, 0):
                return subset_branch.child(subset_i)

    def dataDeleteMessage(self, message):
        '''
        Removes deleted dataset from the viewer
        @param message: Message given by the event, contains details about how it was triggered
        '''
        print("detected data removal")
        # print(message)
        self.deleteHelper('dataset')
        self.dc_count -= 1

    def subsetDeleteMessage(self, message):
        '''
        Removes deleted subset from the viewer
        @param message: Message given by the event, contains details about how it was triggered
        '''
        # print("detected subset deletion")
        self.deleteHelper('subset')
        self.subset_count -= 1

    def deleteHelper(self, deletedType):
        '''
        Helper method for dataDeleteMessage(self, message) and subsetDeleteMessage(self, message)
        @param message: Message given by the event, contains details about how it was triggered
        '''
        # print(deletedType)
        current_list = np.array([])
        past_list = np.array([])
        temp = -1
        if deletedType == 'dataset':
            temp = 0
            # creates a list of the current values in the data_collection
            for ds in self.xc:
                current_list = np.append(current_list, ds.label)
        if deletedType == 'subset':
            temp = 1
            current_list = self.subsetNames()

        if temp == -1:
            raise Exception("invalid error code, method deleteHelper not called properly")

        '''Subset view'''
        # data branch of tree
        data_branch = self.subsetTree.invisibleRootItem().child(temp)
        # counts the number of each dataset
        child_count = data_branch.childCount()
        # creates a list of the values in the outdated tree
        for i in range(child_count):
            past_list = np.append(past_list, data_branch.child(i).data(0, 0))
        # print(current_list)
        # print(past_list)
        # print(np.setdiff1d(past_list, current_list)[0])
        removalList = np.setdiff1d(past_list, current_list)
        if len(removalList) != 0:
            toBeRemoved = np.setdiff1d(past_list, current_list)[0]
            toBeRemovedQItem = ''
            for i in range(child_count):
                if data_branch.child(i).data(0, 0) == toBeRemoved:
                    toBeRemovedQItem = data_branch.child(i)
            data_branch.removeChild(toBeRemovedQItem)

        '''Component View'''
        # data branch of tree
        data_branch = self.componentTree.invisibleRootItem()
        # counts the number of each dataset
        child_count = data_branch.childCount()
        # creates a list of the values in the outdated tree
        for i in range(child_count):
            past_list = np.append(past_list, data_branch.child(i).data(0, 0))
        # print(current_list)
        # print(past_list)
        # print(np.setdiff1d(past_list, current_list)[0])
        removalList = np.setdiff1d(past_list, current_list)
        if len(removalList) != 0:
            toBeRemoved = np.setdiff1d(past_list, current_list)[0]
            toBeRemovedQItem = ''
            for i in range(child_count):
                if data_branch.child(i).data(0, 0) == toBeRemoved:
                    toBeRemovedQItem = data_branch.child(i)
            data_branch.removeChild(toBeRemovedQItem)

    def initialize_toolbar(self):
        '''
        Initializes the the toolbar: add any further customizations here
        '''
        super(StatsDataViewer, self).initialize_toolbar()
        BasicToolbar.setContextMenuPolicy(self, Qt.PreventContextMenu)

    def myPressedEvent(self, currentQModelIndex):
        pass

    def pressedEventCalculate(self):

        '''
        Calculates stats for the rows that are checked
        '''
        '''
        Every time the selection in the treeview changes:
        if it is newly selected, add it to the table
        if it is newly deselected, remove it from the table
        '''

        self.selected_indices = []
        showNANPopup = False
        # determines whether or not to show the NAN error: the subset is too small/no intersection and has no values to calculate

        # create list of rows to calculate
        # calculate for subset view
        if self.tabs.currentIndex() == 0 :

            # get the checked items in the data branch
            data_branch = self.subsetTree.invisibleRootItem().child(0)
            for data_i in range(0, data_branch.childCount()):
                for comp_i in range(0, data_branch.child(data_i).childCount()):
                    # if checked, add to selected list
                    if data_branch.child(data_i).child(comp_i).checkState(0):
                        self.selected_indices.append(
                            # adding item, subset label, data label, and component label
                            [self.subsetTree.indexFromItem(data_branch.child(data_i).child(comp_i)),
                             "All data",
                             data_branch.child(data_i).data(0, 0),
                             data_branch.child(data_i).child(comp_i).data(0, 0)])

            # get the checked items in the subset branch
            subset_branch = self.subsetTree.invisibleRootItem().child(1)
            for subset_i in range(0, subset_branch.childCount()):
                for data_i in range(0, subset_branch.child(subset_i).childCount()):
                    for comp_i in range(0, subset_branch.child(subset_i).child(data_i).childCount()):

                        # try statement here for subsets that are not added(happens when subsets are calculated first and a new dataset is added)
                        try:
                            if subset_branch.child(subset_i).child(data_i).child(comp_i).checkState(0):
                                self.selected_indices.append(
                                    # adding item, subset label, data label, and component label
                                    [self.subsetTree.indexFromItem(subset_branch.child(subset_i).child(data_i).child(comp_i)),
                                     subset_branch.child(subset_i).data(0, 0),
                                     subset_branch.child(subset_i).child(data_i).data(0, 0),
                                     subset_branch.child(subset_i).child(data_i).child(comp_i).data(0, 0)])
                        except:
                            pass
            for x in self.selected_indices:
                self.stCalculatedItems.append(x)
            newly_selected = self.selected_indices  # self.setdiff2d(self.selected_indices, self.past_selected)

            for index in range(0, len(newly_selected)):

                # Check which view mode the tree is in to get the correct indices
                # data_i = newly_selected[index].parent().row()
                # comp_i = newly_selected[index].row()

                # Finds index of the needed data that is in the data collection. The index of the tree and the data collection is not necessarily the same.
                subset_i, data_i, comp_i = self.findIndexInDc(newly_selected[index][1], newly_selected[index][2], newly_selected[index][3])

                is_subset = (subset_i != -1)

                # Check if its a subset and if so run subset stats
                if is_subset:
                    new_data = self.runSubsetStats(subset_i, data_i, comp_i)
                else:
                    # Run standard data stats
                    new_data = self.runDataStats(data_i, comp_i)

                # populate the subset view
                for col_index in range(3, len(new_data)):
                    if new_data[col_index] == "NAN":
                        showNANPopup = True
                        self.subsetTree.itemFromIndex(newly_selected[index][0]).setData(col_index-2, 0, "Error")
                    else:
                        self.subsetTree.itemFromIndex(newly_selected[index][0]).setData(col_index-2, 0, new_data[col_index])

        # if calculating component view
        elif self.tabs.currentIndex() == 1:
            cTree = self.componentTree.invisibleRootItem()
            for data_i in range(0, cTree.childCount()):
                for comp_i in range(0, cTree.child(data_i).childCount()):
                    for subset_i in range(0, cTree.child(data_i).child(comp_i).childCount()):

                        if cTree.child(data_i).child(comp_i).child(subset_i).checkState(0):
                            # adding item, subset label, data label, and component label
                            self.selected_indices.append(
                                [self.componentTree.indexFromItem(cTree.child(data_i).child(comp_i).child(subset_i)),
                                 cTree.child(data_i).child(comp_i).child(subset_i).data(0, 0),
                                 cTree.child(data_i).data(0, 0),
                                 cTree.child(data_i).child(comp_i).data(0, 0)])

            newly_selected = self.selected_indices
            for x in self.selected_indices:
                self.ctCalculatedItems.append(x)

            for index in range(0, len(newly_selected)):

                # Check which view mode the tree is in to get the correct indices
                subset_i, data_i, comp_i = self.findIndexInDc(newly_selected[index][1], newly_selected[index][2], newly_selected[index][3])

                is_subset = (subset_i != -1)

                # Check if its a subset and if so run subset stats
                if is_subset:
                    new_data = self.runSubsetStats(subset_i, data_i, comp_i)

                else:
                    # Run standard data stats
                    new_data = self.runDataStats(data_i, comp_i)
                # self.nestedtree.itemFromIndex(newly_selected[0]).setData(0, 0, new_data[0][0])

                # populate the Component Tree
                for col_index in range(3, len(new_data)):
                    if new_data[col_index] == "NAN":
                        showNANPopup = True
                        self.componentTree.itemFromIndex(newly_selected[index][0]).setData(col_index-2, 0, "Error")
                    else:
                        self.componentTree.itemFromIndex(newly_selected[index][0]).setData(col_index-2, 0, new_data[col_index])
                        # Removes numerical values for categorical variables and replace with NAN

        if showNANPopup:
            self.showNANPopup()

    def findIndexInDc(self, subsetName, dataName, compName):
        '''
        Finds the index of the subset, data, and component in the data collection that corresponds to the item in the viewer.
        @param subsetName: name of subset "All data" if n/a because it is calculating all data
        @param dataName: name of the dataset
        @param compName: name of the component
        '''

        subset_i = ''
        data_i = ''
        comp_i = ''
        # print(subsetName)
        # print(dataName)
        # print(compName)

        # if dataset
        if subsetName == "All data":
            # print("dataset loop")
            subset_i = -1
            for x in range(0, len(self.xc)):
                if self.xc[x].label == dataName:
                    data_i = x
                for y in range(0, len(self.xc[x].components)):
                    if self.xc[x].components[y].label == compName:
                        comp_i = y

        # if subset
        else:
            # print(dataName)
            try:
                i_1 = str(dataName).index("(") + len("(")
                i_2 = str(dataName).index(")")
                dataName = str(dataName)[i_1:i_2]
            except:
                # in component view, the subset may be All Data(x)
                if "All data (" in subsetName:
                    subset_i = -1

            # find data index
            for x in range(0, len(self.xc)):
                # print(self.xc[x].label)
                # print(dataName)
                if self.xc[x].label == dataName:
                    data_i = x
                for y in range(0, len(self.xc[x].components)):
                    if self.xc[x].components[y].label == compName:
                        comp_i = y
            # find subset index
            for z in range(0, len(self.xc[data_i].subsets)):
                if subsetName == self.xc[data_i].subsets[z].label:
                    subset_i = z

        # print(subset_i)
        # print(data_i)
        # print(comp_i)
        if subset_i == '' or data_i == '' or comp_i == '':
            raise Exception("Could not find data")

        return subset_i, data_i, comp_i

    def getCurrentCalculated(self):
        '''
        returns list of current calculated values in the current opened viewer
        '''
        currentCalculated = []
        # if the open tab is subset view
        if self.tabs.currentIndex() == 0:
            # data
            exportHeading = ['Subset', 'Dataset', 'Component'] + self.headings[1:]
            currentCalculated.append(exportHeading)
            st = self.subsetTree.invisibleRootItem().child(0)
            for x in range(0, st.childCount()):
                for y in range(0, st.child(x).childCount()):
                    item = self.subsetTree.indexFromItem(st.child(x).child(y))
                    calculatedValueExists = self.checkIfCalculated(st.child(x).child(y))
                    # if self.subsetTree.itemFromIndex(item).data(3, 0) is not None:
                    if calculatedValueExists:
                        temp = []
                        temp.append('All data')  # no subset
                        temp.append(st.child(x).data(0, 0))  # dataset
                        for t in range(0, len(self.headings)):
                            temp.append(self.subsetTree.itemFromIndex(item).data(t, 0))
                        currentCalculated.append(temp)
            # subset
            st = self.subsetTree.invisibleRootItem().child(1)
            for x in range(0, st.childCount()):
                for y in range(0, st.child(x).childCount()):
                    for z in range(0, st.child(x).child(y).childCount()):
                        item = self.subsetTree.indexFromItem(st.child(x).child(y).child(z))
                        calculatedValueExists = self.checkIfCalculated(st.child(x).child(y).child(z))
                        # if self.subsetTree.itemFromIndex(item).data(3, 0) is not None:
                        if calculatedValueExists:
                            temp = []
                            temp.append(st.child(x).child(y).data(0, 0))  # subset(data) name
                            tempStr = str(st.child(x).child(y).data(0, 0))
                            index1 = tempStr.index("(")+1
                            index2 = tempStr.index(")")
                            dataset_name = tempStr[index1:index2]
                            temp.append(dataset_name)  # dataset name
                            for t in range(0, len(self.headings)):
                                temp.append(self.subsetTree.itemFromIndex(item).data(t, 0))
                            currentCalculated.append(temp)
        # if component view is open
        elif self.tabs.currentIndex() == 1:
            exportHeading = ['Dataset', 'Component', 'Subset'] + self.headings[1:]
            currentCalculated.append(exportHeading)
            ct = self.componentTree.invisibleRootItem()
            for x in range(0, ct.childCount()):
                for y in range(0, ct.child(x).childCount()):
                    for z in range(0, ct.child(x).child(y).childCount()):
                        item = self.componentTree.indexFromItem(ct.child(x).child(y).child(z))
                        calculatedValueExists = self.checkIfCalculated(ct.child(x).child(y).child(z))
                        # if self.componentTree.itemFromIndex(item).data(3, 0) is not None:
                        if calculatedValueExists:
                            temp = []
                            temp.append(ct.child(x).data(0, 0))  # dataset
                            temp.append(ct.child(x).child(y).data(0, 0))  # component
                            for t in range(0, len(self.headings)):
                                if t == 0 and (not self.componentTree.itemFromIndex(item).data(0, 0) == "All data (" + ct.child(x).data(0, 0) + ")"):
                                    temp.append(self.componentTree.itemFromIndex(item).data(t, 0) + " (" + ct.child(x).data(0, 0) + ")")
                                else:
                                    temp.append(self.componentTree.itemFromIndex(item).data(t, 0))
                            currentCalculated.append(temp)
        # print(currentCalculated)
        return currentCalculated

    def checkIfCalculated(self, dataItem):
        '''
        Checks if there is a calculated item in the given dataItem
        '''
        for x in range(3, len(self.headings)):
            if dataItem.data(x, 0) is not None:
                print("ITEM", dataItem.data(x, 0))
                return True
        return False

    def pressedEventExport(self):
        '''
        Exports the current calculated values of the tab that is open
        '''
        # get all values calculated in the open viewer
        df = self.getCurrentCalculated()
        # print(df)
        file_name, fltr = compat.getsavefilename(caption="Choose an output filename")
        try:
            df = pd.DataFrame(df)
            # print(df)
            df.to_csv(str(file_name), header=None, index=None)
        except:
            raise Exception("Export failed")

    def pressedEventConvertNotation(self, bool):
        '''
        Converts from scientific to decimal and vice versa
        '''
        self.isSci = bool
        # left or right justify the text data so the decimal point lines up for easy reading
        if bool:
            self.leftOrRightJustifyViewers(Qt.AlignLeft)
            # print("left")
        else:
            # print("right")
            self.leftOrRightJustifyViewers(Qt.AlignRight)

        # recalculate with new notation,
        # data is cached already so it should be quick
        self.pressedEventCalculate()

    def leftOrRightJustifyViewers(self, justification):

        # subset view
        #    - dataset
        dataset_count = self.subsetTree.invisibleRootItem().child(0).childCount()
        data = self.subsetTree.invisibleRootItem().child(0)
        for x in range(dataset_count):
            attribute_count = data.child(x).childCount()
            for y in range(attribute_count):
                for col in range(1, len(self.headings)):
                    self.subsetTree.invisibleRootItem().child(0).child(x).child(y).setTextAlignment(col, justification)
        #    - subsets
        # subset_count = self.subsetTree.invisibleRootItem().child(1).childCount()
        for x in range(dataset_count):
            attribute_count = data.child(x).childCount()
            for y in range(attribute_count):
                sub_attribute_count = data.child(x).child(y).childCount()
                # Only the subset section of the tree should be able to reach here
                for z in range(sub_attribute_count):
                    for col in range(1, len(self.headings)):
                        self.subsetTree.invisibleRootItem().child(0).child(x).child(y).child(z).setTextAlignment(col, justification)
        # component view
        dataset_count = self.componentTree.invisibleRootItem().childCount()
        data = self.componentTree.invisibleRootItem()
        for x in range(dataset_count):
            attribute_count = data.child(x).childCount()
            for y in range(attribute_count):
                sub_attribute_count = data.child(x).child(y).childCount()
                for z in range(sub_attribute_count):
                    for col in range(1, len(self.headings)):
                        self.componentTree.invisibleRootItem().child(x).child(y).child(z).setTextAlignment(col, justification)

    def runDataStats(self, data_i, comp_i):
        '''
        Runs statistics for the component comp_i of data set data_i
        @param data_i: data index from the tree
        @param comp_i: component index from the tree
        '''

        subset_label = "All data"
        data_label = self.xc[data_i].label
        comp_label = self.xc[data_i].components[comp_i].label  # add to the name array to build the table

        # print("hihihi")
        # print(data_label)
        # print(comp_label)
        # Build the cache key
        cache_key = subset_label + data_label + comp_label

        if cache_key in self.cache_stash:
            column_data = self.cache_stash[cache_key]
        else:
            column_data = self.newDataStats(data_i, comp_i)
        # print(cache_key)
        # See if the values have already been cached
        # if True:
        #    try:
        #        column_data = self.cache_stash[cache_key]
        #    except:
        #        column_data = self.newDataStats(data_i, comp_i)
        # else:
        #    column_data = self.newDataStats(data_i, comp_i)
        # print(column_data)
        # Save the accurate data in self.data_accurate
        # column_df = pd.DataFrame(column_data, columns=self.headings)
        # self.data_accurate = self.data_accurate.append(column_df, ignore_index=True)

        if self.isSci:
            # Format in scientific notation
            string = "%." + str(self.num_sigs) + 'E'
        else:
            # Format in standard notation
            string = "%." + str(self.num_sigs) + 'F'

        # print("xxyyzz")
        # print(string)

        # if the values of the stats are not NAN
        if not column_data[3] == "NaN":
            mean_val = string % column_data[3]
            # print(mean_val)
            # print("mean_val ^^")
            median_val = string % column_data[4]
            min_val = string % column_data[5]
            max_val = string % column_data[6]
            sum_val = string % column_data[7]

            # Create the column data array and append it to the data frame
            column_data = (subset_label, data_label, comp_label, mean_val, median_val, min_val, max_val, sum_val)
            # column_df = pd.DataFrame(column_data, columns=self.headings)
            # # self.data_frame = self.data_frame.append(column_df, ignore_index=True)
            return column_data
        else:
            return (subset_label, data_label, comp_label, "NaN", "NaN", "NaN", "NaN", "NaN")

    def newDataStats(self, data_i, comp_i):
        '''
        Runs statistics for the component comp_i of data set data_i
        @param data_i: data index from the tree
        @param comp_i: component index from the tree
        '''
        # print("newDataStats triggered")
        # Generates new data for a dataset that has to be calculated

        subset_label = "All data"
        data_label = self.xc[data_i].label
        comp_label = self.xc[data_i].components[comp_i].label  # add to the name array to build the table

        # Build the cache key
        cache_key = subset_label + data_label + comp_label

        # NOTE: This section is only necessary because glue's compute_statistics method will return numerical values for categorical variables instead of NaN.
        # This if statement can be removed when this bug is fixed.
        if self.xc[data_i].get_component(self.xc[data_i].components[comp_i]).categorical:
            # print("Detected categorical")
            return (subset_label, data_label, comp_label, "NaN", "NaN", "NaN", "NaN", "NaN")

        # Find the stat values
        # Save the data in the cache
        mean_val = self.xc[data_i].compute_statistic('mean', self.xc[data_i].components[comp_i])
        median_val = self.xc[data_i].compute_statistic('median', self.xc[data_i].components[comp_i])
        min_val = self.xc[data_i].compute_statistic('minimum', self.xc[data_i].components[comp_i])
        max_val = self.xc[data_i].compute_statistic('maximum', self.xc[data_i].components[comp_i])
        sum_val = self.xc[data_i].compute_statistic('sum', self.xc[data_i].components[comp_i])

        column_data = (subset_label, data_label, comp_label, mean_val, median_val, min_val, max_val, sum_val)

        self.cache_stash[cache_key] = column_data

        return column_data

    def runSubsetStats(self, subset_i, data_i, comp_i):
        '''
        Runs statistics for the subset subset_i with respect to the component comp_i of data set data_i
        @param subset_i: subset index from tree
        @param data_i: data index from the tree
        @param comp_i: component index from the tree
        '''

        subset_label = self.xc[data_i].subsets[subset_i].label
        data_label = self.xc[data_i].label
        comp_label = self.xc[data_i].components[comp_i].label  # add to the name array to build the table

        # Build the cache key
        cache_key = subset_label + data_label + comp_label

        # See if the statistics are already in the cache if nothing needs to be updated

        if cache_key in self.cache_stash:
            column_data = self.cache_stash[cache_key]
        else:
            column_data = self.newSubsetStats(subset_i, data_i, comp_i)

        if self.isSci:
            # Format in scientific notation
            string = "%." + str(self.num_sigs) + 'E'
        else:
            # Format in standard notation
            string = "%." + str(self.num_sigs) + 'F'

        # if the values of the stats are not NAN
        if not column_data[3] == "NaN":
            mean_val = string % column_data[3]
            # print(mean_val)
            # print("mean_val ^")
            median_val = string % column_data[4]
            min_val = string % column_data[5]
            max_val = string % column_data[6]
            sum_val = string % column_data[7]

            # Create the column data array and append it to the data frame
            column_data = (subset_label, data_label, comp_label, mean_val, median_val, min_val, max_val, sum_val)
            return column_data
        else:
            return (subset_label, data_label, comp_label, "NaN", "NaN", "NaN", "NaN", "NaN")

    def newSubsetStats(self, subset_i, data_i, comp_i):

        '''
        Runs statistics for the subset subset_i with respect to the component comp_i of data set data_i
        @param subset_i: subset index from tree
        @param data_i: data index from the tree
        @param comp_i: component index from the tree
        '''
        # Generates new data for a subset that needs to be calculated
        subset_label = self.xc[data_i].subsets[subset_i].label
        data_label = self.xc[data_i].label
        comp_label = self.xc[data_i].components[comp_i].label  # add to the name array to build the table

        # Build the cache key
        cache_key = subset_label + data_label + comp_label

        # NOTE: This section is only necessary because glue's compute_statistics method will return numerical values for categorical variables instead of NaN.
        # This if statement can be removed when this bug is fixed.
        if self.xc[data_i].get_component(self.xc[data_i].components[comp_i]).categorical:
            return (subset_label, data_label, comp_label, "NaN", "NaN", "NaN", "NaN", "NaN")

        mean_val = self.xc[data_i].compute_statistic(
            'mean',
            self.xc[data_i].subsets[subset_i].components[comp_i],
            subset_state=self.xc[data_i].subsets[subset_i].subset_state)
        median_val = self.xc[data_i].compute_statistic(
            'median',
            self.xc[data_i].subsets[subset_i].components[comp_i],
            subset_state=self.xc.subset_groups[subset_i].subset_state)
        min_val = self.xc[data_i].compute_statistic(
            'minimum',
            self.xc[data_i].subsets[subset_i].components[comp_i],
            subset_state=self.xc.subset_groups[subset_i].subset_state)
        max_val = self.xc[data_i].compute_statistic(
            'maximum',
            self.xc[data_i].subsets[subset_i].components[comp_i],
            subset_state=self.xc.subset_groups[subset_i].subset_state)
        sum_val = self.xc[data_i].compute_statistic(
            'sum',
            self.xc[data_i].subsets[subset_i].components[comp_i],
            subset_state=self.xc.subset_groups[subset_i].subset_state)

        column_data = (subset_label, data_label, comp_label, mean_val, median_val, min_val, max_val, sum_val)

        self.cache_stash[cache_key] = column_data

        return column_data

    def mousePressEvent(self, event):
        pass

    def sortBySubsets(self):
        '''
        Sorts the treeview by subsets- Dataset then subset then component.
        What we originally had as the default
        '''
        # Set to not component mode
        self.component_mode = False

        # Clear the num_rows
        self.num_rows = 0

        # Clear the data_accurate
        self.data_accurate = pd.DataFrame(columns=self.headings)

        # Clear the selection
        self.subsetTree.clearSelection()

        # Clear the tree
        self.subsetTree.clear()

        # Allow the user to select multiple rows at a time
        self.selection_model = QAbstractItemView.MultiSelection
        self.subsetTree.setSelectionMode(self.selection_model)

        self.subsetTree.setUniformRowHeights(True)

        self.generateSubsetView()
        # self.nestedtree.header.moveSection(1, 0)

        # Make the table update whenever the selection in the tree is changed
        selection_model = QItemSelectionModel(self.model_subsets)
        # self.nestedtree.setSelectionModel(selection_model)
        selection_model.selectionChanged.connect(self.myPressedEvent)
        # self.subsetTree.itemClicked.connect(self.check_status)

    def generateSubsetView(self):
        '''
        Creates the subset view for the viewer
        '''
        # self.component_mode = False
        self.model_subsets = QStandardItemModel()
        self.model_subsets.setHorizontalHeaderLabels([''])

        self.dataItem = QTreeWidgetItem(self.subsetTree)
        self.dataItem.setData(0, 0, '{}'.format('Data'))
        # dataItem.setExpanded(True)
        self.dataItem.setCheckState(0, 0)

        '''
        for i in range(0, len(self.xc)):
            parentItem = QTreeWidgetItem(self.dataItem)
            parentItem.setCheckState(0, 0)
            parentItem.setData(0, 0, '{}'.format(self.xc.labels[i]))
            parentItem.setIcon(0, helpers.layer_icon(self.xc[i]))
            # Make all the data components be children, nested under their parent
            for j in range(0, len(self.xc[i].components)):
                childItem = QTreeWidgetItem(parentItem)
                childItem.setCheckState(0, 0)
                childItem.setData(0, 0, '{}'.format(str(self.xc[i].components[j])))
                childItem.setIcon(0, helpers.layer_icon(self.xc[i]))
                # Add to the subset_dict
                key = self.xc[i].label + self.xc[i].components[j].label + "All data" + self.xc[i].label
                self.num_rows = self.num_rows + 1
        '''

        self.subsetItem = QTreeWidgetItem(self.subsetTree)
        self.subsetItem.setData(0, 0, '{}'.format('Subsets'))
        self.subsetItem.setCheckState(0, 0)
        '''
        for j in range(0, len(self.xc.subset_groups)):
            grandparent = QTreeWidgetItem(self.subsetItem)
            grandparent.setData(0, 0, '{}'.format(self.xc.subset_groups[j].label))
            grandparent.setIcon(0, helpers.layer_icon(self.xc.subset_groups[j]))
            grandparent.setCheckState(0, 0)
            for i in range(0, len(self.xc)):
                parent = QTreeWidgetItem(grandparent)
                parent.setData(0, 0, '{}'.format(self.xc.subset_groups[j].label) + ' (' + '{}'.format(self.xc[i].label) + ')')
                parent.setIcon(0, helpers.layer_icon(self.xc.subset_groups[j]))
                parent.setCheckState(0, 0)
                disableSubset = False
                temp = False
                for k in range(0, len(self.xc[i].components)):
                    child = QTreeWidgetItem(parent)
                    child.setData(0, 0, '{}'.format(str(self.xc[i].components[k])))
                    # child.setEditable(False)
                    child.setIcon(0, helpers.layer_icon(self.xc.subset_groups[j]))
                    child.setCheckState(0, 0)
                    if (not disableSubset) and (not temp):
                        try:
                             self.xc[i].compute_statistic('minimum',
                                                          self.xc[i].subsets[j].components[k],
                                                          subset_state=self.xc.subset_groups[j].subset_state)
                             # self.xc[i].compute_statistic('minimum',
                                                            self.dc[i].subsets[j].components[k],
                                                            subset_state=self.dc[i].subsets[j].subset_state)
                             temp = True
                        except:
                            # child.setData(0, Qt.CheckStateRole, QVariant())
                            parent.setData(0, Qt.CheckStateRole, QVariant())
                            parent.setForeground(0, QtGui.QBrush(Qt.gray))
                            parent.setExpanded(False)
                            disableSubset = True
                    if disableSubset:
                        child.setData(0, Qt.CheckStateRole, QVariant())
                        child.setForeground(0, QtGui.QBrush(Qt.gray))
                    self.num_rows = self.num_rows + 1
        '''

        self.subsetTree.setUniformRowHeights(True)

    def sortByComponents(self):
        '''
        Sorts the treeview by components- Dataset then component then subsets
        '''
        # Set component_mode to true
        self.component_mode = True

        # Clear the num_rows
        self.num_rows = 0

        # Clear the data_accurate
        self.data_accurate = pd.DataFrame(columns=self.headings)

        # Clear the selection
        self.componentTree.clearSelection()
        self.componentTree.clear()

        self.selection_model = QAbstractItemView.MultiSelection
        self.componentTree.setSelectionMode(self.selection_model)

        self.generateComponentView()

        self.componentTree.setUniformRowHeights(True)

    def generateComponentView(self):

        '''
        Creates the component view for the viewer
        '''
        self.component_mode = True
        '''
        for i in range(0, len(self.xc)):
            grandparent = QTreeWidgetItem(self.componentTree)
            grandparent.setData(0, 0, '{}'.format(self.xc.labels[i]))
            grandparent.setIcon(0, helpers.layer_icon(self.xc[i]))
            grandparent.setCheckState(0, 0)
            for k in range(0, len(self.xc[i].components)):
                parent = QTreeWidgetItem(grandparent)
                parent.setData(0, 0, '{}'.format(str(self.xc[i].components[k])))
                parent.setCheckState(0, 0)
                child = QTreeWidgetItem(parent)
                child.setData(0, 0, '{}'.format('All data (' + self.xc.labels[i] + ')'))
                child.setIcon(0, helpers.layer_icon(self.xc[i]))
                child.setCheckState(0, 0)
                self.num_rows = self.num_rows + 1
                disableSubset = False
                temp = False
                for j in range(0, len(self.xc.subset_groups)):
                    childtwo = QTreeWidgetItem(parent)
                    childtwo.setData(0, 0, '{}'.format(self.xc.subset_groups[j].label))
                    # child.setEditable(False)
                    childtwo.setIcon(0, helpers.layer_icon(self.xc.subset_groups[j]))
                    childtwo.setCheckState(0, 0)
                    if (not disableSubset) and (not temp):
                        try:
                            self.xc[i].compute_statistic('minimum',
                                                         self.xc[i].subsets[j].components[k],
                                                         subset_state=self.xc.subset_groups[j].subset_state)
                            # self.xc[i].compute_statistic('minimum',
                                                           self.dc[i].subsets[j].components[k],
                                                           subset_state=self.dc[i].subsets[j].subset_state)
                            temp = True
                        except:
                            # child.setData(0, Qt.CheckStateRole, QVariant())
                            disableSubset = True
                    if disableSubset:
                        childtwo.setData(0, Qt.CheckStateRole, QVariant())
                        childtwo.setForeground(0, QtGui.QBrush(Qt.gray))
                    self.num_rows = self.num_rows + 1
        '''

    def minimizeGrayedData(self):
        '''
        minimizes any subsets/components that have no calculable children
        '''
        # For Subset View
        subsetRoot = self.subsetTree.invisibleRootItem().child(1)
        for j in range(0, subsetRoot.childCount()):
            subsetGray = True
            for i in range(0,  subsetRoot.child(j).childCount()):
                child = subsetRoot.child(j).child(i)
                subsetGray2 = True
                if child.foreground(0) != QtGui.QBrush(Qt.gray):
                    subsetGray = False
                for x in range(0, child.childCount()):
                    if child.foreground(0) != QtGui.QBrush(Qt.gray):
                        subsetGray2 = False

                if subsetGray2:
                    subsetRoot.child(j).child(i).setExpanded(False)
            if subsetGray:
                subsetRoot.child(j).setExpanded(False)

        # For Component View
        componentRoot = self.componentTree.invisibleRootItem()
        for j in range(0, componentRoot.childCount()):
            for i in range(0,  componentRoot.child(j).childCount()):
                subsetGray = True
                child = componentRoot.child(j).child(i)
                for x in range(0, child.childCount()):
                    if child.foreground(0) != QtGui.QBrush(Qt.gray):
                        subsetGray = False

                if subsetGray:
                    child.setExpanded(False)


class ModifiedTreeWidget(QTreeWidget):

    def dragEnterEvent(self, event):
        try:
            self.draggedItem = event.source().currentItem()
            super().dragEnterEvent(event)
        except:
            pass

    def dropEvent(self, dropEvent):
        # print("modified tree widget")
        droppedIndex = self.indexAt(dropEvent.pos())
        # droppedIndex = dropEvent.source().currentItem().parent()
        # draggedIndex =  dragQPoint.pos(dropEvent)
        if not droppedIndex.isValid():
            return
        if self.draggedItem:
            dParent = self.draggedItem.parent()
            if dParent:
                if not self.itemFromIndex(droppedIndex.parent()) == dParent:
                    return
                dParent.removeChild(self.draggedItem)
                dParent.insertChild(droppedIndex.row(), self.draggedItem)

        QTreeWidget.dropEvent(self, dropEvent)
