#
from __future__ import print_function
# Author: Pawel A.Penczek, 09/09/2006 (Pawel.A.Penczek@uth.tmc.edu)
# Copyright (c) 2000-2006 The University of Texas - Houston Medical School
#
# This software is issued under a joint BSD/GNU license. You may use the
# source code in this file under either license. However, note that the
# complete EMAN2 and SPARX software packages have some GPL dependencies,
# so you are responsible for compliance with the licenses of these packages
# if you opt to use BSD licensing. The warranty disclaimer below holds
# in either instance.
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307 USA
#

import EMAN2_cppwrap
import sparx_filter
import sparx_fundamentals
import sparx_global_def
import sparx_morphology
import mpi
import numpy
import numpy.random
import os
import random
import sparx_statistics
import string
import sys
import time
import sparx_utilities
pass#IMPORTIMPORTIMPORT import EMAN2
pass#IMPORTIMPORTIMPORT import EMAN2_cppwrap
pass#IMPORTIMPORTIMPORT import datetime
pass#IMPORTIMPORTIMPORT import filter
pass#IMPORTIMPORTIMPORT import fundamentals
pass#IMPORTIMPORTIMPORT import global_def
pass#IMPORTIMPORTIMPORT import math
pass#IMPORTIMPORTIMPORT import morphology
pass#IMPORTIMPORTIMPORT import mpi
pass#IMPORTIMPORTIMPORT import numpy
pass#IMPORTIMPORTIMPORT import numpy.random
pass#IMPORTIMPORTIMPORT import os
pass#IMPORTIMPORTIMPORT import projection
pass#IMPORTIMPORTIMPORT import random
pass#IMPORTIMPORTIMPORT import reconstruction
pass#IMPORTIMPORTIMPORT import statistics
pass#IMPORTIMPORTIMPORT import string
pass#IMPORTIMPORTIMPORT import subprocess
pass#IMPORTIMPORTIMPORT import sys
pass#IMPORTIMPORTIMPORT import time
pass#IMPORTIMPORTIMPORT import types
pass#IMPORTIMPORTIMPORT import utilities
from builtins import range
from builtins import object
pass#IMPORTIMPORTIMPORT from global_def import *

def insert_slices(reconstructor, proj):
	xforms = [ proj.get_attr("xform.projection") ]
	weights = [ proj.get_attr_default("weight", 1.0) ]
	ixform = 0
	while True:
		ixform += 1
		xform_proj = proj.get_attr_default("xform.projection" + str(ixform), None)
		if xform_proj == None:
			break
		# putting params in a list does not seem to be necessary, one could call reconstructor as one goes.
		xforms.append(xform_proj)
		#weights.append(proj.get_attr_default("weight" + str(ixform), 1.0))
		weights.append(1.0)
	for i in range(len(xforms)):
		reconstructor.insert_slice( proj, xforms[i], weights[i] )

def recons3d_4nn_MPI(myid, prjlist, symmetry="c1", finfo=None, snr = 1.0, npad=2, xysize=-1, zsize=-1, mpi_comm=None):
	pass#IMPORTIMPORTIMPORT from utilities  import reduce_EMData_to_root, pad
	pass#IMPORTIMPORTIMPORT from EMAN2      import Reconstructors
	pass#IMPORTIMPORTIMPORT from utilities  import iterImagesList
	pass#IMPORTIMPORTIMPORT from mpi        import MPI_COMM_WORLD
	pass#IMPORTIMPORTIMPORT import types

	if mpi_comm == None:
		mpi_comm = mpi.MPI_COMM_WORLD

	if type(prjlist) == list:
		prjlist = sparx_utilities.iterImagesList(prjlist)

	if not prjlist.goToNext():
		sparx_global_def.ERROR("empty input list","recons3d_4nn_MPI",1)

	imgsize = prjlist.image().get_xsize()
	if prjlist.image().get_ysize() != imgsize:
		imgsize = max(imgsize, prjlist.image().get_ysize())
		dopad = True
	else:
		dopad = False
	prjlist.goToPrev()

	fftvol = EMAN2_cppwrap.EMData()		
	weight = EMAN2_cppwrap.EMData()
	if (xysize == -1 and zsize == -1 ):
		params = {"size":imgsize, "npad":npad, "symmetry":symmetry, "fftvol":fftvol, "weight":weight, "snr":snr}
		r = EMAN2_cppwrap.Reconstructors.get( "nn4", params )
	else:
		if ( xysize != -1 and zsize != -1):
			rx = float(xysize)/imgsize
			ry = float(xysize)/imgsize
			rz = float(zsize)/imgsize
		elif( xysize != -1):
			rx = float(xysize)/imgsize
			ry = float(xysize)/imgsize
			rz = 1.0
		else:
			rx = 1.0
			ry = 1.0
			rz = float(zsize)/imgsize
		params = {"sizeprojection":imgsize, "npad":npad, "symmetry":symmetry, "fftvol":fftvol,"weight":weight,"xratio":rx,"yratio":ry,"zratio":rz}
		r = EMAN2_cppwrap.Reconstructors.get( "nn4_rect", params )
	r.setup()

	if not (finfo is None): nimg = 0
	while prjlist.goToNext():
		prj = prjlist.image()
		if dopad:
			prj = sparx_utilities.pad(prj, imgsize,imgsize, 1, "circumference")
		insert_slices(r, prj)
		if( not (finfo is None) ):
			nimg += 1
			finfo.write("Image %4d inserted.\n" %(nimg) )
			finfo.flush()

	if not (finfo is None): 
		finfo.write( "Begin reducing ...\n" )
		finfo.flush()

	sparx_utilities.reduce_EMData_to_root(fftvol, myid, comm=mpi_comm)
	sparx_utilities.reduce_EMData_to_root(weight, myid, comm=mpi_comm)

	if myid == 0:  dummy = r.finish(True)
	else:
		pass#IMPORTIMPORTIMPORT from utilities import model_blank
		if ( xysize == -1 and zsize == -1 ):
			fftvol = sparx_utilities.model_blank(imgsize, imgsize, imgsize)
		else:
			if zsize == -1:
				fftvol = sparx_utilities.model_blank(xysize, xysize, imgsize)
			elif xysize == -1:
				fftvol = sparx_utilities.model_blank(imgsize, imgsize, zsize)
			else:
				fftvol = sparx_utilities.model_blank(xysize, xysize, zsize)
	return fftvol

"""Multiline Comment0"""
"""Multiline Comment1"""

def recons3d_trl_struct_MPI(myid, main_node, prjlist, paramstructure, refang, rshifts_shrank, delta, upweighted = True, mpi_comm=None, CTF = True, target_size=-1, avgnorm = 1.0, norm_per_particle = None):
	"""
		recons3d_4nn_ctf - calculate CTF-corrected 3-D reconstruction from a set of projections using three Eulerian angles, two shifts, and CTF settings for each projeciton image
		Input
			list_of_prjlist: list of lists of projections to be included in the reconstruction
	"""
	pass#IMPORTIMPORTIMPORT from utilities  import reduce_EMData_to_root, random_string, get_im, findall
	pass#IMPORTIMPORTIMPORT from EMAN2      import Reconstructors
	pass#IMPORTIMPORTIMPORT from utilities  import model_blank
	pass#IMPORTIMPORTIMPORT from filter	import filt_table
	pass#IMPORTIMPORTIMPORT from fundamentals import fshift
	pass#IMPORTIMPORTIMPORT from mpi        import MPI_COMM_WORLD, mpi_barrier
	pass#IMPORTIMPORTIMPORT import types
	pass#IMPORTIMPORTIMPORT import datetime
	
	if mpi_comm == None: mpi_comm = mpi.MPI_COMM_WORLD

	refvol = sparx_utilities.model_blank(target_size)
	refvol.set_attr("fudge", 1.0)

	if CTF: do_ctf = 1
	else:   do_ctf = 0

	fftvol = EMAN2_cppwrap.EMData()
	weight = EMAN2_cppwrap.EMData()

	pass#IMPORTIMPORTIMPORT from utilities import info
	params = {"size":target_size, "npad":2, "snr":1.0, "sign":1, "symmetry":"c1", "refvol":refvol, "fftvol":fftvol, "weight":weight, "do_ctf": do_ctf}
	r = EMAN2_cppwrap.Reconstructors.get( "nn4_ctfw", params )
	r.setup()
	
	if norm_per_particle == None: norm_per_particle = len(prjlist)*[1.0]

	nnx = prjlist[0].get_xsize()
	nny = prjlist[0].get_ysize()
	nshifts = len(rshifts_shrank)
	for im in range(len(prjlist)):
		#  parse projection structure, generate three lists:
		#  [ipsi+iang], [ishift], [probability]
		#  Number of orientations for a given image
		numbor = len(paramstructure[im][2])
		ipsiandiang = [ paramstructure[im][2][i][0]/1000  for i in range(numbor) ]
		allshifts   = [ paramstructure[im][2][i][0]%1000  for i in range(numbor) ]
		probs       = [ paramstructure[im][2][i][1] for i in range(numbor) ]
		#  Find unique projection directions
		tdir = list(set(ipsiandiang))
		bckgn = prjlist[im].get_attr("bckgnoise")
		ct = prjlist[im].get_attr("ctf")
		#  For each unique projection direction:
		data = [None]*nshifts
		for ii in range(len(tdir)):
			#  Find the number of times given projection direction appears on the list, it is the number of different shifts associated with it.
			lshifts = sparx_utilities.findall(tdir[ii], ipsiandiang)
			toprab  = 0.0
			for ki in range(len(lshifts)):  toprab += probs[lshifts[ki]]
			recdata = EMAN2_cppwrap.EMData(nny,nny,1,False)
			recdata.set_attr("is_complex",0)
			for ki in range(len(lshifts)):
				lpt = allshifts[lshifts[ki]]
				if( data[lpt] == None ):
					data[lpt] = sparx_fundamentals.fshift(prjlist[im], rshifts_shrank[lpt][0], rshifts_shrank[lpt][1])
					data[lpt].set_attr("is_complex",0)
				EMAN2_cppwrap.Util.add_img(recdata, EMAN2_cppwrap.Util.mult_scalar(data[lpt], probs[lshifts[ki]]/toprab))
			recdata.set_attr_dict({"padffted":1, "is_fftpad":1,"is_fftodd":0, "is_complex_ri":1, "is_complex":1})
			if not upweighted:  recdata = sparx_filter.filt_table(recdata, bckgn )
			recdata.set_attr_dict( {"bckgnoise":bckgn, "ctf":ct} )
			ipsi = tdir[ii]%100000
			iang = tdir[ii]/100000
			r.insert_slice( recdata, EMAN2_cppwrap.Transform({"type":"spider","phi":refang[iang][0],"theta":refang[iang][1],"psi":refang[iang][2]+ipsi*delta}), toprab*avgnorm/norm_per_particle[im])
	#  clean stuff
	del bckgn, recdata, tdir, ipsiandiang, allshifts, probs


	sparx_utilities.reduce_EMData_to_root(fftvol, myid, main_node, comm=mpi_comm)
	sparx_utilities.reduce_EMData_to_root(weight, myid, main_node, comm=mpi_comm)

	if myid == main_node:
		dummy = r.finish(True)
	mpi.mpi_barrier(mpi_comm)

	if myid == main_node: return fftvol, weight, refvol
	else: return None, None, None


def recons3d_4nn_ctf(stack_name, list_proj = [], snr = 1.0, sign=1, symmetry="c1", verbose=0, npad=2, xysize = -1, zsize = -1 ):
	"""Perform a 3-D reconstruction using Pawel's FFT Back Projection algoritm.

	   Input:
	    stack_name - name of the stack file on a disk,
	                 each image has to have the following attributes set:
			 psi, theta, phi, sx, sy, defocus, 
	    list_proj - list of images from stack_name to be included in the reconstruction
	    symmetry	 -- Point group of the target molecule (defaults to "C1")

	   Return:  3d reconstructed volume image

	   Usage:
	     
	     anglelist = getAngles("myangles.txt") # not yet written
	     vol = do_reconstruction(filepattern, start, end, anglelist, symmetry)
	"""
	pass#IMPORTIMPORTIMPORT import types
	pass#IMPORTIMPORTIMPORT from EMAN2     import Reconstructors
	pass#IMPORTIMPORTIMPORT from utilities import pad

	# read first image to determine the size to use
	if list_proj == []:	
		if type(stack_name) == bytes: nima = EMAN2_cppwrap.EMUtil.get_image_count(stack_name)
		else : nima = len(stack_name)
		list_proj = list(range(nima)) 
	# read first image to determine the size to use
	if type(stack_name) == bytes:
		proj = EMAN2_cppwrap.EMData()
		proj.read_image(stack_name, list_proj[0])
	else:    proj = stack_name[list_proj[0]].copy()

	# convert angles to transform (rotation) objects
	# horatio active_refactoring Jy51i1EwmLD4tWZ9_00000_1
	# active = proj.get_attr_default('active', 1)
	size   = proj.get_xsize()
	if proj.get_ysize() != size:
		size = max(size, proj.get_ysize())
		dopad = True
	else:
		dopad = False

	# reconstructor
	fftvol = EMAN2_cppwrap.EMData()
	weight = EMAN2_cppwrap.EMData()
	params = {"npad":npad, "symmetry":symmetry, "snr":snr, "sign":sign, "fftvol":fftvol, "weight":weight}
	if ( xysize == -1 and zsize == -1 ):
		params["size"] = size
		r = EMAN2_cppwrap.Reconstructors.get("nn4_ctf", params)
	else:
		if ( xysize != -1 and zsize != -1):
			rx = float(xysize)/size
			ry = float(xysize)/size
			rz = float(zsize)/size
		elif( xysize != -1):
			rx = float(xysize)/size
			ry = float(xysize)/size
			rz = 1.0
		else:
			rx = 1.0
			ry = 1.0
			rz = float(zsize)/size

		params["sizeprojection"] = size
		params["xratio"] = rx
		params["yratio"] = ry
		params["zratio"] = rz
		r = EMAN2_cppwrap.Reconstructors.get("nn4_ctf_rect", params)
	r.setup()

	if type(stack_name) == bytes:
		for i in range(len(list_proj)):
			proj.read_image(stack_name, list_proj[i])
			if dopad: 
				proj = sparx_utilities.pad(proj, size, size, 1, "circumference")
			insert_slices(r, proj)
	else:
		for i in range(len(list_proj)):
			insert_slices(r, stack_name[list_proj[i]])
	dummy = r.finish(True)
	return fftvol


def recons3d_4nn_ctf_MPI(myid, prjlist, snr = 1.0, sign=1, symmetry="c1", finfo=None, npad=2, xysize=-1, zsize=-1, mpi_comm=None, smearstep = 0.0):
	"""
		recons3d_4nn_ctf - calculate CTF-corrected 3-D reconstruction from a set of projections using three Eulerian angles, two shifts, and CTF settings for each projeciton image
		Input
			stack: name of the stack file containing projection data, projections have to be squares
			list_proj: list of projections to be included in the reconstruction or image iterator
			snr: Signal-to-Noise Ratio of the data 
			sign: sign of the CTF 
			symmetry: point-group symmetry to be enforced, each projection will enter the reconstruction in all symmetry-related directions.
	"""
	pass#IMPORTIMPORTIMPORT from utilities  import reduce_EMData_to_root, pad
	pass#IMPORTIMPORTIMPORT from EMAN2      import Reconstructors
	pass#IMPORTIMPORTIMPORT from utilities  import iterImagesList, set_params_proj
	pass#IMPORTIMPORTIMPORT from mpi        import MPI_COMM_WORLD
	pass#IMPORTIMPORTIMPORT import types

	if mpi_comm == None:
		mpi_comm = mpi.MPI_COMM_WORLD

	if type(prjlist) == list:
		prjlist = sparx_utilities.iterImagesList(prjlist)
	if not prjlist.goToNext():
		sparx_global_def.ERROR("empty input list","recons3d_4nn_ctf_MPI",1)
	imgsize = prjlist.image().get_xsize()
	if prjlist.image().get_ysize() != imgsize:
		imgsize = max(imgsize, prjlist.image().get_ysize())
		dopad = True
	else:
		dopad = False
	prjlist.goToPrev()

	fftvol = EMAN2_cppwrap.EMData()

	if( smearstep > 0.0 ):
		#if myid == 0:  print "  Setting smear in prepare_recons_ctf"
		ns = 1
		smear = []
		for j in range(-ns,ns+1):
			if( j != 0):
				for i in range(-ns,ns+1):
					for k in range(-ns,ns+1):
						smear += [i*smearstep,j*smearstep,k*smearstep,1.0]
		# Deal with theta = 0.0 cases
		prj = []
		for i in range(-ns,ns+1):
			for k in range(-ns,ns+1):
				prj.append(i+k)
		for i in range(-2*ns,2*ns+1,1):
			smear += [i*smearstep,0.0,0.0,float(prj.count(i))]
		#if myid == 0:  print "  Smear  ",smear
		fftvol.set_attr("smear", smear)

	weight = EMAN2_cppwrap.EMData()
	if (xysize == -1 and zsize == -1 ):
		params = {"size":imgsize, "npad":npad, "snr":snr, "sign":sign, "symmetry":symmetry, "fftvol":fftvol, "weight":weight}
		r = EMAN2_cppwrap.Reconstructors.get( "nn4_ctf", params )
	else:
		if ( xysize != -1 and zsize != -1):
			rx = float(xysize)/imgsize
			ry = float(xysize)/imgsize
			rz = float(zsize)/imgsize
		elif( xysize != -1):
			rx = float(xysize)/imgsize
			ry = float(xysize)/imgsize
			rz = 1.0
		else:
			rx = 1.0
			ry = 1.0
			rz = float(zsize)/imgsize
		#  There is an error here with sizeprojection  PAP 10/22/2014
		params = {"size":sizeprojection, "npad":npad, "snr":snr, "sign":sign, "symmetry":symmetry, "fftvol":fftvol, "weight":weight,"xratio":rx,"yratio":ry,"zratio":rz}
		r = EMAN2_cppwrap.Reconstructors.get( "nn4_ctf_rect", params )
	r.setup()

	#if not (finfo is None):
	nimg = 0
	while prjlist.goToNext():
		prj = prjlist.image()
		if dopad:
			prj = sparx_utilities.pad(prj, imgsize, imgsize, 1, "circumference")
		#if params:
		insert_slices(r, prj)
		if not (finfo is None):
			nimg += 1
			finfo.write(" %4d inserted\n" %(nimg) )
			finfo.flush()
	del utilities.pad
	if not (finfo is None): 
		finfo.write( "begin reduce\n" )
		finfo.flush()

	sparx_utilities.reduce_EMData_to_root(fftvol, myid, comm=mpi_comm)
	sparx_utilities.reduce_EMData_to_root(weight, myid, comm=mpi_comm)

	if not (finfo is None): 
		finfo.write( "after reduce\n" )
		finfo.flush()

	if myid == 0 :
		dummy = r.finish(True)
	else:
		pass#IMPORTIMPORTIMPORT from utilities import model_blank
		if ( xysize == -1 and zsize == -1 ):
			fftvol = sparx_utilities.model_blank(imgsize, imgsize, imgsize)
		else:
			if zsize == -1:
				fftvol = sparx_utilities.model_blank(xysize, xysize, imgsize)
			elif xysize == -1:
				fftvol = sparx_utilities.model_blank(imgsize, imgsize, zsize)
			else:
				fftvol = sparx_utilities.model_blank(xysize, xysize, zsize)
	return fftvol


