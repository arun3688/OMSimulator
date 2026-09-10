# This file is part of OpenModelica.
#
# Copyright (c) 1998-2026, Open Source Modelica Consortium (OSMC),
# c/o Linköpings universitet, Department of Computer and Information Science,
# SE-58183 Linköping, Sweden.
#
# All rights reserved.
#
# THIS PROGRAM IS PROVIDED UNDER THE TERMS OF AGPL VERSION 3 LICENSE OR
# THIS OSMC PUBLIC LICENSE (OSMC-PL) VERSION 1.8.
# ANY USE, REPRODUCTION OR DISTRIBUTION OF THIS PROGRAM CONSTITUTES
# RECIPIENT'S ACCEPTANCE OF THE OSMC PUBLIC LICENSE OR THE GNU AGPL
# VERSION 3, ACCORDING TO RECIPIENTS CHOICE.
#
# The OpenModelica software and the OSMC (Open Source Modelica Consortium)
# Public License (OSMC-PL) are obtained from OSMC, either from the above
# address, from the URLs:
# http://www.openmodelica.org or
# https://github.com/OpenModelica/ or
# http://www.ida.liu.se/projects/OpenModelica,
# and in the OpenModelica distribution.
#
# GNU AGPL version 3 is obtained from:
# https://www.gnu.org/licenses/licenses.html#GPL
#
# This program is distributed WITHOUT ANY WARRANTY; without
# even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE, EXCEPT AS EXPRESSLY SET FORTH
# IN THE BY RECIPIENT SELECTED SUBSIDIARY LICENSE CONDITIONS OF OSMC-PL.
#
# See the full OSMC Public License conditions for more details.

'''ResultsViewer: a plain top-level window over one simulation's result
file -- a checkable list of every signal (minus 'time', which is always the
plot's x-axis) and a pyqtgraph plot showing whichever ones are checked.
Deliberately minimal for v1: no multi-axis/unit grouping or curve styling
beyond pyqtgraph's own defaults.'''

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QListWidget, QListWidgetItem, QSplitter, QWidget

from OMSimulatorGui.results.result_reader import readResultFile

# pyqtgraph defaults to a dark theme (black background/white foreground) --
# switch to a white background with dark axes/grid/text to match the rest
# of this app's plain light UI, before any PlotWidget is constructed.
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')


class ResultsViewer(QWidget):
  def __init__(self, resultPath: str, parent=None):
    super().__init__(parent)
    self.setWindowFlag(Qt.WindowType.Window)
    self.setWindowTitle(f'Results - {resultPath}')
    self.resize(1000, 600)

    self._signals = readResultFile(resultPath)
    self._curves: dict[str, object] = {}
    # Cycles forward only (never reused on uncheck) so a signal's color
    # stays stable across toggling other signals on/off -- pg.mkPen()'s own
    # default pen now resolves to the 'foreground' config color (black,
    # see above), which made every curve render identically and
    # indistinguishable from the axes/text.
    self._nextColorIndex = 0

    self._list = QListWidget(self)
    for name in sorted(self._signals):
      if name == 'time':
        continue
      item = QListWidgetItem(name, self._list)
      item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
      item.setCheckState(Qt.CheckState.Unchecked)
    self._list.itemChanged.connect(self._onItemChanged)

    self._plot = pg.PlotWidget(self)
    self._plot.addLegend()
    self._plot.showGrid(x=True, y=True)

    splitter = QSplitter(self)
    splitter.addWidget(self._list)
    splitter.addWidget(self._plot)
    splitter.setStretchFactor(0, 0)
    splitter.setStretchFactor(1, 1)
    splitter.setSizes([250, 750])

    layout = QHBoxLayout(self)
    layout.addWidget(splitter)

  def _onItemChanged(self, item: QListWidgetItem) -> None:
    name = item.text()
    if item.checkState() == Qt.CheckState.Checked:
      times, values = self._signals[name]
      color = pg.intColor(self._nextColorIndex, hues=12)
      self._nextColorIndex += 1
      self._curves[name] = self._plot.plot(times, values, name=name, pen=pg.mkPen(color=color, width=2))
    else:
      curve = self._curves.pop(name, None)
      if curve is not None:
        self._plot.removeItem(curve)
