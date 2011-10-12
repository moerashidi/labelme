#!/usr/bin/env python
# -*- coding: utf8 -*-

import os.path
import re
import sys

from functools import partial
from collections import defaultdict

from PyQt4.QtGui import *
from PyQt4.QtCore import *

import resources

from lib import newAction, addActions
from shape import Shape
from canvas import Canvas
from zoomwidget import ZoomWidget
from labelDialog import LabelDialog


__appname__ = 'labelme'

# TODO:
# - Zoom is too "steppy".

### Utility functions and classes.

class WindowMixin(object):
    def menu(self, title, actions=None):
        menu = self.menuBar().addMenu(title)
        if actions:
            addActions(menu, actions)
        return menu

    def toolbar(self, title, actions=None):
        toolbar = QToolBar(title)
        toolbar.setObjectName(u'%sToolBar' % title)
        #toolbar.setOrientation(Qt.Vertical)
        toolbar.setContentsMargins(0,0,0,0)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        toolbar.layout().setContentsMargins(0,0,0,0)
        if actions:
            addActions(toolbar, actions)
        self.addToolBar(Qt.LeftToolBarArea, toolbar)
        return toolbar


class MainWindow(QMainWindow, WindowMixin):
    def __init__(self, filename=None):
        super(MainWindow, self).__init__()
        self.setWindowTitle(__appname__)

        self.setContentsMargins(0, 0, 0, 0)

        # Main widgets.
        self.label = LabelDialog(parent=self)
        self.zoom_widget = ZoomWidget()

        self.canvas = Canvas()
        #self.canvas.setAlignment(Qt.AlignCenter)
        self.canvas.setContextMenuPolicy(Qt.ActionsContextMenu)
        self.canvas.zoomRequest.connect(self.zoomRequest)

        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(True)
        self.scrollBars = {
            Qt.Vertical: scroll.verticalScrollBar(),
            Qt.Horizontal: scroll.horizontalScrollBar()
            }
        self.canvas.scrollRequest.connect(self.scrollRequest)

        self.canvas.newShape.connect(self.newShape)

        self.setCentralWidget(scroll)

        # Actions
        action = partial(newAction, self)
        quit = action('&Quit', self.close,
                'Ctrl+Q', 'quit', u'Exit application')
        open = action('&Open', self.openFile,
                'Ctrl+O', 'open', u'Open file')
        color = action('&Color', self.chooseColor,
                'Ctrl+C', 'color', u'Choose line color')
        label = action('&New Item', self.newLabel,
                'Ctrl+N', 'new', u'Add new label')
        delete = action('&Delete', self.deleteSelectedShape,
                'Ctrl+D', 'delete', u'Delete')


        zoom = QWidgetAction(self)
        zoom.setDefaultWidget(self.zoom_widget)

        fit_window = action('&Fit Window', self.setFitWindow,
                'Ctrl+F', 'fit',  u'Fit image to window', checkable=True)

        self.menus = struct(
                file=self.menu('&File'),
                edit=self.menu('&Image'),
                view=self.menu('&View'))
        addActions(self.menus.file, (open, quit))
        addActions(self.menus.edit, (label, color, fit_window))

        #addActions(self.menus.view, (labl,))

        self.tools = self.toolbar('Tools')
        addActions(self.tools, (open, color, None, label, delete, None,
            zoom, fit_window, None, quit))


        self.statusBar().showMessage('%s started.' % __appname__)
        self.statusBar().show()

        # Application state.
        self.image = QImage()
        self.filename = filename
        self.recent_files = []
        self.color = None
        self.zoom_level = 100
        self.fit_window = False

        # TODO: Could be completely declarative.
        # Restore application settings.
        types = {
            'filename': QString,
            'recent-files': QStringList,
            'window/size': QSize,
            'window/position': QPoint,
            'window/geometry': QByteArray,
            # Docks and toolbars:
            'window/state': QByteArray,
        }
        self.settings = settings = Settings(types)
        self.recent_files = settings['recent-files']
        size = settings.get('window/size', QSize(600, 500))
        position = settings.get('window/position', QPoint(0, 0))
        self.resize(size)
        self.move(position)
        # or simply:
        #self.restoreGeometry(settings['window/geometry']
        self.restoreState(settings['window/state'])
        self.color = QColor(settings.get('line/color', QColor(0, 255, 0, 128)))

        # The file menu has default dynamically generated entries.
        self.updateFileMenu()
        # Since loading the file may take some time, make sure it runs in the background.
        self.queueEvent(partial(self.loadFile, self.filename))

        # Callbacks:
        self.zoom_widget.editingFinished.connect(self.paintCanvas)


    ## Callback functions:
    def newShape(self, position):
        """Pop-up and give focus to the label editor.

        position MUST be in global coordinates.
        """
        action = self.label.popUp(position)
        if action == self.label.OK:
            print "Setting label to %s" % self.label.text()
            self.canvas.setLastLabel(self.label.text())
            # TODO: Add to list of labels.
        elif action == self.label.UNDO:
            print "Undo last line"
            self.canvas.undoLastLine()
        elif action == self.label.DELETE:
            self.canvas.deleteLastShape()
        else:
            assert False, "unknown label action"

    def scrollRequest(self, delta, orientation):
        units = - delta / (8 * 15)
        bar = self.scrollBars[orientation]
        bar.setValue(bar.value() + bar.singleStep() * units)

    def zoomRequest(self, delta):
        if not self.fit_window:
            units = delta / (8 * 15)
            scale = 10
            self.zoom_widget.setValue(self.zoom_widget.value() + scale * units)
            self.zoom_widget.editingFinished.emit()

    def setFitWindow(self, value=True):
        self.zoom_widget.setEnabled(not value)
        self.fit_window = value
        self.paintCanvas()

    def queueEvent(self, function):
        QTimer.singleShot(0, function)

    def loadFile(self, filename=None):
        """Load the specified file, or the last opened file if None."""
        if filename is None:
            filename = self.settings['filename']
        # FIXME: Load the actual file here.
        if QFile.exists(filename):
            # Load image
            image = QImage(filename)
            if image.isNull():
                message = "Failed to read %s" % filename
            else:
                message = "Loaded %s" % os.path.basename(unicode(filename))
                self.image = image
                self.filename = filename
                self.loadPixmap()
            self.statusBar().showMessage(message)

    def resizeEvent(self, event):
        if self.fit_window and self.canvas and not self.image.isNull():
            self.paintCanvas()
        super(MainWindow, self).resizeEvent(event)

    def loadPixmap(self):
        assert not self.image.isNull(), "cannot load null image"
        self.canvas.pixmap = QPixmap.fromImage(self.image)

    def paintCanvas(self):
        assert not self.image.isNull(), "cannot paint null image"
        self.canvas.scale = self.fitSize() if self.fit_window\
                            else 0.01 * self.zoom_widget.value()
        self.canvas.adjustSize()
        self.canvas.repaint()

    def fitSize(self):
        """Figure out the size of the pixmap in order to fit the main widget."""
        e = 2.0 # So that no scrollbars are generated.
        w1 = self.centralWidget().width() - e
        h1 = self.centralWidget().height() - e
        a1 = w1/ h1
        # Calculate a new scale value based on the pixmap's aspect ratio.
        w2 = self.canvas.pixmap.width() - 0.0
        h2 = self.canvas.pixmap.height() - 0.0
        a2 = w2 / h2
        return w1 / w2 if a2 >= a1 else h1 / h2


    def closeEvent(self, event):
        # TODO: Make sure changes are saved.
        s = self.settings
        s['filename'] = self.filename if self.filename else QString()
        s['window/size'] = self.size()
        s['window/position'] = self.pos()
        s['window/state'] = self.saveState()
        s['line/color'] = self.color
        #s['window/geometry'] = self.saveGeometry()

    def updateFileMenu(self):
        """Populate menu with recent files."""

    ## Dialogs.
    def openFile(self):
        if not self.check():
            return
        path = os.path.dirname(unicode(self.filename))\
                if self.filename else '.'
        formats = ['*.%s' % unicode(fmt).lower()\
                for fmt in QImageReader.supportedImageFormats()]
        filename = unicode(QFileDialog.getOpenFileName(self,
            '%s - Choose Image', path, 'Image files (%s)' % ' '.join(formats)))
        if filename:
            self.loadFile(filename)

    def check(self):
        # TODO: Prompt user to save labels etc.
        return True

    def chooseColor(self):
        self.color = QColorDialog.getColor(self.color, self,
                u'Choose line color', QColorDialog.ShowAlphaChannel)
        # Change the color for all shape lines:
        Shape.line_color = self.color
        self.canvas.repaint()

    def newLabel(self):
        self.canvas.deSelectShape()
        self.canvas.startLabeling=True

    def deleteSelectedShape(self):
        self.canvas.deleteSelected()


class Settings(object):
    """Convenience dict-like wrapper around QSettings."""
    def __init__(self, types=None):
        self.data = QSettings()
        self.types = defaultdict(lambda: QVariant, types if types else {})

    def __setitem__(self, key, value):
        t = self.types[key]
        self.data.setValue(key,
                t(value) if not isinstance(value, t) else value)

    def __getitem__(self, key):
        return self._cast(key, self.data.value(key))

    def get(self, key, default=None):
        return self._cast(key, self.data.value(key, default))

    def _cast(self, key, value):
        # XXX: Very nasty way of converting types to QVariant methods :P
        t = self.types[key]
        if t != QVariant:
            method = getattr(QVariant, re.sub('^Q', 'to', t.__name__, count=1))
            return method(value)
        return value


class struct(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def main(argv):
    """Standard boilerplate Qt application code."""
    app = QApplication(argv)
    app.setApplicationName(__appname__)
    win = MainWindow(argv[1] if len(argv) == 2 else None)
    win.show()
    return app.exec_()

if __name__ == '__main__':
    sys.exit(main(sys.argv))
