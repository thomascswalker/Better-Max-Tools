# Standard imports
import os, sys, imp
from PySide2 import QtGui, QtCore, QtWidgets
from PySide2.QtGui import QColor
from PySide2.QtCore import Qt, QSortFilterProxyModel, QObject, Signal, Slot
from PySide2.QtWidgets import QFileIconProvider
from pymxs import runtime as rt

# Asset Tracker imports/reloads
import asset
reload(asset)
from helpers import helpers
reload(helpers)

# Import each class/function
from core.asset import *
from helpers.helpers import *

class Model(QtCore.QAbstractItemModel):
    def __init__(self, parent=None):
        super(Model, self).__init__(parent)

        # Define the visible headers in the main tree view
        headers = ("Name", "Ext", "Path", "Type", "Status", "Size")
        self._rootHeaders = [header for header in headers]

        # Build the root (invisible) item in the tree view.
        # This will allow the headers to be set and visible.
        self._rootItem = asset.Asset(self._rootHeaders)

        # Setup the rest of the model data
        self.setupModelData(self._rootItem)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return self._rootItem.columnCount()

    def data(self, index, role):
        item = self.getItem(index)

        # If the index is not valid for some reason, return nothing
        if not index.isValid():
            return None

        # Return the filetype icons
        if role == QtCore.Qt.DecorationRole and index.column() == 0:
            return item.icon()

        # Color the foreground text, depending on the file status
        if role == Qt.BackgroundRole:
            status = item.data(4) # Index 4 is the found/missing status
            if (status):
                return QColor(90,90,90,255)
            else:
                return QColor(255,50,50,128)

        # Ignore non-display and non-edit roles
        if role != QtCore.Qt.DisplayRole and role != QtCore.Qt.EditRole:
            return None

        # For the item status, style the return as:
        # True = Found
        # False = Missing
        if (index.column() == 4):
            status = item.data(4)
            if (status):
                return "Found"
            else:
                return "Missing"

        # For the file size, style the return with
        # the B/KB/MB/GB size.
        if (index.column() == 5):
            size = item.data(5)
            assetSize = getFileSize(size)
            return assetSize

        # For all other cell data
        return item.data(index.column())

    def flags(self, index):
        if not index.isValid():
            return 0

        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

    def getItem(self, index):
        if index.isValid():
            item = index.internalPointer()
            if item:
                return item

        return self._rootItem

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._rootItem.data(section)

        return None

    def index(self, row, column, parent=QtCore.QModelIndex()):
        if parent.isValid() and parent.column() != 0:
            return QtCore.QModelIndex()

        parentItem = self.getItem(parent)
        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QtCore.QModelIndex()

    def insertColumns(self, position, columns, parent=QtCore.QModelIndex()):
        self.beginInsertColumns(parent, position, position + columns - 1)
        success = self._rootItem.insertColumns(position, columns)
        self.endInsertColumns()

        return success

    def insertRows(self, position, rows, parent=QtCore.QModelIndex()):
        parentItem = self.getItem(parent)
        self.beginInsertRows(parent, position, position + rows - 1)
        success = parentItem.insertChildren(position, rows,
                self._rootItem.columnCount())
        self.endInsertRows()

        return success

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()

        childItem = self.getItem(index)
        parentItem = childItem.parent()

        if parentItem == self._rootItem:
            return QtCore.QModelIndex()

        return self.createIndex(parentItem.childNumber(), 0, parentItem)

    def removeColumns(self, position, columns, parent=QtCore.QModelIndex()):
        self.beginRemoveColumns(parent, position, position + columns - 1)
        success = self._rootItem.removeColumns(position, columns)
        self.endRemoveColumns()

        if self._rootItem.columnCount() == 0:
            self.removeRows(0, rowCount())

        return success

    def removeRows(self, position, rows, parent=QtCore.QModelIndex()):
        parentItem = self.getItem(parent)

        self.beginRemoveRows(parent, position, position + rows - 1)
        success = parentItem.removeChildren(position, rows)
        self.endRemoveRows()

        return success

    def rowCount(self, parent=QtCore.QModelIndex()):
        parentItem = self.getItem(parent)

        return parentItem.childCount()

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        if role != QtCore.Qt.EditRole:
            return False

        item = self.getItem(index)
        result = item.setData(index.column(), value)

        if result:
            self.dataChanged.emit(index, index)

        return result

    def insertRefs(self,
                   classType,
                   assetRefs,
                   node):
        # Check to make sure the number of refs is greater than 0
        if len(assetRefs[classType]) > 0:

            # Get the row index to insert at
            row = node.childCount()

            # Insert the reference parent row. This is the 'Materials', 'Geometry',
            # etc. node which can then be expanded.
            node.insertChildren(row, 1, self._rootItem.columnCount())
            refParentNode = node.child(row)

            # If the node insertion worked...
            if (refParentNode != None):

                # Name it
                refParentNode.setData(0, classType)

                # Then iterate through each of the references, inserting each
                for i in range(len(assetRefs[classType])):

                    # Get the 'name' of the asset, which is just the Name and Class
                    assetType = assetRefs[classType][i]

                    # Insert the new node
                    refParentNode.insertChildren(i, 1, self._rootItem.columnCount())

                    # Set the data of the newly-created node
                    refNode = refParentNode.child(i)
                    refNode.setData(0, str(assetType))
                    refNode.setClassType(classType)

    def setupModelData(self, parent):
        parents = [parent]
        numAssets = rt.AssetManager.getNumAssets()

        # For each asset (row)
        for i in range(1, numAssets + 1):

            # Get the asset object
            asset         = rt.AssetManager.getAssetByIndex(i)

            # Get the asset properties
            assetFilename = asset.GetFilename()
            assetBasename = os.path.basename(assetFilename)
            assetName     = os.path.splitext(assetBasename)[0]
            assetPath     = os.path.dirname(assetFilename)
            assetExt      = os.path.splitext(assetBasename)[1]
            if assetExt == "":
                continue
            assetType     = str(asset.GetType())
            assetStatus   = os.path.exists(assetFilename)
            if (assetStatus):
                assetSize = os.path.getsize(assetFilename)
            else:
                assetSize = 0

            # We'll use QFileIconProvider to grab the icon that the OS
            # is currently using to grab the icon to display in the view
            fileInfo = QtCore.QFileInfo(assetFilename)
            iconProvider = QFileIconProvider()
            assetIcon = iconProvider.icon(fileInfo)

            # Read the column data from the rest of the line.
            columnData = [assetName,
                          assetExt,
                          assetPath,
                          assetType,
                          os.path.exists(assetFilename),
                          assetSize]

            # Append a new node to the root
            parent = parents[-1]
            parent.insertChildren(parent.childCount(), 1, self._rootItem.columnCount())
            node = parent.child(parent.childCount() - 1)

            # Fill each column in the current row
            for column in range(len(columnData)):
                node.setData(column, columnData[column])
                node.setIcon(assetIcon)

            # Get the references associated with the asset filename
            # assetRefs = getAssetRefs(assetFilename)

            # Insert three children to the new node for the referenced
            # materials, geometry, and modifiers
            # if len(assetRefs) > 0:
            #     refSuperClasses = getSettings()["RefSuperClasses"]
            #     for refSuperClass in refSuperClasses:
            #         self.insertRefs(str(refSuperClass), assetRefs, node)
