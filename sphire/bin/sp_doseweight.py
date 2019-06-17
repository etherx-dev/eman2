from __future__ import print_function
import os
import glob
import matplotlib.pyplot as plt
from matplotlib import cm
import numpy as np
import scipy as sp
import cPickle as pickle
from EMAN2 import *
import EMAN2_cppwrap
from EMAN2 import EMNumPy

import sp_utilities
import sp_projection
import sp_statistics
import sp_filter
import mpi
import sp_applications
import sp_fundamentals

from scipy.optimize import curve_fit
from scipy import fftpack
from scipy import interpolate

location =os.getcwd()
RUNNING_UNDER_MPI = "OMPI_COMM_WORLD_SIZE" in os.environ


no_of_micrographs = 112
main_mpi_proc = 0
if RUNNING_UNDER_MPI:
    pass  # IMPORTIMPORTIMPORT from mpi import mpi_init
    pass  # IMPORTIMPORTIMPORT from mpi import MPI_COMM_WORLD, mpi_comm_rank, mpi_comm_size, mpi_barrier, mpi_reduce, MPI_INT, MPI_SUM

    mpi.mpi_init(0, [])
    my_mpi_proc_id = mpi.mpi_comm_rank(mpi.MPI_COMM_WORLD)
    n_mpi_procs = mpi.mpi_comm_size(mpi.MPI_COMM_WORLD)
else:
    my_mpi_proc_id = 0
    n_mpi_procs = 1


ima_start , ima_end = sp_applications.MPI_start_end(no_of_micrographs, n_mpi_procs, my_mpi_proc_id)

print(ima_start, ima_end)


def numpy2em_python(numpy_array, out=None):
    """
	Create an EMData object based on a numpy array by reference.
	The output EMData object will have the reversed order of dimensions.
	x,y,z -> z,y,x
	Arguments:
	numpy_array - Array to convert
	Return:
	EMData object
	"""
    if out is None:
        shape = numpy_array.shape[::-1]
        if len(shape) == 1:
            shape = (shape[0], 1)
        return_array = EMData(*shape)
    else:
        return_array = out
	return_view = EMNumPy.em2numpy(return_array)
	return_view[...] = numpy_array
	return_array.update()
    if out is None:
        return return_array

def return_movie_names(input_image_path):
    mic_pattern = input_image_path
    mic_basename_pattern = os.path.basename(mic_pattern)
    global_entry_dict = {}
    subkey_input_mic_path = "Input Micrograph Path"

    mic_basename_tokens = mic_basename_pattern.split('*')
    mic_id_substr_head_idx = len(mic_basename_tokens[0])

    input_mic_path_list = glob.glob(mic_pattern)

    for input_mic_path in input_mic_path_list:
        # Find tail index of  id substring and extract the substring from the  name
        input_mic_basename = os.path.basename(input_mic_path)
        mic_id_substr_tail_idx = input_mic_basename.index(mic_basename_tokens[1])
        mic_id_substr = input_mic_basename[mic_id_substr_head_idx:mic_id_substr_tail_idx]
        if not mic_id_substr in global_entry_dict:
            global_entry_dict[mic_id_substr] = {}
        global_entry_dict[mic_id_substr][subkey_input_mic_path] = input_mic_path

    print(" ")
    print("\n Summary of dataset consistency check...")
    print(("  Detected  IDs               : %6d" % (len(global_entry_dict))))
    print(("  Entries in input directory  : %6d" % (len(input_mic_path_list))))


    valid_mic_id_substr_list = []
    for mic_id_substr in global_entry_dict:
        mic_id_entry = global_entry_dict[mic_id_substr]
        valid_mic_id_substr_list.append(mic_id_substr)

    input_file_path_list = []
    for mic_id_substr in sorted(valid_mic_id_substr_list):
        mic_path = global_entry_dict[mic_id_substr][subkey_input_mic_path]
        input_file_path_list.append(mic_path)

    print(("Found %d micrographs in %s." % (len(input_mic_path_list), os.path.dirname(mic_pattern))))
    return input_file_path_list


def return_images_from_movie(movie_name, show_first = False):
    mov_imgs = EMAN2_cppwrap.EMData.read_images(movie_name)
    if show_first:
        plt.ion()
        plt.figure()
        plt.imshow(mov_imgs[0].get_3dview()[0], cmap=plt.get_cmap('Greys'))
        plt.colorbar()
        plt.show()
    print("\n No of images in the selected movie %s are %d" % (os.path.basename(movie_name) ,len(mov_imgs[0].get_3dview())))
    print("Shape of the Movie i.e. dimension of the frames and no of frames", np.shape(mov_imgs[0].get_3dview()))
    print("No of images in the movie",mov_imgs[0].get_zsize() )
    print("X dimension of image in the movie", mov_imgs[0].get_xsize())
    print("X dimension of image in the movie", mov_imgs[0].get_ysize())
    return mov_imgs[0]



"""
Reads the x and y values per frame in a micrograph  
"""
def returns_values_in_file(f, mode = 'r'):
    """
    read a file and returns all its lines
    :param f: path to file
    :param mode: how open the file. Default: read file
    :return: contained values
    """
    if os.path.isfile(f):
        with open(f, mode) as f1:
            values_f1 = f1.readlines()
        return values_f1
    print ("ERROR> the given file '"+str(f)+"' is not present!")
    exit(-1)


def read_meta_shifts(f):
    x = []
    y  = []
    for row in returns_values_in_file(f):
        if "image #" in row:
            v=row.replace('\n','').split('=')[1].replace(' ', '').split(',')
            x.append(float(v[0]))
            y.append(float(v[1]))
    return x,y



"""
Reading a particle stack to find all the parameters saved in the header file
"""

def read_all_attributes_from_stack(stack):
    no_of_imgs_once = EMUtil.get_image_count(stack)  # Counting how many are there in the stack
    # -------Extracting the information from the substack
    ptcl_source_images_once = EMUtil.get_all_attributes(stack, 'ptcl_source_image')
    project_params_all_once = EMUtil.get_all_attributes(stack, "xform.projection")
    particle_coordinates_all_once = EMUtil.get_all_attributes(stack, "ptcl_source_coord")
    ctf_params_all_once = EMUtil.get_all_attributes(stack, "ctf")


    nx_all_once = EMUtil.get_all_attributes(stack, 'nx')
    ny_all_once = EMUtil.get_all_attributes(stack, 'ny')
    nz_all_once = EMUtil.get_all_attributes(stack, 'nz')

    return no_of_imgs_once, ptcl_source_images_once, project_params_all_once, particle_coordinates_all_once, ctf_params_all_once, nx_all_once, ny_all_once, nz_all_once


def find_particles_info_from_movie(stack, movie_name, no_of_imgs, ptcl_source_images, project_params_all, particle_coordinates_all, ctf_params_all, nx_all, ny_all, nz_all, source_n_all, show_first = False):

    #-----------------------------------------------   CTF related attributes
    """
    defocus = defocus associated with the image, positive value corresponds to underfocus
    cs =  spherical aberration constant [mm].
    voltage = accelerating voltage of the microscope [kV]
    apix =
    bfactor = The parameter in Gaussian like envelope function, which roughly explains Fourier factor dumping of the image.
    ampcont = amplitude contrast
    dfdiff  = astigmatism amplitude
    dfang =  astigmatism angle
    """

    # -------------------------------------------  2D orientation / orientation attributes
    """
    phi =  Eulerian angle for 3D reconstruction (azimuthal) 
    theta = Eulerian angle for 3D reconstruction (tilt) 
    psi = Eulerian angle for 3D reconstruction (in-plane rotation of projection) 
    tx =  shift in x direction
    ty = shift in y direction
    """
    print("Number of images in the substack are %d" % len(ptcl_source_images))

    project_params_per_movie = []
    particle_coordinates_per_movie = []
    ctf_params_per_movie = []
    nx_per_movie = []
    ny_per_movie = []
    nz_per_movie = []
    source_n_per_movie = []

    for i in range(no_of_imgs):
        if (
                str(os.path.basename(movie_name)) == str(os.path.basename(ptcl_source_images[i])) or
                str(os.path.basename(movie_name)) == str(os.path.basename(ptcl_source_images[i]))+'s'
                ):
            project_params_per_movie.append(project_params_all[i])
            particle_coordinates_per_movie.append(particle_coordinates_all[i])
            ctf_params_per_movie.append(ctf_params_all[i])
            nx_per_movie.append(nx_all[i])
            ny_per_movie.append(ny_all[i])
            nz_per_movie.append(nz_all[i])
            source_n_per_movie.append(source_n_all[i])

    print("Number of particles detected in %s are %d" % (str(os.path.basename(movie_name)), len(project_params_per_movie)))
    print("Ctf estimation parameters for 1st particle in the stack are ", ctf_params_per_movie[0].to_dict())
    print("Projection parameters for 1st particle in the stack are ", project_params_per_movie[0].get_params('spider'))
    print("Dimensions x for all particles are ", nx_per_movie)
    print("Dimensions y for all particles are ", ny_per_movie)
    print("Dimensions z for all particles are ", nz_per_movie)


    if show_first:
        ima = EMAN2_cppwrap.EMData()
        ima.read_image(stack, 0, False)
        plt.ion()
        plt.figure()
        plt.imshow(ima.get_2dview(), cmap=plt.get_cmap('Greys'))
        plt.colorbar()
        plt.show()

    return project_params_per_movie, particle_coordinates_per_movie, ctf_params_per_movie, nx_per_movie, ny_per_movie, nz_per_movie, source_n_per_movie

"""
Reading a reference map
"""
def get_2D_project_for_all_ptcl_from_reference(volume_ft , project_params_in_stack, show = False):
    project_2D_per_movie = []
    for i in range(len(project_params_in_stack)):
        params_substack = project_params_in_stack[i].get_params('spider')
        params_for_each_image = [params_substack['phi'], params_substack['theta'], params_substack['psi'],
                                 params_substack['tx'], params_substack['ty']]
        project_2D_per_movie.append(sp_projection.prgl(volume_ft, params_for_each_image, interpolation_method=1))
    if show:
        plt.ion()
        plt.figure()
        plt.imshow(project_2D_per_movie[0].get_2dview(), cmap = plt.get_cmap('Greys'))
        plt.colorbar()
        plt.show()
    return project_2D_per_movie


"""
Extracting particle image from the movie data. First getting the particle cordinates from the dictionary and then 
creating a window around to extract the same particle from each frame
"""
#----------------------- Particle cordinate
def get_all_reduce_ptcl_imgs(frames_i, maski, nxx, nyy, part_cord, ctf_para, cen_xx, cen_yy, cen_zz, no_invert=True):
    particle_imgs_in_movie = []
    for j in range(len(part_cord)):
        crop_imgs = []
        for i in range(2*cen_zz):
            box_img = Util.window(frames_i, nxx, nyy, 1, part_cord[j][0] - cen_xx,
                                         part_cord[j][1] - cen_yy , i - cen_zz)

            crop_imgs.append(box_img)
            del box_img

        particle_imgs_in_movie.append(crop_imgs)
        del crop_imgs

    return particle_imgs_in_movie


def get_all_reduce_ptcl_imgs_modified(movie_name, nxx, nyy, part_cord,
                                      b_list_i, c_list_i, mask_applied, sum_k,zsize):

    """Getting dimension information"""
    current_frame = EMData()
    current_frame.read_image(movie_name, 0)
    xsize = current_frame.get_xsize()
    ysize = current_frame.get_ysize()


    cen_xx = xsize // 2
    cen_yy = ysize // 2
    cen_zz = zsize // 2

    particle_imgs_in_movie = []

    for i in range(zsize):
        current_frame.read_image(movie_name, i)
        shift_frame = sp_fundamentals.fshift(current_frame, shift_x[i], shift_y[i])
        weights_mask = get_weight_values([b_list_i[i]], [c_list_i[i]], mask_applied)
        np.divide(weights_mask, sum_k, out=weights_mask)

        """Apply Fourier Transform"""
        four_img = np.fft.fft2(shift_frame.get_2dview())
        four_img2 = np.fft.fftshift(four_img)
        np.multiply(four_img2, weights_mask[0], out=four_img2)
        doseweight_framesi = np.fft.ifftshift(four_img2)
        doseweight_framesi = np.fft.ifft2( doseweight_framesi ).real

        numpy2em_python(doseweight_framesi, out=shift_frame)

        del four_img
        del four_img2
        del doseweight_framesi

        crop_imgs = []
        for j in range(len(part_cord)):
            box_img = Util.window(shift_frame, nxx, nyy, 1, part_cord[j][0] - cen_xx,
                                             part_cord[j][1] - cen_yy , 0 ) #i - cen_zz
            crop_imgs.append(box_img)
            del box_img

        particle_imgs_in_movie.append(crop_imgs)
        del crop_imgs
        del shift_frame

    return particle_imgs_in_movie



def get_fscs_all_particles(frames_i, refer,  nxx, nyy, part_cord, cen_xx, cen_yy, cen_zz):
    fsc_vali = []
    fsc_freqi = []
    for j in range(len(part_cord)):
        fsc_frames_vali = []
        fsc_frames_freqi = []
        for i in range(2*cen_zz):
            ptcl = Util.window(frames_i, nxx, nyy, 1, part_cord[j][0] - cen_xx,
                                         part_cord[j][1] - cen_yy , i - cen_zz)

            fsc_frames_vali.append(sp_statistics.fsc(ptcl, refer[j])[1])
            fsc_frames_freqi.append(sp_statistics.fsc(ptcl, refer[j])[0])

        fsc_vali.append(fsc_frames_vali)
        fsc_freqi.append(fsc_frames_freqi)

    return fsc_vali, fsc_freqi

def get_fscs_all_particles_modified(movie_name, refer, nxx, nyy, part_cord, zsize):
    # if no_invert == True:
    fsc_vali = []
    fsc_freqi = []
    current_frame = EMData()
    current_frame.read_image(movie_name, 0)
    xsize = current_frame.get_xsize()
    ysize = current_frame.get_ysize()


    cen_xx = xsize // 2
    cen_yy = ysize // 2
    cen_zz = zsize // 2

    for i in range(zsize):
        current_frame.read_image(movie_name,i)
        shift_frame = sp_fundamentals.fshift(current_frame, shift_x[i], shift_y[i])
        fsc_frames_vali = []
        fsc_frames_freqi = []
        for j in range(len(part_cord)):

            ptcl = Util.window(shift_frame, nxx, nyy, 1, part_cord[j][0] - cen_xx,
                                         part_cord[j][1] - cen_yy ,0)

            fsc_frames_vali.append(sp_statistics.fsc(ptcl, refer[j])[1])
            fsc_frames_freqi.append(sp_statistics.fsc(ptcl, refer[j])[0])

        fsc_vali.append(fsc_frames_vali)
        fsc_freqi.append(fsc_frames_freqi)

    return fsc_vali, fsc_freqi


def moving_avg_filter(fsc_curve):
    for i in range(2, len(fsc_curve) -3 ) :
        fsc_curve[i] = (fsc_curve[i] + fsc_curve[i-1] + fsc_curve[i-2] + fsc_curve[i+1] + fsc_curve[i+2])/5
    return fsc_curve

def smooth(x,window_len):
    import numpy as np
    w = np.ones(window_len, 'd')
    y = np.convolve(w / w.sum(), x, mode='same')
    return y


def fitfunc(x, a, b,c,d ):
    return -a * np.exp(c + (4*b * (np.array(x)*np.array(x)))) + d


def zero_pad(img, size_new):
    pad_extends = []
    dif_shape_y = size_new[0] - img.shape[0]
    dif_shape_x = size_new[1] - img.shape[1]

    pad_extends.append((dif_shape_y // 2, dif_shape_y // 2 + dif_shape_y % 2))
    pad_extends.append((dif_shape_x // 2, dif_shape_x // 2 + dif_shape_x % 2))

    padded = np.pad(img, pad_extends, "symmetric")

    return padded, pad_extends


def next_power_of2(number):
    return int(np.power(2, np.ceil(np.log2(number))))


def create_mask (xlen, ylen):

    row, col = np.ogrid[0:xlen, 0:ylen]
    length = xlen/2
    edge_norm = length**2
    cosine_falloff = 0.5
    kernel_mask = np.sqrt(((row - length) ** 2 + (col - length) ** 2) /
                          float(edge_norm)) * cosine_falloff
    return kernel_mask


def calculate_bfactor(fsc_array,freq_per_micrograph):

    frames_range = 24
    freq_range = len(freq_per_micrograph[0])
    N_ITER =25

    shift = 10
    # myk = np.array(range(freq_range)) * 1.0 / (2*freq_range)
    # myk = myk[shift:]

    FCC_FITTED = np.zeros((frames_range, freq_range - shift))

    # fsc_final_orig = np.zeros((frames_range, len(myk)))

    # for i in range(frames_range):
    #     f = interpolate.interp1d(freq_per_micrograph[0], fsc_array[i], kind = 'cubic')
    #     fsc_final_orig[i] = f(myk)

    fsc_final_orig = fsc_array[:,shift:]
    myk = freq_per_micrograph[0][shift:]

    dk = np.average(fsc_final_orig, axis=0)

    b_list = np.zeros(frames_range)
    c_list = np.zeros(frames_range)
    d_list = dk # np.zeros(freq_range)


    for iteration in range(N_ITER):
        for f in range(frames_range):
            fcc_per_f = fsc_final_orig[f, :]
            f_c_b = lambda u, c, b: np.multiply(d_list[u], np.exp(c + (4 * b * (myk ** 2))))
            fcc_per_f[fcc_per_f <= 0] = 0.01
            popt, pconv = curve_fit(f_c_b, range(len(myk)), fcc_per_f, p0=(0.45, -85),
                                    bounds=((-20.95, -400), (20, -50)))  # bounds=((-np.inf, -np.inf), (np.inf, -50))
            c_list[f] = popt[0]
            b_list[f] = popt[1]

        for k_index, k in enumerate(myk):
            fcc_per_k = fsc_final_orig[:, k_index]
            fcc_per_k[fcc_per_k <= 0] = 0.01
            f_d = lambda u, d: d * np.exp(c_list[u] + np.multiply(4 * b_list[u], k ** 2))
            popt, pconv = curve_fit(f_d, np.arange(frames_range).tolist(), fcc_per_k, p0=(0.50), bounds=(0, 5))
            d_list[k_index] = popt[0]


    for f in range(frames_range):
        for k_abs in range(len(myk)):
            k = myk[k_abs] #k_abs*1.0/2*freq_range
            FCC_FITTED[f,k_abs] = d_list[k_abs] * np.exp(c_list[f] + 4*b_list[f]*k**2)

    return FCC_FITTED, b_list, c_list, d_list

def get_weight_values(b_list, c_list, freq_k):
    a = np.multiply.outer(4 * np.array(b_list), freq_k ** 2)
    np.add(a.T, np.array(c_list), out=a.T)
    np.exp(a.T, out=a.T)
    return a

#%%

"""
Reading of Movie frames in .mrc format and display one frame
"""
ABSOLUTE_PATH_TO_MRC_FOLDER= "/home/adnan/PycharmProjects/DoseWeighting/MOVIES/"
input_image_path = os.path.join(ABSOLUTE_PATH_TO_MRC_FOLDER, "TcdA1-*_frames.mrcs")

movie_names = return_movie_names(input_image_path)

ABSOLUTE_PATH_TO_LOG_FOLDER= "/home/adnan/PycharmProjects/DoseWeighting/corrsum_dw_log/"
log_movie_path = os.path.join(ABSOLUTE_PATH_TO_LOG_FOLDER, "TcdA1-*_frames.log")
shift_movie_files = return_movie_names(log_movie_path)

# -------------- Loading the reference volume
ref_vol_filename = "/home/adnan/PycharmProjects/DoseWeighting/vol_combined.hdf"
ref_volume = sp_utilities.get_im(ref_vol_filename)
# ---------------Preparing the volume for calculation of projections
volft = sp_projection.prep_vol(ref_volume, npad=2,
                               interpolation_method=1)  # transforms the volume in fourier space and then expands the volume with npad and centers the volume and returns the volume
del ref_volume
# read_meta_shifts
fsc_values = []
fsc_avgs = []
frequencies = []
fsc_raw_all = []

for micro in enumerate(movie_names[ima_start:ima_end]):

    # micro = (0, '/home/adnan/PycharmProjects/DoseWeighting/MOVIES/TcdA1-0100_frames.mrcs')

    logfile = ABSOLUTE_PATH_TO_LOG_FOLDER + micro[1].split('.')[0].split('/')[-1] + '.log'
    shift_x , shift_y = read_meta_shifts(logfile)


    zsize = EMUtil.get_image_count(micro[1])


    """
    Reading a particle stack to find all the parameters saved in the header file
    """

    stackfilename = "bdb:/home/adnan/PycharmProjects/DoseWeighting/Substack/isac_substack"
    source_n_ind_all = EMUtil.get_all_attributes(stackfilename, "source_n")
    no_of_imgs, ptcl_source_images, project_params_all, particle_coordinates_all, ctf_params_all, nx_all, ny_all, nz_all = read_all_attributes_from_stack(stackfilename)

    project_params, particle_coordinates, ctf_params, \
    nx, ny, nz, source_n_ind = find_particles_info_from_movie(
        stackfilename,
        micro[1],
        no_of_imgs,
        ptcl_source_images,
        project_params_all,
        particle_coordinates_all,
        ctf_params_all,
        nx_all,
        ny_all,
        nz_all,
        source_n_ind_all,
        show_first=False)

    """
    Reading a reference map
    """
    ref_project_2D_ptcl_all = get_2D_project_for_all_ptcl_from_reference(volft, project_params, show = False) #Projection of 3D volume in 2-D for all the particles in all frames in one movie

    mask = sp_utilities.model_circle(nx[0] / 2, nx[0], nx[0])  # nx/2 is for the radius
    for i in range(len(ref_project_2D_ptcl_all)):
        ref_project_2D_ptcl_all[i] = sp_filter.filt_ctf(ref_project_2D_ptcl_all[i], ctf_params[i], binary=True)

    """
    Extracting particle image from the movie data. First getting the particle cordinates from the dictionary and then
    creating a window around to extract the same particle from each frame
    """

    fsc_val, fsc_freq = get_fscs_all_particles_modified( micro[1],ref_project_2D_ptcl_all,  nx[0], ny[0], particle_coordinates, zsize)

    fsc_val = np.array(fsc_val)
    fsc_freq = np.array(fsc_freq)


    """
    Calculating the fourier shell correlation of all the particle images with respect to 2-D reference projection of 3-D volume
    """
    fsc_final = []
    for i in range (zsize):
        fsc_sum = [entry/len(fsc_val[i]) for entry in fsc_val[i][0]]
        for fsc in fsc_val[i][1:]:  # one frame ahead for averageing
            for idx, ok in enumerate(fsc):
                fsc_sum[idx] += ok/len(fsc_val[i])
        fsc_final.append(fsc_sum)

    fsc_final_avg =  []
    for idx in range (0,len(fsc_final)-3):
        avv = []
        for p in range(len(fsc_final[idx])):
            avv.append((fsc_final[idx][p] + fsc_final[idx+1][p] + fsc_final[idx+2][p] + fsc_final[idx+3][p] )/4)
        fsc_final_avg.append(avv)

    for idx in range(len(fsc_final) - 3, len(fsc_final)):
        avv = []
        for p in range(len(fsc_final[idx])):
            avv.append((fsc_final[idx][p] + fsc_final[idx-1][p] + fsc_final[idx-2][p] + fsc_final[idx-3][p] )/4)
        fsc_final_avg.append(avv)

    fsc_values.append(fsc_final)
    fsc_avgs.append(fsc_final_avg)
    frequencies.append(fsc_freq[0][0])
    fsc_raw_all.append(np.array(fsc_val))

    # fsc_values_per_micrograph =fsc_values
    # freq_per_micrograph =frequencies
    # fsc_avgs_per_micrograph = fsc_avgs

    del fsc_final
    del fsc_final_avg
    del fsc_freq
    del fsc_val
    del ref_project_2D_ptcl_all
    del mask

del volft


print("Fsc part is completed, removing data from cache")

fsc_values_per_micrograph = sp_utilities.wrap_mpi_gatherv(fsc_values, 0, mpi.MPI_COMM_WORLD)
fsc_avgs_per_micrograph = sp_utilities.wrap_mpi_gatherv(fsc_avgs, 0, mpi.MPI_COMM_WORLD)
freq_per_micrograph = sp_utilities.wrap_mpi_gatherv(frequencies, 0, mpi.MPI_COMM_WORLD)
fsc_raw =  sp_utilities.wrap_mpi_gatherv(fsc_raw_all, 0 , mpi.MPI_COMM_WORLD)


del fsc_values
del fsc_avgs
del frequencies
del fsc_raw_all


mpi.mpi_barrier(mpi.MPI_COMM_WORLD)
"""
Writing data in pickle files

"""
#%%

"""
mpi.mpi_barrier(mpi.MPI_COMM_WORLD)

if my_mpi_proc_id == main_mpi_proc:
    with open(str(no_of_micrographs) + '_Micrograph_plot_values', 'wb') as wb:
        for value in fsc_values_per_micrograph:
            pickle.dump(value, wb)
    wb.close()


    with open(str(no_of_micrographs) + '_Micrograph_avg_plot_values', 'wb') as wb:
        for value in fsc_avgs_per_micrograph:
            pickle.dump(value, wb)
    wb.close()


    with open(str(no_of_micrographs) + '_Micrograph_frequencies_plot_values', 'wb') as wb:
        for value in freq_per_micrograph:
            pickle.dump(value, wb)
    wb.close()


    with open(str(no_of_micrographs) + '_Micrograph_raw_fsc_values', 'wb') as wb:
        for value in fsc_raw:
            pickle.dump(value, wb)
    wb.close()


    # del fsc_values_per_micrograph
    # del fsc_avgs_per_micrograph
    # del freq_per_micrograph
    # del fsc_raw

"""
print("I am finish")
#


#%%

fsc_values_per_micrograph = []
fsc_avgs_per_micrograph = []
freq_per_micrograph = []
fsc_raw = []

if my_mpi_proc_id == main_mpi_proc:
    with open(location + '/sphire/bin/' + str(no_of_micrographs) + '_Micrograph_plot_values', 'rb') as rb:
        while True:
            try:
                fsc_values_per_micrograph.append(pickle.load(rb))
            except EOFError:
                break

    rb.close()


    with open(location + '/sphire/bin/' + str(no_of_micrographs) + '_Micrograph_avg_plot_values', 'rb') as rb:
        while True:
            try:
                fsc_avgs_per_micrograph.append(pickle.load(rb))
            except EOFError:
                break
    rb.close()


    with open(location + '/sphire/bin/' + str(no_of_micrographs) + '_Micrograph_frequencies_plot_values', 'rb') as rb:
        while True:
            try:
                freq_per_micrograph.append(pickle.load(rb))
            except EOFError:
                break
    rb.close()


    with open(location + '/sphire/bin/' + str(no_of_micrographs) + '_Micrograph_raw_fsc_values', 'rb') as rb:
        while True:
            try:
                fsc_raw.append(pickle.load(rb))
            except EOFError:
                break
    rb.close()



print(np.array(fsc_values_per_micrograph).shape)
print(np.array(fsc_avgs_per_micrograph).shape)
print(np.array(freq_per_micrograph).shape)


fsc_values_per_micrograph = np.array(fsc_values_per_micrograph)
fsc_avgs_per_micrograph = np.array(fsc_avgs_per_micrograph)
freq_per_micrograph = np.array(freq_per_micrograph)

# fsc_raw = np.array(fsc_raw[0])



#%%

if main_mpi_proc == my_mpi_proc_id :

    fsc_values_per_micrograph = np.array(fsc_values_per_micrograph)
    fsc_avgs_per_micrograph = np.array(fsc_avgs_per_micrograph)
    freq_per_micrograph = np.array(freq_per_micrograph)

    fsc_sum_per_frame = []
    for frames_ind in range(fsc_values_per_micrograph.shape[1]):
        fsc_sum =  [entry / len(fsc_values_per_micrograph) for entry in fsc_values_per_micrograph[0][frames_ind]]
        for micrograph in fsc_values_per_micrograph[1:]:
            for ind , values in enumerate(micrograph[frames_ind]):
                fsc_sum[ind] += values/len(fsc_values_per_micrograph)
        fsc_sum_per_frame.append(fsc_sum)


    fsc_sum_per_frame = np.array(fsc_sum_per_frame)[:] * -1

    FCC_FITTED, b_list, c_list, d_list = calculate_bfactor(fsc_sum_per_frame,freq_per_micrograph)

    b_list = [float(val) for val in b_list]
    c_list = [float(val) for val in c_list]
    d_list = [float(val) for val in d_list]

    del fsc_sum_per_frame

else:
    b_list = []
    c_list = []
    d_list = []


b_list = sp_utilities.bcast_list_to_all(b_list, my_mpi_proc_id, main_mpi_proc, mpi.MPI_COMM_WORLD)
c_list = sp_utilities.bcast_list_to_all(c_list, my_mpi_proc_id, main_mpi_proc, mpi.MPI_COMM_WORLD)
d_list = sp_utilities.bcast_list_to_all(d_list, my_mpi_proc_id, main_mpi_proc, mpi.MPI_COMM_WORLD)



"""
# i= 0
# fig , ax = plt.subplots(nrows = 4, ncols=6 )
# for row in ax:
#     for col in row:
#         if i < len(fsc_sum_avg_per_frame):
#             col.plot(freq_per_micrograph[0][offset_start:offset_end], smooth(fsc_array[i][offset_start:offset_end], window_len), label= 'Orig_' + str(i))
#             col.plot(freq_per_micrograph[0][offset_start:offset_end],  FCC_FITTED[i], label='fit_' + str(i))
#             i+= 1
#             col.legend()
# plt.show()


# plt.figure()
# plt.plot(np.arange(24),b_list, 'o-',label = 'B-factors')
# plt.legend()



# for mic in range(len(fsc_raw)):
#     fsc_raw_mic = fsc_raw[mic]
#     fsc_final_mic = []
#     for i in range(24):
#         fsc_sum_mic = [entry / len(fsc_raw_mic[i]) for entry in fsc_raw_mic[i][0]]
#         for fsc in fsc_raw_mic[i][1:]:  # one frame ahead for averageing
#             for idx, ok in enumerate(fsc):
#                 fsc_sum_mic[idx] += ok / len(fsc_raw_mic[i])
#         fsc_final_mic.append(fsc_sum_mic)
#
#     FCC_FITTED_mic, weight_per_frame_mic, b_list_mic, c_list_mic, d_list_mic = calculate_bfactor(np.array(fsc_final_mic) * -1 )

"""

#%%
print("Creating mask for all images, Start")
shape = (4096, 4096)
mask_applied = create_mask(*shape)
sum_k = get_weight_values(b_list, c_list, mask_applied).sum(axis=0)
print("Creating mask for all images, Finish")

for micro in enumerate(movie_names[ima_start:ima_end]):

    if main_mpi_proc == my_mpi_proc_id:
        b_list = sp_utilities.bcast_list_to_all(b_list, my_mpi_proc_id, main_mpi_proc, mpi.MPI_COMM_WORLD)
        c_list = sp_utilities.bcast_list_to_all(c_list, my_mpi_proc_id, main_mpi_proc, mpi.MPI_COMM_WORLD)
        d_list = sp_utilities.bcast_list_to_all(d_list, my_mpi_proc_id, main_mpi_proc, mpi.MPI_COMM_WORLD)

# micro = (0, '/home/adnan/PycharmProjects/DoseWeighting/MOVIES/TcdA1-0100_frames.mrc')

    ABSOLUTE_PATH_TO_LOG_FOLDER= "/home/adnan/PycharmProjects/DoseWeighting/corrsum_dw_log/"
    logfile = ABSOLUTE_PATH_TO_LOG_FOLDER + micro[1].split('.')[0].split('/')[-1] + '.log'

    shift_x, shift_y = read_meta_shifts(logfile)
    zsize = EMUtil.get_image_count(micro[1])

    stackfilename = "bdb:/home/adnan/PycharmProjects/DoseWeighting/Substack/isac_substack"
    source_n_ind_all = EMUtil.get_all_attributes(stackfilename, "source_n")
    no_of_imgs, ptcl_source_images, project_params_all, particle_coordinates_all, ctf_params_all, nx_all, ny_all, nz_all = read_all_attributes_from_stack(stackfilename)

    project_params, particle_coordinates, ctf_params, \
                                    nx, ny, nz, source_n_ind = find_particles_info_from_movie(
                                    stackfilename,
                                    micro[1],
                                    no_of_imgs,
                                    ptcl_source_images,
                                    project_params_all,
                                    particle_coordinates_all,
                                    ctf_params_all,
                                    nx_all,
                                    ny_all,
                                    nz_all,
                                    source_n_ind_all,
                                    show_first=False)
    del no_of_imgs
    del ptcl_source_images
    del project_params_all
    del particle_coordinates_all
    del ctf_params_all
    del project_params

    particle_imgs_dosed = get_all_reduce_ptcl_imgs_modified(micro[1], nx[0], ny[0],particle_coordinates,
                                                            b_list, c_list, mask_applied, sum_k, zsize)

    particle_imgs_dosed = np.array(particle_imgs_dosed).swapaxes(0,1)

    mask = sp_utilities.model_circle(nx[0] / 2, nx[0], nx[0])
    ave_particle_dosed = []
    for i in range(len(particle_imgs_dosed)):
        ave_particle_dosed.append(sum(particle_imgs_dosed[i]) / zsize)

        st = Util.infomask(ave_particle_dosed[i], mask, False)
        Util.mul_scalar(ave_particle_dosed[i], -1.0)
        ave_particle_dosed[i] += 2 * st[0]

        st = Util.infomask(ave_particle_dosed[i], mask, False)
        ave_particle_dosed[i] -= st[0]
        ave_particle_dosed[i] /= st[1]

    del particle_imgs_dosed

    stack_absolute_path = "/home/adnan/PycharmProjects/DoseWeighting/NewParticles/"
    local_stack_path = "bdb:%s" % stack_absolute_path + micro[1].split('.')[0].split('/')[-1] + "_ptcls"

    local_mrc_path = stack_absolute_path + micro[1].split('.')[0].split('/')[-1] + "_ptcls.mrcs"


    local_bdb_stack = db_open_dict(local_stack_path)
    old_stack = db_open_dict(stackfilename, ro=True)

    for i in range(len(ave_particle_dosed)):
        index_old = source_n_ind[i]
        old_dict = old_stack.get(index_old, nodata=True).get_attr_dict()
        old_dict['data_path'] = local_mrc_path
        old_dict['ptcl_source_coord_id'] = i
        local_bdb_stack[i] = old_dict
        ave_particle_dosed[i].append_image(local_mrc_path)

    db_close_dict(local_stack_path)
    db_close_dict(stackfilename)



    del local_bdb_stack
    del old_stack
    del ave_particle_dosed
    del source_n_ind

mpi.mpi_barrier(mpi.MPI_COMM_WORLD)
mpi.mpi_finalize()

#%%


stackfileold = "bdb:/home/adnan/PycharmProjects/DoseWeighting/Substack/isac_substack"
boxid_old = EMUtil.get_all_attributes(stackfileold, "ptcl_source_box_id")
attrib_old= read_all_attributes_from_stack(stackfileold)
no_of_imgs_old = attrib_old[0]
ptcl_source_images_old = attrib_old[1]


stackfilenew = "bdb:/home/adnan/PycharmProjects/DoseWeighting/all_particlesv5"
boxid_new = np.array(EMUtil.get_all_attributes(stackfilenew, "ptcl_source_box_id"))
ptcl_source_images_new = np.array(EMUtil.get_all_attributes(stackfilenew, 'ptcl_source_image'))

chunks_loc = "/home/adnan/PycharmProjects/DoseWeighting/chunks/"
chunck0_file = chunks_loc + "chunk_0_000.txt"
chunck1_file = chunks_loc + "chunk_1_000.txt"

chunck0 = np.loadtxt(chunck0_file)
chunck1 = np.loadtxt(chunck1_file)



new_chunck0 = []
for i in chunck0:
    i = int(i)
    print(i)
    img_idx = np.where((ptcl_source_images_old[i] == ptcl_source_images_new) & (boxid_old[i] == boxid_new))[0]
    new_chunck0.append(int(img_idx))

new_chunck1 = [index for index in range(boxid_new.shape[0]) if index not in new_chunck0]



np.savetxt(chunks_loc + "polish_chuck_0_000.txt", new_chunck0, fmt = '% 4d')
np.savetxt(chunks_loc + "polish_chuck_1_000.txt", new_chunck1, fmt = '% 4d')




#%%

"""

plt.figure()
plt.imshow(np.array(particle_imgs_dosed).T[0][0].get_2dview(),  cmap = plt.get_cmap('Greys'))
plt.colorbar()

plt.figure()
plt.imshow(ave_particle_dosed[47].get_2dview(),  cmap = plt.get_cmap('Greys'))
plt.colorbar()
"""


#%%

""" Time to save some data homies """





# mpi.mpi_barrier(mpi.MPI_COMM_WORLD)
# mpi.mpi_finalize()


#%%

# plt.figure()
# plt.imshow(doseweight_frames.mean(axis=0),  cmap = plt.get_cmap('Greys'))
# plt.colorbar()
#
#
# plt.figure()
# plt.imshow(frames_np.mean(axis=0),  cmap = plt.get_cmap('Greys'))
# plt.colorbar()

# img_no = 6
#
# plt.figure()
# plt.imshow(weights_mask[img_no])
# plt.colorbar()
#
#
# plt.figure()
# plt.imshow(doseweight_frames[img_no].real,cmap = plt.get_cmap('Greys'))
# plt.colorbar()
#
#
# plt.figure()
# plt.imshow(frames_np[img_no],cmap = plt.get_cmap('Greys'))
# plt.colorbar()



#%%
#Trying something new which is similar to what relion does

""""
fsc_final = np.array(fsc_final)
fsc_final_avg = np.array(fsc_final_avg)

i = 0
# window_len = 6
fig , ax = plt.subplots(nrows = 4, ncols=6 )
for row in ax:
    for col in row:
        if i < len(fsc_final):
            print(i)
            fsc_final_i = smooth(fsc_final[i][3:], window_len)
            fsc_final_avg_i = smooth(fsc_final_avg[i][3:], window_len)
            fsc_final_i = fsc_final_i[:][(fsc_final_i > 0.143) & (fsc_final_i < 1)]
            fsc_final_avg_i = fsc_final_avg_i[:][(fsc_final_avg_i > 0.143) & (fsc_final_avg_i < 1)]

            fsc_final_i = fsc_final_i[0:len(fsc_final_avg_i)]
            rel_damp_sqrt = np.sqrt(
                np.divide(fsc_final_i - fsc_final_i * fsc_final_avg_i, fsc_final_avg_i - fsc_final_i * fsc_final_avg_i))
            reldamp_i = np.log(rel_damp_sqrt)

            col.plot(np.array(fsc_s)[0][0][0][0:len(reldamp_i)], reldamp_i, label='Frame' + str(i))
            # col.plot(fsc_s[0][0][0],smooth(fsc_final_avg[i], window_len), label='Average' + str(i))
            i+= 1
            col.legend()

plt.show()



    # fig = plt.figure()
    # ax = fig.add_subplot(111)
    # for i in range(5):
    #     if i == 0:
    #         shift_x_app = shift_x
    #         shift_y_app = shift_y
    #         name = 'add'
    #     elif i == 1:
    #         shift_x_app = [-entry for entry in shift_x]
    #         shift_y_app = [-entry for entry in shift_y]
    #         name = 'subtract'
    #     elif i == 2:
    #         shift_x_app = [entry for entry in shift_x]
    #         shift_y_app = [-entry for entry in shift_y]
    #         name = 'pxmy'
    #     elif i == 3:
    #         shift_x_app = [-entry for entry in shift_x]
    #         shift_y_app = [entry for entry in shift_y]
    #         name = 'mxpy'
    #     elif i == 4:
    #         shift_x_app = [0 for entry in shift_x]
    #         shift_y_app = [0 for entry in shift_y]
    #         name = 'normal'
    #     particle_imgs = get_all_reduce_ptcl_imgs(
    #         frames, mask, nx[0], ny[0], [particle_coordinates[num]],
    #         ctf_params, cen_x, cen_y, cen_z, shift_x_app , shift_y_app
    #     )
    #     print(particle_imgs)
    #     print(np.array(particle_coordinates).shape  )
    #
    #     avg_part = sum(particle_imgs[0])
    #     fsc = sp_statistics.fsc(avg_part, ref_project_2D_ptcl_all[num])
    #     print(name, fsc[1])
    #     ax.plot(fsc[0], fsc[1], label=str(i))
    #
    #     plt.figure()
    #     plt.imshow(avg_part.get_2dview()[::-1],cmap = plt.get_cmap('Greys'))
    #     plt.colorbar()
    #     plt.title(str(micro[1]) )
    #     plt.savefig(str(micro[1]) + '_{0}.png'.format(name))
    #     plt.clf()
    #
    # ax.legend()
    # fig.savefig(str(micro[1]) + '_fsc.png')


"""