#!/usr/bin/env python

#
# Author: Steven Ludtke  3/4/2011
# Copyright (c) 2011- Baylor College of Medicine
#
# This software is issued under a joint BSD/GNU license. You may use the
# source code in this file under either license. However, note that the
# complete EMAN2 and SPARX software packages have some GPL dependencies,
# so you are responsible for compliance with the licenses of these packages
# if you opt to use BSD licensing. The warranty disclaimer below holds
# in either instance.
#
# This complete copyright notice must be included in any revised version of the
# source code. Additional authorship citations may be added, but existing
# author citations must be preserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston MA 02111-1307 USA
#

from PyQt4 import QtCore, QtGui
from PyQt4.QtCore import Qt
from optparse import OptionParser
import sys
import os
import weakref
import threading

from EMAN2 import *
from emapplication import get_application, EMApp
from emimage2d import EMImage2DWidget
from emimagemx import EMImageMXWidget
from emimage3d import EMImage3DWidget
from emshape import EMShape
from valslider import *

def main():
	progname = os.path.basename(sys.argv[0])
	usage = """%prog [options] <image file>

	Provides a GUI interface for applying a sequence of filters to an image, stack of images or a volume."""

	parser = OptionParser(usage=usage,version=EMANVERSION)

#	parser.add_option("--boxsize","-B",type="int",help="Box size in pixels",default=64)
#	parser.add_option("--shrink",type="int",help="Shrink factor for full-frame view, default=0 (auto)",default=0)
	parser.add_option("--apix",type="float",help="Override the A/pix value stored in the file header",default=0.0)
	parser.add_option("--verbose", "-v", dest="verbose", action="store", metavar="n", type="int", default=0, help="verbose level [0-9], higner number means higher level of verboseness")
	
	(options, args) = parser.parse_args()
		
	if len(args) != 1: parser.error("You must specify a single data file on the command-line.")
	if not file_exists(args[0]): parser.error("%s does not exist" %args[0])
#	if options.boxsize < 2: parser.error("The boxsize you specified is too small")
#	# The program will not run very rapidly at such large box sizes anyhow
#	if options.boxsize > 2048: parser.error("The boxsize you specified is too large.\nCurrently there is a hard coded max which is 2048.\nPlease contact developers if this is a problem.")
	
#	logid=E2init(sys.argv)
	
	app = EMApp()
	
	control=EMFilterTool(app,datafile=args[0],options.apix,options.verbose)
	control.show()
	app.execute()
#	E2end(logid)


class EMTomoBoxer(QtGui.QMainWindow):
	"""This class represents the EMTomoBoxer application instance.  """
	
	def __init__(self,application,data=None,apix=0.0,verbose=0):
		QtGui.QWidget.__init__(self)
		
		self.app=weakref.ref(application)
		self.apix=apix
		self.setWindowTitle("e2filtertool.py")
		
		# Menu Bar
		self.mfile=self.menuBar().addMenu("File")
		self.mfile_save_processed=self.mfile.addAction("Save processed data")
		self.mfile_quit=self.mfile.addAction("Quit")

		self.mwin=self.menuBar().addMenu("Window")
		self.mwin_boxes=self.mwin.addAction("Particles")
		self.mwin_single=self.mwin.addAction("Single Particle")
		self.mwin_average=self.mwin.addAction("Averaging")


		self.setCentralWidget(QtGui.QWidget())
		self.gbl = QtGui.QGridLayout(self.centralWidget())

		# relative stretch factors
		self.gbl.setColumnStretch(0,1)
		self.gbl.setColumnStretch(1,4)
		self.gbl.setColumnStretch(2,0)
		self.gbl.setRowStretch(1,1)
		self.gbl.setRowStretch(0,4)
		
		# 3 orthogonal restricted projection views
		self.xyview = EMImage2DWidget()
		self.gbl.addWidget(self.xyview,0,1)

		self.xzview = EMImage2DWidget()
		self.gbl.addWidget(self.xzview,1,1)

		self.zyview = EMImage2DWidget()
		self.gbl.addWidget(self.zyview,0,0)

		# Select Z for xy view
		self.wdepth = QtGui.QSlider()
		self.gbl.addWidget(self.wdepth,1,2)
		
		### Control panel area in upper left corner
		self.gbl2 = QtGui.QGridLayout()
		self.gbl.addLayout(self.gbl2,1,0)
		
		# box size
		self.wboxsize=ValBox(label="Box Size:",value=100)
		self.gbl2.addWidget(self.wboxsize,0,0,1,2)
		
		# max or mean
		self.wmaxmean=QtGui.QPushButton("MaxProj")
		self.wmaxmean.setCheckable(True)
		self.gbl2.addWidget(self.wmaxmean,1,0)
		
		# number slices
		self.wnlayers=QtGui.QSpinBox()
		self.wnlayers.setMinimum(1)
		self.wnlayers.setMaximum(256)
		self.wnlayers.setValue(1)
		self.gbl2.addWidget(self.wnlayers,1,1)
		
		# Local boxes in side view
		self.wlocalbox=QtGui.QCheckBox("Limit Side Boxes")
		self.gbl2.addWidget(self.wlocalbox,2,0)
		
		# scale factor
		self.wscale=ValSlider(rng=(.1,2),label="Sca:",value=1.0)
		self.gbl2.addWidget(self.wscale,3,0,1,2)
		
		# 2-D filters
		self.wfilt = ValSlider(rng=(0,50),label="Filt:",value=0.0)
		self.gbl2.addWidget(self.wfilt,4,0,1,2)
		
		
		
		self.curbox=-1
		self.boxes=[]						# array of box info, each is (x,y,z,...)
		self.boxesimgs=[]					# z projection of each box
		self.xydown=None
		
		# file menu
		QtCore.QObject.connect(self.mfile_save_processed,QtCore.SIGNAL("triggered(bool)")  ,self.menu_file_save_processed  )
		QtCore.QObject.connect(self.mfile_quit,QtCore.SIGNAL("triggered(bool)")  ,self.menu_file_quit)

		# window menu
		QtCore.QObject.connect(self.mwin_boxes,QtCore.SIGNAL("triggered(bool)")  ,self.menu_win_boxes  )
		QtCore.QObject.connect(self.mwin_single,QtCore.SIGNAL("triggered(bool)")  ,self.menu_win_single  )
		QtCore.QObject.connect(self.mwin_average,QtCore.SIGNAL("triggered(bool)")  ,self.menu_win_average  )

		# all other widgets
		QtCore.QObject.connect(self.wdepth,QtCore.SIGNAL("valueChanged(int)"),self.event_depth)
		QtCore.QObject.connect(self.wnlayers,QtCore.SIGNAL("valueChanged(int)"),self.event_nlayers)
		QtCore.QObject.connect(self.wboxsize,QtCore.SIGNAL("valueChanged"),self.event_boxsize)
		QtCore.QObject.connect(self.wmaxmean,QtCore.SIGNAL("clicked(bool)"),self.event_projmode)
		QtCore.QObject.connect(self.wscale,QtCore.SIGNAL("valueChanged")  ,self.event_scale  )
		QtCore.QObject.connect(self.wfilt,QtCore.SIGNAL("valueChanged")  ,self.event_filter  )
		QtCore.QObject.connect(self.wlocalbox,QtCore.SIGNAL("stateChanged(int)")  ,self.event_localbox  )
		
		QtCore.QObject.connect(self.xyview,QtCore.SIGNAL("mousedown"),self.xy_down)
		QtCore.QObject.connect(self.xyview,QtCore.SIGNAL("mousedrag"),self.xy_drag)
		QtCore.QObject.connect(self.xyview,QtCore.SIGNAL("mouseup"),self.xy_up  )
		QtCore.QObject.connect(self.xyview,QtCore.SIGNAL("mousewheel"),self.xy_wheel  )
		QtCore.QObject.connect(self.xyview,QtCore.SIGNAL("set_scale"),self.xy_scale)
		QtCore.QObject.connect(self.xyview,QtCore.SIGNAL("origin_update"),self.xy_origin)

		QtCore.QObject.connect(self.xzview,QtCore.SIGNAL("mousedown"),self.xz_down)
		QtCore.QObject.connect(self.xzview,QtCore.SIGNAL("mousedrag"),self.xz_drag)
		QtCore.QObject.connect(self.xzview,QtCore.SIGNAL("mouseup")  ,self.xz_up  )
		QtCore.QObject.connect(self.xzview,QtCore.SIGNAL("set_scale"),self.xz_scale)
		QtCore.QObject.connect(self.xzview,QtCore.SIGNAL("origin_update"),self.xz_origin)

		QtCore.QObject.connect(self.zyview,QtCore.SIGNAL("mousedown"),self.zy_down)
		QtCore.QObject.connect(self.zyview,QtCore.SIGNAL("mousedrag"),self.zy_drag)
		QtCore.QObject.connect(self.zyview,QtCore.SIGNAL("mouseup")  ,self.zy_up  )
		QtCore.QObject.connect(self.zyview,QtCore.SIGNAL("set_scale"),self.zy_scale)
		QtCore.QObject.connect(self.zyview,QtCore.SIGNAL("origin_update"),self.zy_origin)

		self.viewer=None			# viewer window for data
		self.filters=[]				# list of filter specifications (name,dict)
		self.origdata=None
		self.nx=0
		self.ny=0
		self.nz=0

		if data!=None : self.set_data(data)
		
		
#		QtCore.QObject.connect(self.boxesviewer,QtCore.SIGNAL("mx_image_selected"),self.img_selected)
		
	def set_data(self,data):
		if data==None :
			self.data=None
			return
		
		self.nimg=EMUtil.get_image_count(data)
		
		self.origdata=self.read_image(data,0)
		self.nx=data["nx"]
		self.ny=data["ny"]
		self.nz=data["nz"]
		
		if data["nz"]==1:
			if self.n>20 : 
				self.n=20
			if self.n>1 :
				self.origdata=EMData.read_images(data,
		
		
		self.data=data
		self.datafile=None
		if self.yshort: self.datasize=(data["nx"],data["nz"],data["ny"])
		else: self.datasize=(data["nx"],data["ny"],data["nz"])
		self.wdepth.setRange(0,self.datasize[2]-1)
		self.boxes=[]
		self.curbox=-1
		
		self.wdepth.setValue(self.datasize[2]/2)
		self.update_all()


	def menu_file_save_processed(self):
		"incomplete"
		
	def menu_file_quit(self):
		self.close()
		
	def closeEvent(self,event):
		print "Exiting"
		if self.viewer!=None : self.viewer.close()
		event.accept()
		#self.app().close_specific(self)
		self.emit(QtCore.SIGNAL("module_closed")) # this signal is important when e2ctf is being used by a program running its own event loop

	#def closeEvent(self,event):
		#self.target().done()


if __name__ == "__main__":
	main()
		
		
		
