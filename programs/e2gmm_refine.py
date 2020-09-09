#!/usr/bin/env python
# Muyuan Chen 2020-06
from EMAN2 import *
import numpy as np
from sklearn.decomposition import PCA
floattype=np.float32
os.environ["CUDA_VISIBLE_DEVICES"]='0' 
os.environ["TF_FORCE_GPU_ALLOW_GROWTH"]='true' 
import tensorflow as tf

#### Symmetrize the Gaussian coordinates. Only works for c/d sym right now
def get_sym_pts(sym, pts):
	if sym=="c1":
		return [tf.transpose(pts[:,:3])]
	nsym=Transform.get_nsym(sym)
	asym=[]
	if sym.startswith('d'):
		for i in range(nsym//2):
			a=np.pi*4/nsym*i
			asym.append(
				[pts[:,0]*np.cos(a)-pts[:,1]*np.sin(a),
				 pts[:,0]*np.sin(a)+pts[:,1]*np.cos(a),
				 pts[:,2]])
			asym.append(
				[pts[:,0]*np.cos(a)-pts[:,1]*np.sin(a),
				 -(pts[:,0]*np.sin(a)+pts[:,1]*np.cos(a)),
				 -pts[:,2]])
			

	if sym.startswith('c'):
		asym=[]
		for i in range(nsym):
			a=np.pi*2/nsym*i
			asym.append(
				[pts[:,0]*np.cos(a)-pts[:,1]*np.sin(a),
				 pts[:,0]*np.sin(a)+pts[:,1]*np.cos(a),
				 pts[:,2]])
			
	return asym

#### rotate-translate Gaussian coordinates based on transforms
@tf.function
def xf2pts(pts, ang):

	azp=-ang[:,0]
	altp=ang[:,1]
	phip=-ang[:,2]

	matrix=tf.stack([(tf.cos(phip)*tf.cos(azp) - tf.cos(altp)*tf.sin(azp)*tf.sin(phip)),
	(tf.cos(phip)*tf.sin(azp) + tf.cos(altp)*tf.cos(azp)*tf.sin(phip)),
	(tf.sin(altp)*tf.sin(phip)),

	(-tf.sin(phip)*tf.cos(azp) - tf.cos(altp)*tf.sin(azp)*tf.cos(phip)),
	(-tf.sin(phip)*tf.sin(azp) + tf.cos(altp)*tf.cos(azp)*tf.cos(phip)),
	(tf.sin(altp)*tf.cos(phip)),

	(tf.sin(altp)*tf.sin(azp)),
	(-tf.sin(altp)*tf.cos(azp)),
	tf.cos(altp)], 0)

	matrix=tf.transpose(matrix)
	matrix=tf.reshape(matrix, shape=[-1, 3,3]) #### Here we get a batch_size x 3 x 3 matrix

	#### transform Gaussian positions
	if len(pts.shape)>2:
		pts_rot=tf.tensordot(pts, matrix, [[2],[2]])
		pts_rot=tf.transpose(pts_rot, (0,2,1,3))#, (-1, pts.shape[1],3))
		e=tf.eye(pts.shape[0], dtype=bool)#.flatten()
		pts_rot=pts_rot[e]
		
	else:
		pts_rot=tf.tensordot(pts, matrix, [[1],[2]])
		pts_rot=tf.transpose(pts_rot, [1,0,2])
		
	
	tx=ang[:,3][:,None]
	ty=ang[:,4][:,None]
	pts_rot_trans=tf.stack([(pts_rot[:,:,0]+tx), (-pts_rot[:,:,1])+ty], 2)
	
	pts_rot_trans=pts_rot_trans*sz+sz/2
	return pts_rot_trans


#### make 2D projections in Fourier space
@tf.function
def pts2img(pts, ang, lp=.1, sym="c1"):
	bsz=ang.shape[0]
	
	imgs_real=tf.zeros((bsz, sz,sz//2+1), dtype=floattype)
	imgs_imag=tf.zeros((bsz, sz,sz//2+1), dtype=floattype)
	if len(pts.shape)>2 and pts.shape[0]>1:
		ni=pts.shape[1]
		pts=tf.reshape(pts, (-1, pts.shape[-1]))
		bamp=tf.reshape(pts[:, 3], (bsz,-1))
		bsigma=tf.reshape(pts[:, 4], (bsz,-1))
		multmodel=True
		
	else:
		bamp=pts[:, 3][None, :]
		bsigma=pts[:, 4][None, :]
		multmodel=False
		
	p0=get_sym_pts(sym, pts)
	for p in p0:
		p=tf.transpose(p)
		if multmodel:
			p=tf.reshape(p, (bsz, ni, -1))

		bpos=xf2pts(p,ang)
		bposft=bpos*np.pi*2
		bposft=bposft[:, :, :, None, None]

		cpxang=idxft[0]*bposft[:,:,0] + idxft[1]*bposft[:,:,1]
		bamp0=tf.nn.relu(bamp[:, :,None, None])
		bsigma0=tf.nn.relu(bsigma[:,:,None, None])
		
		amp=tf.exp(-rrft*lp*bsigma0)*bamp0
		pgauss_real=tf.cos(cpxang)*amp
		pgauss_imag=-tf.sin(cpxang)*amp

		imgs_real+=tf.reduce_sum(pgauss_real, axis=1)
		imgs_imag+=tf.reduce_sum(pgauss_imag, axis=1)

	return (imgs_real, imgs_imag)

#### compute particle-projection FRC 
@tf.function
def calc_frc(data_cpx, imgs_cpx, return_curve=False):
	mreal, mimag=imgs_cpx
	dreal, dimag=data_cpx
	#### normalization per ring
	nrm_img=mreal**2+mimag**2
	nrm_data=dreal**2+dimag**2

	nrm0=tf.tensordot(nrm_img, rings, [[1,2],[0,1]])
	nrm1=tf.tensordot(nrm_data, rings, [[1,2],[0,1]])
	
	nrm=tf.sqrt(nrm0)*tf.sqrt(nrm1)
	nrm=tf.maximum(nrm, 1e-4) #### so we do not divide by 0
		
	#### average FRC per batch
	ccc=mreal*dreal+mimag*dimag
	frc=tf.tensordot(ccc, rings, [[1,2],[0,1]])/nrm
	
	if return_curve:
		return frc
	else:
		frcval=tf.reduce_mean(frc[:, 4:], axis=1)
		return frcval
	
#### load particles from file and fourier transform them
#### particles need to have their transform in file header or comment of list file
def load_particles(fname, shuffle=False, hdrxf=False):
	projs=[]
	n=EMUtil.get_image_count(fname)
	e=EMData(fname, 0, True)
	nx=e["nx"]
	bx=nx
	for i in range(n):
		e=EMData(fname, i)
		e.clip_inplace(Region((nx-bx)//2,(nx-bx)//2, bx,bx))
		projs.append(e)
		
	#projs=EMData.read_images(fname)#[:200]
	if shuffle:
		rnd=np.arange(len(projs))
		np.random.shuffle(rnd)
		projs=[projs[i] for i in rnd]

	hdrs=[p.get_attr_dict() for p in projs]
	projs=np.array([p.numpy().copy() for p in projs], dtype=floattype)/1e3
	data_cpx=np.fft.rfft2(projs)
	data_cpx=(data_cpx.real.astype(floattype), data_cpx.imag.astype(floattype))	
	
	if hdrxf:
		if fname.endswith(".lst"):
			lst=LSXFile(fname, True)
			xfs=[]
			for i in range(len(projs)):
				l=lst.read(i)
				xfs.append(eval(l[2]))
			if shuffle:
				xfs=[xfs[i] for i in rnd]
		else:
			xfs=[p["xform.projection"].get_params("eman") for p in hdrs]
		xfsnp=np.array([[x["az"],x["alt"],x["phi"], x["tx"], x["ty"]] for x in xfs], dtype=floattype)
		xfsnp[:,:3]=xfsnp[:,:3]*np.pi/180.
		xfsnp[:,3:]/=projs.shape[-1]
		print(projs.shape)
		
		return data_cpx,xfsnp
	else:
		return data_cpx
	
#### do fourier clipping in numpy than export to tf to save memory...
def get_clip(datacpx, newsz):
	if (datacpx[0].shape[1])<=newsz:
		return datacpx
	s=newsz//2
	dc=[d[:,clipid[1]<s,:] for d in datacpx]
	dc=[d[:,:,clipid[0]<s+1] for d in dc]
	return [tf.constant(d) for d in dc]

#### compute fourier indices for image generation, clipping, and frc
#### use some global varibles to avoid passing them around too often...
def set_indices_boxsz(boxsz, apix=0, return_freq=False):
	idx=np.indices((boxsz,boxsz))-boxsz//2
	idx=np.fft.ifftshift(idx)
	idx=idx[:,:,:boxsz//2+1]
	
	if return_freq:
		global freq, clipid
		
		freq=np.fft.fftfreq(boxsz, apix)[:boxsz//2]
		ci=idx[0,0]
		cj=idx[1,:,0]
		cj[cj<0]+=1
		clipid=[abs(ci), abs(cj)]
		return freq, clipid
	
	else:
		global sz, idxft, rrft, rings
		sz=boxsz
		idxft=(idx/sz).astype(floattype)[:, None, :,:]
		rrft=np.sqrt(np.sum(idx**2, axis=0)).astype(floattype)## batch, npts, x-y

		rr=np.round(np.sqrt(np.sum(idx**2, axis=0))).astype(int)
		rings=np.zeros((sz,sz//2+1,sz//2), dtype=floattype) #### Fourier rings
		for i in range(sz//2):
			rings[:,:,i]=(rr==i)
		
		return idxft, rrft, rings

#### build decoder network. 
## input integer to initialize as zeros with N points
## input point list to initialize to match input
def build_decoder(pts, mid=512):
	if isinstance(pts, int):
		npt=pts
		initpts=False
		
	else:
		npt=len(pts)
		initpts=True
	
	x0=tf.keras.Input(shape=(1,2))
	
	kinit=tf.keras.initializers.RandomNormal(0,1e-2)
	layer_output=tf.keras.layers.Dense(npt*5, kernel_initializer=kinit, activation="sigmoid")
	
	layers=[
		tf.keras.layers.Dense(mid,activation="relu",
					bias_initializer=kinit),
		tf.keras.layers.Dense(mid,activation="relu"),
		tf.keras.layers.Dense(mid,activation="relu"),
		tf.keras.layers.Dense(mid,activation="relu"),
		tf.keras.layers.BatchNormalization(),
		layer_output,
		tf.keras.layers.Reshape((npt,5))
	]
	
	## the five columns are for x,y,z,amp,sigma
	## the range for x,y,z is [-.5, .5]
	## range for amp is [0,1], sigma is [.5, 1.5]
	bshift=np.array([-.5,-.5,-.5,0,.5]).astype(floattype)
	
	y0=x0
	for l in layers:
		y0=l(y0)
		
	y0=y0+tf.constant(bshift)
	gen_model=tf.keras.Model(x0, y0)
	
	## match the bias of the final layer to input
	## need to undo the sigmoid activation
	if initpts:
		bs=pts.copy()-bshift
		bs=np.clip(bs, 1e-6, 1-1e-6)
		bs=-np.log(1./bs-1)
		layer_output.bias.assign(bs.flatten())
	
	return gen_model

#### training decoder on projections

def train_decoder(gen_model, trainset, options):
	opt=tf.keras.optimizers.Adam(learning_rate=options.learnrate) 
	wts=gen_model.trainable_variables
	
	nbatch=0
	for t in trainset: nbatch+=1
	
	for itr in range(options.niter):
		cost=[]
		for pjr,pji,xf in trainset:
			if xf.shape[0]==1: continue
			pj_cpx=(pjr,pji)
			with tf.GradientTape() as gt:
				conf=tf.zeros((xf.shape[0],1,2), dtype=floattype)
				pout=gen_model(conf)
				std=tf.reduce_mean(tf.math.reduce_std(pout, axis=1), axis=0)
				imgs_cpx=pts2img(pout, xf)
				fval=calc_frc(pj_cpx, imgs_cpx)
				loss=-tf.reduce_mean(fval)
				l=loss+std[4]*options.sigmareg
			
			cost.append(loss)   
			grad=gt.gradient(l, wts)
			opt.apply_gradients(zip(grad, wts))
			
			sys.stdout.write("\r {}/{}\t{:.3f}     ".format(len(cost), nbatch, loss))
			sys.stdout.flush()
		sys.stdout.write("\r")
		
		print("iter {}, loss : {:.3f}      ".format(itr, np.mean(cost)))

def eval_model(gen_model, options):
	
	imgs=[]
	xfs=[]
	symmetry=Symmetries.get(options.sym)
	xfs=symmetry.gen_orientations("eman", {"delta":3})
	xfs=[x.get_params("eman") for x in xfs]
	
	xfsnp=np.array([[x["az"],x["alt"],x["phi"], x["tx"], x["ty"]] for x in xfs], dtype=floattype)
	xfsnp[:,:3]=xfsnp[:,:3]*np.pi/180.
	xfs=[]
	set_indices_boxsz(128)
	trainset=tf.data.Dataset.from_tensor_slices((xfsnp))
	trainset=trainset.batch(8)
	for xf in trainset:
		conf=tf.zeros((xf.shape[0],1,2), dtype=floattype)
		pout=gen_model(conf)
		imgs_real, imgs_imag=pts2img(pout, xf, sym=options.sym)
		imgs_cpx=tf.complex(imgs_real, imgs_imag)
		imgs_out=tf.signal.irfft2d(imgs_cpx)
		imgs.append(imgs_out)
		xfs.append(xf.numpy())
		
	imgs=tf.concat(imgs, axis=0).numpy()
	xfs=np.concatenate(xfs, axis=0)
	print(imgs.shape)
	print(xfs.shape)
	xfs[:,:3]=xfs[:,:3]*180./np.pi
	xfs[:,3:]*=imgs.shape[-1]
	if os.path.isfile(options.evalmodel):
		os.remove(options.evalmodel)
	for m,x in zip(imgs, xfs):
		e=from_numpy(m)
		x=x.tolist()
		xf=Transform({"type":"eman", "az":x[0], "alt":x[1], "phi":x[2], "tx":x[3], "ty":x[4]})
		e["xform.projection"]=xf
		e["apix_x"]=e["apix_y"]=options.raw_apix
		e.write_image(options.evalmodel,-1)
		
	
def ccf_trans(ref,img):
	ref_real, ref_imag = ref
	img_real, img_imag = img
	ccfr=(img_real*ref_real+img_imag*ref_imag)
	ccfi=(img_real*ref_imag-img_imag*ref_real)
	ccf=tf.complex(ccfr, ccfi)
	ccf=tf.signal.ifftshift(tf.signal.irfft2d(ccf))
	s=ccf.shape[1]//4
	ccf=ccf[:, s:-s, s:-s]
	tx=tf.argmax(tf.math.reduce_max(ccf, axis=1), axis=1)
	ty=tf.argmax(tf.math.reduce_max(ccf, axis=2), axis=1)
	trans=tf.cast(tf.stack([tx, ty], axis=1), floattype)-ccf.shape[1]/2
	return -trans

def translate_image(img, trans):
	imgs_real, imgs_imag=img
	s=idxft[0]*trans[:,0,None,None]+idxft[1]*trans[:,1,None,None]
	s*=-2*np.pi
	imgs_real1=imgs_real*np.cos(s)-imgs_imag*np.sin(s)
	imgs_imag1=imgs_imag*np.cos(s)+imgs_real*np.sin(s)
	return(imgs_real1, imgs_imag1)

def coarse_align(dcpx, pts, options):
	print("coarse aligning particles")
	astep=7.5
	npt=len(dcpx[0])
	symmetry=Symmetries.get(options.sym)
	#xfs=symmetry.gen_orientations("rand", {"n":npt,"phitoo":1,"inc_mirror":1})
	
	
	xfs=symmetry.gen_orientations("eman", {"delta":astep,"phitoo":astep,"inc_mirror":1})
	xfs=[x.get_params("eman") for x in xfs]
	xfsnp=np.array([[x["az"],x["alt"],x["phi"],x["tx"], x["ty"]] for x in xfs], dtype=floattype)
	xfsnp[:,:3]=xfsnp[:,:3]*np.pi/180.
	#return [xfsnp]
	
	bsz=800
	allfrcs=np.zeros((npt, len(xfsnp)))
	alltrans=np.zeros((npt, len(xfsnp), 2))
	niter=len(xfsnp)//bsz
	for ii in range(niter):
		xx=xfsnp[ii*bsz:(ii+1)*bsz]
		projs_cpx=pts2img(pts, xx, sym=options.sym)
		
		for idt in range(npt):
			dc=list(tf.repeat(d[idt:idt+1], len(xx), axis=0) for d in dcpx)
			ts=ccf_trans(dc, projs_cpx)
			dtrans=translate_image(dc,ts)
			frcs=calc_frc(dtrans, projs_cpx)
			#mxxfs.append(np.argmax(frcs))
			allfrcs[idt,ii*bsz:(ii+1)*bsz]=frcs
			alltrans[idt,ii*bsz:(ii+1)*bsz]=ts

			sys.stdout.write("\r projs: {}/{}, data: {}/{}    ".format(ii+1, niter, idt+1, npt))
			sys.stdout.flush()
	xfs=[]
	for ii in range(1):
		fid=np.argmax(allfrcs, axis=1)
		xf=xfsnp[fid]
		ts=alltrans[np.arange(npt),fid]
		xf[:,3:]-=ts/sz
		xfs.append(xf)
		allfrcs[np.arange(npt),fid]=-1
	
	print()
	return xfs

def refine_align(dcpx, xfsnp, pts, options, lr=1e-3):
	nsample=dcpx[0].shape[0]
	trainset=tf.data.Dataset.from_tensor_slices((dcpx[0], dcpx[1], xfsnp))
	trainset=trainset.batch(options.batchsz)
	nbatch=nsample//options.batchsz
	
	opt=tf.keras.optimizers.Adam(learning_rate=lr) 
	xfvs=[]
	frcs=[]
	niter=options.niter
	scr=[]
	
	for ptr,ptj,xf in trainset:
		ptcl_cpx=(ptr, ptj)
		xfvar=tf.Variable(xf)
		p=tf.constant(tf.zeros((xf.shape[0],pts.shape[0], 5))+pts)
		cost=[]
		for itr in range(niter):
			with tf.GradientTape() as gt:
				#xv=tf.concat([xf[:,:3], xfvar[:,3:]], axis=1)
				xv=xfvar
				proj_cpx=pts2img(p, xv, sym=options.sym)
				fval=calc_frc(proj_cpx, ptcl_cpx)
				loss=-tf.reduce_mean(fval)

			grad=gt.gradient(loss, xfvar)
			opt.apply_gradients([(grad, xfvar)])
			cost.append(loss)

			sys.stdout.write("\r batch {}/{}, iter {}/{}, loss {:.3f}   ".format(len(xfvs), nbatch, itr+1, niter, loss))
			sys.stdout.flush()
			
		xfvs.append(xfvar.numpy())
		frcs.extend(fval.numpy().tolist())
		scr.append([cost[0],cost[-1]])
		
	print()
	xfsnp1=np.vstack(xfvs)
	print(np.mean(abs(xfsnp1-xfsnp), axis=0))
	#xfsnp1[:,:3]=xfsnp[:,:3]
	xfsnp=xfsnp1.copy()
	
	frcs=np.array(frcs)
	
	scr=np.mean(scr, axis=0)
	print("Done. average loss from {:.3f} to {:.3f}".format(scr[0], scr[1]))
	
	return xfsnp, frcs

def save_ptcls_xform(xfsnp, boxsz, options, scr):
	xnp=xfsnp.copy()
	xnp[:,:3]=xnp[:,:3]*180./np.pi
	xnp[:,3:]*=boxsz
	xfs=[Transform({"type":"eman", "az":x[0], "alt":x[1], 
				"phi":x[2], "tx":x[3], "ty":x[4]}) for x in xnp.tolist()]

	oname=options.ptclsout
	print("saving aligned particles to {}".format(oname))
	if os.path.isfile(oname): os.remove(oname)
	lst=LSXFile(oname, False)
	lst0=LSXFile(options.ptclsin, True)
	print(scr)
	for i,xf in enumerate(xfs):
		l0=lst0.read(i)
		d=xf.get_params("eman")
		d["score"]=-scr[i]
		lst.write(-1, l0[0], l0[1], str(d))

	lst=None
	lst0=None

def main():
	
	usage=""" 
	"""
	parser = EMArgumentParser(usage=usage,version=EMANVERSION)
	parser.add_argument("--sym", type=str,help="symmetry. currently only support c and d", default="c1")
	parser.add_argument("--model", type=str,help="load from an existing model file", default="")
	parser.add_argument("--modelout", type=str,help="output trained model file. only used when --projs is provided", default="")
	parser.add_argument("--projs", type=str,help="projections with orientations (in hdf header or comment column of lst file) to train model", default="")
	parser.add_argument("--evalmodel", type=str,help="generate model projection images", default="")
	parser.add_argument("--ptclsin", type=str,help="particles input for alignment", default="")
	#parser.add_argument("--fsc", type=str,help="fsc file input for weighting. does not seem to be very useful...", default="")
	parser.add_argument("--ptclsout", type=str,help="aligned particle output", default="")
	parser.add_argument("--learnrate", type=float,help="learning rate for model training only. ", default=1e-4)
	parser.add_argument("--sigmareg", type=float,help="regularizer for the std of gaussian width", default=.1)
	parser.add_argument("--niter", type=int,help="number of iterations", default=10)
	parser.add_argument("--npts", type=int,help="number of points to initialize. ", default=-1)
	parser.add_argument("--batchsz", type=int,help="batch size", default=32)
	parser.add_argument("--maxboxsz", type=int,help="maximum fourier box size to use. Idealy use pixels of the current resolution * 3 ", default=64)
	parser.add_argument("--double", action="store_true", default=False ,help="double the number of points.")
	parser.add_argument("--fromscratch", action="store_true", default=False ,help="start from coarse alignment. otherwise will only do refinement from last round")
	(options, args) = parser.parse_args()
	logid=E2init(sys.argv)
	

	maxboxsz=options.maxboxsz		
		
	if options.model:
		print("Recompute model from coordinates...")
		pts=np.loadtxt(options.model)
		#pts=pts[:1001]
		
		if options.double:
			pts=np.repeat(pts, 2, axis=0)
			pts[:,3]/=2
		
		if options.npts>len(pts):
			p=pts.copy()
			np.random.shuffle(p)
			p=p[:(options.npts-len(pts))]
			pts=np.concatenate([pts, p], axis=0)
	       
		## randomize it a bit so we dont have all zero weights
		rnd=np.random.randn(pts.shape[0], pts.shape[1])*1e-3
		gen_model=build_decoder(pts+rnd)
		print("{} gaussian in the model".format(len(pts)))
		conf=tf.zeros((1,1,2), dtype=floattype)
		opt=tf.keras.optimizers.Adam(learning_rate=1e-4) 
		gen_model.compile(optimizer=opt, loss=tf.losses.MeanAbsoluteError())
		loss=[]
		for i in range(500):
			loss.append(gen_model.train_on_batch(conf, pts))
			
		print("Abs loss from loaded model : {:.05f}".format(loss[-1]))
	else:
		gen_model=build_decoder(options.npts)
	
	if options.projs:
		print("Train model from ptcl-xfrom pairs...")
		e=EMData(options.projs, 0, True)
		raw_apix, raw_boxsz = e["apix_x"], e["ny"]
		options.raw_apix=raw_apix
		data_cpx, xfsnp = load_particles(options.projs, shuffle=True, hdrxf=True)
		set_indices_boxsz(data_cpx[0].shape[1], raw_apix, True)
		
		if options.niter>0:
			set_indices_boxsz(maxboxsz)
			dcpx=get_clip(data_cpx, sz)
			trainset=tf.data.Dataset.from_tensor_slices((dcpx[0], dcpx[1], xfsnp))
			trainset=trainset.batch(options.batchsz)
		
			train_decoder(gen_model, trainset, options)
			pout=gen_model(tf.zeros((1,1,2), dtype=floattype))
			np.savetxt(options.modelout, pout[0])
		
		if options.evalmodel:
			set_indices_boxsz(raw_boxsz)
			eval_model(gen_model, options)
		
		
	if options.ptclsin:
		print("Align particles...")
		e=EMData(options.ptclsin, 0, True)
		raw_apix, raw_boxsz = e["apix_x"], e["ny"]
		pts=gen_model(tf.zeros((1,1,2), dtype=floattype))[0]
		
		if options.fromscratch:
			data_cpx = load_particles(options.ptclsin, shuffle=False, hdrxf=False)
			set_indices_boxsz(data_cpx[0].shape[1], raw_apix, True)
			set_indices_boxsz(32)
			dcpx=get_clip(data_cpx, sz)
			xfs=coarse_align(dcpx, pts, options)
			
			xfsnp=np.zeros((data_cpx[0].shape[0], 5), dtype=floattype)
			frcs=np.zeros(data_cpx[0].shape[0], dtype=floattype)
			for xf in xfs:
				set_indices_boxsz(32)
				dcpx=get_clip(data_cpx, sz)
				xo, fc=refine_align(dcpx, xf, pts, options, lr=1e-2)
				fid=fc>frcs
				xfsnp[fid]=xo[fid]
				frcs[fid]=fc[fid]
			
			set_indices_boxsz(64)
			dcpx=get_clip(data_cpx, sz)
			xfsnp, frcs=refine_align(dcpx, xfsnp, pts, options)
			
		else:
			data_cpx, xfsnp = load_particles(options.ptclsin, shuffle=False, hdrxf=True)
			set_indices_boxsz(data_cpx[0].shape[1], raw_apix, True)
			
		set_indices_boxsz(maxboxsz)
		dcpx=get_clip(data_cpx, sz)
		xfsnp, frcs=refine_align(dcpx, xfsnp, pts, options, lr=1e-4)
			
		save_ptcls_xform(xfsnp, raw_boxsz, options, frcs)

	
	#conf=tf.zeros((1,1,2), dtype=floattype)
	#pout=gen_model(conf)[0]
	#np.savetxt("gmm_02/gauss_model_00.txt", pout)

	E2end(logid)
	
def run(cmd):
	print(cmd)
	launch_childprocess(cmd)
	
	
if __name__ == '__main__':
	main()
	