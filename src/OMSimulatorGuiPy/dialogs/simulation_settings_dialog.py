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

'''SimulationSettingsDialog: edits the active SSD's own experiment settings
(ssd:DefaultExperiment plus the solver's maximum step size) -- the same fields
the CLI's --startTime/--stopTime/--tolerance/--stepSize/--resultFile options
override, but persisted on the model itself rather than a one-off run.

Like the other Add* dialogs, this only collects and validates values; the
caller (MainWindow) applies them to the SSD object so every model mutation
still goes through one place.'''

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit


class SimulationSettingsDialog(QDialog):
  def __init__(self, ssd, parent=None):
    super().__init__(parent)
    self.setWindowTitle('Simulation Settings')

    self._startTimeEdit = QLineEdit(str(ssd.startTime), self)
    self._stopTimeEdit = QLineEdit(str(ssd.stopTime), self)
    self._toleranceEdit = QLineEdit(str(ssd.tolerance), self)
    self._stepSizeEdit = QLineEdit(str(ssd.maximumStepSize), self)
    self._resultFileEdit = QLineEdit(ssd.resultFile, self)

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
    buttons.accepted.connect(self._onAccept)
    buttons.rejected.connect(self.reject)

    layout = QFormLayout(self)
    layout.addRow('Start Time:', self._startTimeEdit)
    layout.addRow('Stop Time:', self._stopTimeEdit)
    layout.addRow('Tolerance:', self._toleranceEdit)
    layout.addRow('Step Size:', self._stepSizeEdit)
    layout.addRow('Result File:', self._resultFileEdit)
    layout.addRow(buttons)

  def _onAccept(self) -> None:
    try:
      self.startTime()
      self.stopTime()
      self.tolerance()
      self.stepSize()
    except ValueError:
      return
    if not self._resultFileEdit.text().strip():
      return
    self.accept()

  def startTime(self) -> float:
    return float(self._startTimeEdit.text())

  def stopTime(self) -> float:
    return float(self._stopTimeEdit.text())

  def tolerance(self) -> float:
    return float(self._toleranceEdit.text())

  def stepSize(self) -> float:
    return float(self._stepSizeEdit.text())

  def resultFile(self) -> str:
    return self._resultFileEdit.text().strip()
