"""1
	fl, aa = fit_tanh(ref_data[3])
	msg = "Tangent filter:  cut-off frequency = %10.3f        fall-off = %10.3f\n"%(fl, aa)
	print_msg(msg)
	tavg = filt_tanl(ref_data[2], fl, aa)
	"""	
'''2
	pass#IMPORTIMPORTIMPORT from math import exp
	nx = tavg.get_xsize()
	ft = []
	good = True
	for i in xrange(nx):
		if(good):
			ex = exp((float(i)/float(nx))**2/2.0/0.12**2)
			if(ex>100.): good = False
		ft.append(ex)
	pass#IMPORTIMPORTIMPORT from filter import filt_table
	tavg = filt_table(tavg, ft)
	'''
"""3
	if(ref_data[1] == 1):
		cs    = volf.phase_cog()
		msg = "Center x = %10.3f        Center y = %10.3f        Center z = %10.3f\n"%(cs[0], cs[1], cs[2])
		print_msg(msg)
		volf  = fshift(volf, -cs[0], -cs[1], -cs[2])
	"""
"""4
		if myid == 0:
			#from utilities import write_text_file
			#write_text_file(rops_table(vol,1),"goo.txt")
			stat = Util.infomask(vol, mask3D, False)
			vol -= stat[0]
			Util.mul_scalar(vol, 1.0/stat[1])
			vol = threshold(vol)
			vol = filt_btwl(vol, 0.38, 0.5)#  This will have to be corrected.
			Util.mul_img(vol, mask3D)
			del mask3D
			# vol.write_image('toto%03d.hdf'%iter)
		"""
