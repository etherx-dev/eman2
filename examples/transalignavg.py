#!/bin/env python

#
# Author: Steven Ludtke, 04/10/2003 (sludtke@bcm.edu)
# Copyright (c) 2000-2006 Baylor College of Medicine
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  2111-1307 USA
#
#

# transalignavg 12/02/2005  Steven Ludtke
# This will read a series of images, translationally align them, average them
# together, and optionally iterate. Translational alignment only.
# transalignavg.py <infile> <dot threshold> <iterations> <background> <gamma>

from EMAN2 import *
import sys
from math import *


n=EMUtil.get_image_count(sys.argv[1])
thr=float(sys.argv[2])

if len(sys.argv)>3: iter=int(sys.argv[3])
else: iter=1

if len(sys.argv)>4 :
	darkref=EMData()
	darkref.read_image(sys.argv[4],0)
else: darkref=None

if len(sys.argv)>5 : gamma=float(sys.argv[5])
else : gamma=0

# Pass 1, sequential alignment to average
avg=EMData()
avg.read_image(sys.argv[1],0)
darkref.process_inplace("eman1.normalize.toimage",{"noisy":avg})
avg-=darkref
avg-=avg.get_edge_mean()
#if gamma : avg.process_inplace("math.pow",{"pow":gamma})
sum=1
for i in range(1,n):
	a=EMData()
	a.read_image(sys.argv[1],i)
	darkref.process_inplace("eman1.normalize.toimage",{"noisy":a})
	a-=darkref
	a-=a.get_edge_mean()
#	if gamma : a.process_inplace("math.pow",{"pow":gamma})
	b=a.align("translational",avg,{})
	dot=b.cmp("dot",avg,{"negative":0,"normalize":1})
	print "%4d. %3d\t%3d\t%1.4f"%(i,b.get_attr("translational.dx"),b.get_attr("translational.dy"),dot)
	if dot>thr : 
		avg+=b
		sum+=1
	
print "%d/%d used"%(sum,n)
avg-=avg.get_attr("minimum")
avg/=avg.get_attr("maximum")
avg.process_inplace("math.pow",{"pow":gamma})
avg.write_image("avg.mrc")
display(avg)

