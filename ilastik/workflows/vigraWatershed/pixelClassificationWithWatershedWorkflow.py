###############################################################################
#   ilastik: interactive learning and segmentation toolkit
#
#       Copyright (C) 2011-2014, the ilastik developers
#                                <team@ilastik.org>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# In addition, as a special exception, the copyright holders of
# ilastik give you permission to combine ilastik with applets,
# workflows and plugins which are not covered under the GNU
# General Public License.
#
# See the LICENSE file for details. License information is also available
# on the ilastik web site at:
#		   http://ilastik.org/license.html
###############################################################################
import vigra
from lazyflow.graph import Operator, InputSlot, OutputSlot
from ilastik.workflows.pixelClassification import PixelClassificationWorkflow
from ilastik.applets.vigraWatershedViewer import VigraWatershedViewerApplet

class PixelClassificationWithWatershedWorkflow(PixelClassificationWorkflow):

    workflowName = "Pixel Classification (with Watershed Preview)"
    workflowDisplayName = "Pixel Classification (with Watershed Preview)"
    
    def __init__( self, shell, headless, workflow_cmdline_args, project_creation_args, *args, **kwargs ):
        super(PixelClassificationWithWatershedWorkflow, self).__init__( shell, headless, workflow_cmdline_args, project_creation_args, *args, **kwargs )

        # Create applets
        self.watershedApplet = VigraWatershedViewerApplet(self, "Watershed", "Watershed")

        opDataExport = self.dataExportApplet.topLevelOperator
        opDataExport.SelectionNames.setValue( self.EXPORT_NAMES + ["Watershed Seeds", "Watershed Labels"] )
        
        # Expose for shell (insert before last applet, which is the batch applet)
        self._applets.insert(-2, self.watershedApplet)

    def connectLane(self, laneIndex):
        super( PixelClassificationWithWatershedWorkflow, self ).connectLane( laneIndex )

        # Get the right lane from each operator
        opPixelClassification = self.pcApplet.topLevelOperator.getLane(laneIndex)
        opWatershedViewer = self.watershedApplet.topLevelOperator.getLane(laneIndex)
        opDataExport = self.dataExportApplet.topLevelOperator.getLane(laneIndex)

        # We allow the user to declare her data as tyx instead of zyx,
        #  which enables 2D features for pixel classification.
        # But the watershed viewer insists on 3D data, so we'll use this special
        #  operator to rename the 't' axis to the 'z' axis before feeding it in.
        opMake3DRaw = _OpMake3D(parent=self)
        opMake3DInput = _OpMake3D(parent=self)

        # Connect them up
        opMake3DInput.Input.connect( opPixelClassification.CachedPredictionProbabilities )
        opMake3DRaw.Input.connect( opPixelClassification.InputImages )
        
        opWatershedViewer.InputImage.connect( opMake3DInput.Output )
        opWatershedViewer.RawImage.connect( opMake3DRaw.Output )

        opDataExport.Inputs.resize( len(PixelClassificationWorkflow.EXPORT_NAMES) + 2 )
        opDataExport.Inputs[-2].connect( opWatershedViewer.Seeds )
        opDataExport.Inputs[-1].connect( opWatershedViewer.WatershedLabels )

    def handleAppletStateUpdateRequested(self):
        super(PixelClassificationWithWatershedWorkflow, self).handleAppletStateUpdateRequested()
        predictions_ready = self._shell.isAppletEnabled(self.dataExportApplet)
        self._shell.setAppletEnabled(self.watershedApplet, predictions_ready)

class _OpMake3D(Operator):
    """
    Pass-through operator, except that the 't' axis (if any) is renamed to 'z'.
    """
    Input = InputSlot()
    Output = OutputSlot()

    def setupOutputs(self):
        self.Output.meta.assignFrom(self.Input.meta)
        input_tags = self.Input.meta.axistags
        if 't' in input_tags and 'z' not in input_tags:
            # Replace t -> z
            self.Output.meta.axistags['t'] = vigra.AxisInfo.z

    def execute(self, slot, subindex, roi, result):
        self.Input.get(roi).writeInto(result).wait()

    def propagateDirty(self, slot, subindex, roi):
        self.Output.setDirty(roi.start, roi.stop)
