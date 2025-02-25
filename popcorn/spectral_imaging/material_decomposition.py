import sys
import glob

import numpy as np

from pathlib import Path
path_root = str(Path(__file__).parents[1])
if path_root not in sys.path:
    sys.path.append(path_root)

from popcorn import resampling, input_output
import spekpy as sp

import skimage.io as io
import pandas as pd


def loading_bar(iteration, total_iterations):
    """

    Args:
        iteration ():
        total_iterations ():

    Returns:

    """
    percent = "{0:.1f}".format(100 * (float(iteration) / float(total_iterations)))

    filled_length = int(100 * float(iteration) // float(total_iterations))

    bar = '#' * filled_length + '-' * (100 - filled_length)
    print("\r |" + bar + "| " + percent + "% ", end="")
    # Print New Line on Complete
    sys.stdout.flush()
    if iteration == total_iterations:
        print()


def retrieve_material_and_energy_from_folder_name(folder_name):
    """

    Args:
        folder_name ():

    Returns:

    """
    if "AboveAu" in folder_name:
        return "Au", "above"
    elif "BelowAu" in folder_name:
        return "Au", "below"
    elif "AboveBa" in folder_name:
        return "Ba", "above"
    elif "BelowBa" in folder_name:
        return "Ba", "below"
    elif "AboveGd" in folder_name:
        return "Gd", "above"
    elif "BelowGd" in folder_name:
        return "Gd", "below"
    elif "AboveI" in folder_name:
        return "I", "above"
    elif "BelowI" in folder_name:
        return "I", "below"
    else:
        return None, None


def get_attenuation_from_kedge(attenuation_material="Au", kedge_material="I", above_or_below="above"):
    """returns linear attenuation value depending on the given material and energy (above/below k-edge)

    Args:
        attenuation_material (str): material we need the attenuation of
        kedge_material (str):       material whose k-edge we used for above/below acquisitions
        above_or_below (str):       above or below given material k-edge

    Returns:
        (float): linear attenuation value
    """
    indices_dict = {
        "water": 0,
        "h2o": 0,
        "i": 1,
        "iodine": 1,
        "ba": 2,
        "barium": 2,
        "gd": 3,
        "gadolinium": 3,
        "au": 4,
        "gold": 4
    }

    #          I-        I+       Ba-       Ba+       Gd-       Gd+       Au-       Au+
    muz = [[000.3307, 000.3188, 000.2940, 000.2790, 000.2290, 000.2240, 000.1835, 000.1827],  # Water
           [033.6370, 170.9231, 028.2000, 024.5600, 012.8300, 011.5500, 016.8852, 016.3330],  # Iodine
           [008.2170, 007.0000, 005.9230, 027.3200, 014.3500, 012.9300, 004.0000, 003.7450],  # Barium
           [012.3200, 010.4900, 008.8730, 007.7050, 004.0150, 017.7000, 005.6240, 005.2720],  # Gadolinium
           [421.9694, 389.5878, 016.5900, 014.4300, 007.5510, 006.8090, 040.7423, 165.8642]]  # Gold

    kedge_material_index = indices_dict.get(kedge_material.lower())
    attenuation_material_index = indices_dict.get(attenuation_material.lower())

    if above_or_below.lower() == "above":
        return muz[attenuation_material_index][(kedge_material_index - 1) * 2 + 1]
    else:
        return muz[attenuation_material_index][(kedge_material_index - 1) * 2]


def material_decomposition_pipeline(radix):
    """Temporary material decomposition for (I, Ba, Gd, Au) + Water

    Args:
        radix (str): radix of reconstructed images

    Returns:
        None
    """
    densities_dict = {
        "water": 1.0,
        "i": 4.93,
        "ba": 3.5,
        "gd": 7.9,
        "au": 19.3,
    }
    list_of_materials = []
    list_of_energies = []
    checking_folders = glob.glob(radix + "*/")
    list_of_input_folders = []
    list_of_min_max = []
    # Checking all potential folders corresponding to given radix
    for folder in checking_folders:
        material, energy = retrieve_material_and_energy_from_folder_name(folder)
        if material is not None and material not in list_of_materials:
            list_of_materials.append(material)
        if material is not None and energy is not None:
            list_of_energies.append((energy, material))
            list_of_input_folders.append(folder)
            list_of_min_max.append((float(folder.split("_")[-2]),
                                    float(folder.split("_")[-1].replace("\\", "").replace("/", ""))))

    print("list of energies :", list_of_energies)
    attenuations_array = np.zeros((len(list_of_energies), len(list_of_materials) + 1))

    material_index = 0
    print("materials :", list_of_materials)

    # 1- Creating and filling in attenuation array for material decomposition
    for energy_index, (above_or_below, kedge_material) in enumerate(list_of_energies):
        # Retrieving linear attenuation for input materials
        for attenuation_material in list_of_materials:
            attenuations_array[energy_index, material_index] = \
                get_attenuation_from_kedge(attenuation_material, kedge_material, above_or_below=above_or_below)

            material_index += 1

        # Retrieving linear attenuation for water
        attenuations_array[energy_index, len(list_of_materials)] = \
            get_attenuation_from_kedge("water", kedge_material, above_or_below=above_or_below)
        material_index = 0
    print("attenuations array :", attenuations_array)

    # 2- Creating a list of material density for material decomposition
    list_of_densities = [
        densities_dict[material.lower()] for material in list_of_materials
    ]

    list_of_densities.append(densities_dict["water"])
    densities = np.array(list_of_densities)
    print("densities :", densities)

    # We'll now proceed to the material decomposition one image at a time: we create the list of files for each
    # acquisition -> becomes a list of list of files (could be written better)
    list_of_list_of_filenames = []
    nb_of_filenames = []
    for folder in list_of_input_folders:
        print("folder :", folder)
        current_list_of_filenames = input_output.create_list_of_files(folder, ".tif")
        nb_of_filenames.append(len(current_list_of_filenames))
        list_of_list_of_filenames.append(current_list_of_filenames)

    total_filenames_nb = min(nb_of_filenames)
    reference_image = input_output.open_image(list_of_list_of_filenames[0][0])
    reference_width, reference_height = reference_image.shape

    images = np.zeros((len(list_of_energies), reference_width, reference_height))

    # We create output folders
    material_decomposition_folder = radix.split("*")[0] + "material_decomposition/"
    input_output.create_directory(material_decomposition_folder)
    list_of_output_folders = []
    for material in list_of_materials:
        input_output.create_directory(material_decomposition_folder + material + "_decomposition/")
        list_of_output_folders.append(material_decomposition_folder + material + "_decomposition/")
    input_output.create_directory(material_decomposition_folder + "water_decomposition/")
    list_of_output_folders.append(material_decomposition_folder + "water_decomposition/")

    # 3- Material decomposition
    for slice_nb in range(total_filenames_nb):
        loading_bar(slice_nb, total_filenames_nb - 1)

        for material_index in range(len(list_of_input_folders)):
            image = input_output.open_image(list_of_list_of_filenames[material_index][slice_nb])
            converted_image = resampling.conversion_from_uint16_to_float32(image, list_of_min_max[material_index][0],
                                                                           list_of_min_max[material_index][1])
            images[material_index, :, :] = converted_image

        concentration_maps = decomposition_equation_resolution(images, densities, attenuations_array,
                                                               volume_fraction_hypothesis=False, verbose=False)

        for material_index in range(len(list_of_output_folders)):
            input_output.save_tif_image(concentration_maps[material_index, :, :],
                                        list_of_output_folders[material_index] + '%4.4d' % slice_nb)


def three_materials_decomposition(above_kedge_image, below_kedge_image, kedge_material="Au", secondary_material="I"):
    """Temporary 3 material decomposition for (I, Ba, Gd, Au) + Water

    Args:
        above_kedge_image (numpy.ndarray): above K-edge acquisition image
        below_kedge_image (numpy.ndarray): below K-edge acquisition image
        kedge_material (str):              K-edge element (among I, Ba, Gd and Au)
        secondary_material (str):          secondary element (among I, Ba, Gd and Au)

    Returns:
        (numpy.ndarray, numpy.ndarray, numpy.ndarray): concentration maps (in g/L) of both input materials and water
    """
    indices_dict = {
        "i": 1,
        "iodine": 1,
        "ba": 2,
        "barium": 2,
        "gd": 3,
        "gadolinium": 3,
        "au": 4,
        "gold": 4
    }

    #          I-        I+       Ba-       Ba+       Gd-       Gd+       Au-       Au+
    muz = [[000.3307, 000.3188, 000.2940, 000.2790, 000.2290, 000.2240, 000.1835, 000.1827],  # Water
           [033.6370, 170.9231, 028.2000, 024.5600, 012.8300, 011.5500, 016.8852, 016.3330],  # Iodine
           [008.2170, 007.0000, 005.9230, 027.3200, 014.3500, 012.9300, 004.0000, 003.7450],  # Barium
           [012.3200, 010.4900, 008.8730, 007.7050, 004.0150, 017.7000, 005.6240, 005.2720],  # Gadolinium
           [421.9694, 389.5878, 016.5900, 014.4300, 007.5510, 006.8090, 040.7423, 165.8642]]  # Gold

    densities = [4.93, 3.5, 7.9, 19.3]

    kedge_material_index = indices_dict.get(kedge_material.lower())
    secondary_material_index = indices_dict.get(secondary_material.lower())

    # Water attenuation
    mu_water_below = muz[0][(kedge_material_index - 1) * 2]
    mu_water_above = muz[0][(kedge_material_index - 1) * 2 + 1]

    # Secondary material attenuation
    mu_secondary_material_below = muz[secondary_material_index][(kedge_material_index - 1) * 2]
    mu_secondary_material_above = muz[secondary_material_index][(kedge_material_index - 1) * 2 + 1]

    # Kedge material attenuation
    mu_kedge_material_below = muz[kedge_material_index][(kedge_material_index - 1) * 2]
    mu_kedge_material_above = muz[kedge_material_index][(kedge_material_index - 1) * 2 + 1]

    images = np.stack((above_kedge_image, below_kedge_image), axis=0)
    material_densities = np.array([densities[kedge_material_index - 1], densities[secondary_material_index - 1], 1.0])
    mus = np.array([[mu_kedge_material_above, mu_secondary_material_above, mu_water_above],
                    [mu_kedge_material_below, mu_secondary_material_below, mu_water_below]])

    main_material_concentration_map, second_material_concentration_map, water_concentration_map = \
        decomposition_equation_resolution(images, material_densities, mus)

    return main_material_concentration_map.copy(), \
        second_material_concentration_map.copy(), \
        water_concentration_map.copy()


def decomposition_equation_resolution(images, densities, material_attenuations, volume_fraction_hypothesis=True,
                                      verbose=False):
    """solves the element decomposition system

    Args:
        images (numpy.ndarray): N dim array, each N-1 dim array is an image acquired at 1 given energy (can be 2D or 3D,
        K energies in total)
        densities (numpy.ndarray): 1D array, one density per elements inside a voxel (P elements in total)
        material_attenuations (numpy.ndarray): 2D array, linear attenuation of each element at each energy (K * P array)
        volume_fraction_hypothesis (bool):
        verbose (bool):

    Returns:
        (numpy.ndarray): material decomposition maps, N-dim array composed of P * N-1-dim arrays
    """
    number_of_energies = images.shape[0]
    number_of_materials = densities.size

    if verbose:
        print("-- Material decomposition --")
        print(">Number of energies: ", number_of_energies)
        print(">Number of materials: ", number_of_materials)
        print(">Sum of materials volume fraction equal to 1 hypothesis :", volume_fraction_hypothesis)

    system_2d_matrix = np.ones((number_of_energies + volume_fraction_hypothesis * 1, number_of_materials))

    system_2d_matrix[0:number_of_energies, :] = material_attenuations
    vector_2d_matrix = np.ones((number_of_energies + volume_fraction_hypothesis * 1, images[0, :].size))
    for energy_index, image in enumerate(images):
        vector_2d_matrix[energy_index] = image.flatten()
    vector_2d_matrix = np.transpose(vector_2d_matrix)

    solution_matrix = None
    if number_of_energies + volume_fraction_hypothesis * 1 == number_of_materials:
        system_3d_matrix = np.repeat(system_2d_matrix[np.newaxis, :], images[0, :].size, axis=0)
        solution_matrix = np.linalg.solve(system_3d_matrix, vector_2d_matrix)
    else:
        for nb, vector in enumerate(vector_2d_matrix):

            # Q, R = np.linalg.qr(system_2d_matrix)  # qr decomposition of A
            # Qb = np.dot(Q.T, vector)  # computing Q^T*b (project b onto the range of A)
            # solution_vector = np.linalg.solve(R, Qb)  # solving R*x = Q^T*b
            solution_vector = np.linalg.lstsq(system_2d_matrix, vector, rcond=None)

            if solution_matrix is not None:
                # loading_bar(nb, vector_2d_matrix.size)
                if solution_matrix.ndim == 2:
                    solution_matrix = np.vstack([solution_matrix, solution_vector[0]])
                else:
                    solution_matrix = np.stack((solution_matrix, solution_vector[0]), axis=0)
            else:
                solution_matrix = solution_vector[0]
    if images.ndim == 3:
        concentration_maps = np.zeros((number_of_materials, images[0, :].shape[0], images[0, :].shape[1]))
    else:
        concentration_maps = np.zeros((number_of_materials, images[0, :].shape[0], images[0, :].shape[1],
                                       images[0, :].shape[2]))

    for material_index in range(len(densities)):
        solution_matrix[:, material_index] = (solution_matrix[:, material_index] * densities[material_index] * 1000.0)\
            .astype(np.float32)
        concentration_maps[material_index, :] = np.reshape(solution_matrix[:, material_index], images[0, :].shape)
    return concentration_maps


def multispectral_decomposition(input_folder):
    list_of_tif_files = input_output.create_list_of_files(input_folder, "tif")
    print(list_of_tif_files)

    gold_attenuations = pd.read_csv('gold_attenuation.csv').to_numpy().flatten()
    iodine_attenuations = pd.read_csv('iodine_attenuation.csv').to_numpy().flatten()
    water_attenuations = pd.read_csv('water_attenuation.csv').to_numpy().flatten()

    list_of_images = []
    list_of_voltages = []
    list_of_spectrum = []
    list_of_gold_mus = []
    list_of_iodine_mus = []
    list_of_water_mus = []
    for tif_file in list_of_tif_files:
        current_image = io.imread(tif_file)
        current_voltage = float(tif_file.lower().split('kvp')[0].split('_')[-1])
        current_image = current_image.astype(np.float32) - (32768*np.ones(current_image.shape))

        spectre = sp.Spek()
        spectre.set(kvp=current_voltage, th=20, targ="W")
        spectre.filter("Al", 1.8)
        normalized_spectrum = spectre.get_spectrum()[1]/np.sum(spectre.get_spectrum()[1])
        converted_image = resampling.convert_from_hounsfield_unit_to_mu(current_image, normalized_spectrum)
        list_of_images.append(converted_image)
        list_of_voltages.append(current_voltage)
        list_of_spectrum.append(normalized_spectrum)
        list_of_gold_mus.append(np.sum(normalized_spectrum * gold_attenuations[0:normalized_spectrum.shape[0]]))
        list_of_iodine_mus.append(np.sum(normalized_spectrum * iodine_attenuations[0:normalized_spectrum.shape[0]]))
        list_of_water_mus.append(np.sum(normalized_spectrum * water_attenuations[0:normalized_spectrum.shape[0]]))

    min_x = 100000
    min_y = 100000
    min_z = 100000
    for image in list_of_images:
        if image.shape[0] < min_z:
            min_z = image.shape[0]
        if image.shape[1] < min_y:
            min_y = image.shape[1]
        if image.shape[2] < min_x:
            min_x = image.shape[2]

    print("mins :", min_x, min_y, min_z)
    i = 0
    for image in list_of_images:
        if image.shape[0] > min_z:
            image = image[(image.shape[0]-min_z)//2:(image.shape[0]-min_z)//2 + min_z,:,:]
        if image.shape[1] > min_y:
            image = image[:,(image.shape[1]-min_y)//2:(image.shape[1]-min_y)//2 + min_y,:]
        if image.shape[2] > min_x:
            image = image[:,:,(image.shape[2]-min_x)//2:(image.shape[2]-min_x)//2 + min_x]
        list_of_images[i] = image
        input_output.save_tif_sequence(image, input_folder + "\\converted_" + str(i) + "kVp\\")
        i+=1

    list_of_masks = []
    i = 0
    for image in list_of_images:
        mask = np.zeros(image.shape)
        if i == 0:
            mask[image >= 1.7] = 1
        else:
            mask[image >= 1.0] = 1
        list_of_masks.append(mask)
        input_output.save_tif_sequence(mask, input_folder + "\\mask" + str(i) + "\\")
        i += 1

    first_index = 0
    second_index = 1
    from popcorn.spectral_imaging import registration
    rotation_transform = registration.registration_computation(list_of_images[first_index]/np.amax(list_of_images[first_index]),
                                                               list_of_images[second_index]/np.amax(list_of_images[second_index]),
                                                               transform_type="translation",
                                                               metric="msq",
                                                               moving_mask=list_of_masks[first_index],
                                                               ref_mask=list_of_masks[second_index],
                                                               verbose=True)

    # Registering the above image
    registered_image = registration.apply_itk_transformation(list_of_images[first_index], rotation_transform, "linear", ref_img=list_of_images[second_index])
    input_output.save_tif_sequence(registered_image, input_folder + "\\registered_35kVp\\")

    images = np.stack((list_of_images[second_index], registered_image), axis=0)
    material = "Au"
    if material == "Au":
        densities = np.array([19.3, 1.0])
        material_attenuations = np.array([[list_of_gold_mus[second_index], list_of_water_mus[second_index]],
                                          [list_of_gold_mus[first_index], list_of_water_mus[first_index]]])
    else:
        densities = np.array([4.93, 1.0])
        material_attenuations = np.array([[list_of_iodine_mus[second_index], list_of_water_mus[second_index]],
                                          [list_of_iodine_mus[first_index], list_of_water_mus[first_index]]])
    concentration_maps = decomposition_equation_resolution(images, densities, material_attenuations,
                                                                 volume_fraction_hypothesis=False,
                                                                 verbose=False)
    print(list_of_water_mus)
    import PyIPSDK.IPSDKIPLBinarization as Bin
    import PyIPSDK
    import PyIPSDK.IPSDKIPLMorphology as Morpho
    mask = list_of_images[second_index] > 1.0
    thresholded_image_ipsdk = Bin.lightThresholdImg(PyIPSDK.fromArray(mask), 1)

    # We start with a 3d opening image computation
    morpho_mask = PyIPSDK.sphericalSEXYZInfo(2)  # 3D sphere (r=1) structuring element
    opened_image = Morpho.dilate3dImg(thresholded_image_ipsdk, morpho_mask)
    concentration_map = np.copy(concentration_maps[0])
    # concentration_map[opened_image.array > 0] = 0
    input_output.save_tif_sequence(concentration_map, input_folder + "\\gold_decomposition\\")


    # energy_list = [35, 50, 70, 80]
    # for energy in energy_list:
    #     spectre = sp.Spek()
    #     spectre.set(kvp=energy, th=20, targ="W")
    #     spectre.filter("Al", 1.8)
    #     normalized_spectrum = spectre.get_spectrum()[1]/np.sum(spectre.get_spectrum()[1])
    #     print("for energy", energy, "water attenuation :", np.sum(normalized_spectrum * water_attenuations[0:normalized_spectrum.shape[0]]))
    #     print("for energy", energy, "gold attenuation :", np.sum(normalized_spectrum * gold_attenuations[0:normalized_spectrum.shape[0]]))





    # print(list_of_spectrum)
    # print("-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-")
    # print(gold_attenuations)
    # print("-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-")
    # print(iodine_attenuations)
    # print("-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-")
    # print(water_attenuations)
    # print("-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-")
if __name__ == '__main__':


    folder = "C:\\Users\\ctavakol\\Desktop\\Experiences_Fevrier_2021\\muCT\\LRB-tests CT\\P17\\"
    multispectral_decomposition(folder)
    # spectre = sp.Spek()
    # spectre.set(kvp=80, th=20, targ="W")
    # spectre.filter("Al", 1.8)
    # spectrum = spectre.get_spectrum()
    #
    # print(spectrum)
    # material_decomposition_pipeline("C:\\Users\\ctavakol\\Desktop\\test_material_decomposition\\BiColor_Cell_Pellet__")

    """radix = "BiColor_B1toB9__"
    mainFolder = "/data/visitor/md1237/id17/voltif/"
    mainMaterial = "Au"

    aboveFileNames = glob.glob(mainFolder + radix + "*Above*" + mainMaterial + "*.*" + '/*.tif') + glob.glob(
        mainFolder + radix + "*Above*" + mainMaterial + "*.*" + '/*.edf')
    aboveFileNames.sort()

    belowFileNames = glob.glob(mainFolder + radix + "*Below*" + mainMaterial + "*.*" + '/*.tif') + glob.glob(
        mainFolder + radix + "*Below*" + mainMaterial + "*.*" + '/*.edf')
    belowFileNames.sort()

    aboveFolder = aboveFileNames[0].split("/")[-2]
    aboveMinFloat = float(aboveFolder.split("_")[-2])
    aboveMaxFloat = float(aboveFolder.split("_")[-1])
    print("Found above folder :", aboveFolder)
    print("min Float value :", aboveMinFloat)
    print("max Float value :", aboveMaxFloat)
    belowFolder = belowFileNames[0].split("/")[-2]
    belowMinFloat = float(belowFolder.split("_")[-2])
    belowMaxFloat = float(belowFolder.split("_")[-1])
    print("Found below folder :", belowFolder)
    print("min Float value :", belowMinFloat)
    print("max Float value :", belowMaxFloat)

    if not os.path.exists(mainFolder + "material_decomposition/"):
        os.makedirs(mainFolder + "material_decomposition/")

    if not os.path.exists(mainFolder + radix + "/"):
        os.makedirs(mainFolder + radix + "material_decomposition/")

    if not os.path.exists(mainFolder + radix + "material_decomposition/" + "/Au_decomposition"):
        os.makedirs(mainFolder + radix + "material_decomposition/" + "/Au_decomposition")
    if not os.path.exists(mainFolder + radix + "material_decomposition/" + "/I_decomposition"):
        os.makedirs(mainFolder + radix + "material_decomposition/" + "/I_decomposition")
    if not os.path.exists(mainFolder + radix + "material_decomposition/" + "/Water_decomposition"):
        os.makedirs(mainFolder + radix + "material_decomposition/" + "/Water_decomposition")

    for fileNameIndex in range(0, min(len(aboveFileNames), len(belowFileNames))):
        belowImage = input_output.open_image(belowFileNames[fileNameIndex])
        aboveImage = input_output.open_image(aboveFileNames[fileNameIndex])

        aboveImage = resampling.conversion_from_uint16_to_float32(aboveImage, aboveMinFloat, aboveMaxFloat)

        belowImage = resampling.conversion_from_uint16_to_float32(belowImage, belowMinFloat, belowMaxFloat)

        if mainMaterial == "Au":
            AuImage, IImage, WaterImage = three_materials_decomposition(aboveImage, belowImage, "Au", "I")
        else:
            IImage, AuImage, WaterImage = three_materials_decomposition(aboveImage, belowImage, "I", "Au")

        percent = "{0:.1f}".format(100 * (fileNameIndex / float(min(len(aboveFileNames), len(belowFileNames)) - 1)))
        filled_length = int(100 * fileNameIndex // min(len(aboveFileNames), len(belowFileNames)) - 1)
        bar = '#' * filled_length + '-' * (100 - filled_length)
        print("\r |" + bar + "| " + percent + "% ", end="\r")
        # Print New Line on Complete
        if fileNameIndex == min(len(aboveFileNames), len(belowFileNames)) - 1:
            print()

        textSlice = '%4.4d' % fileNameIndex

        input_output.save_edf_image(AuImage,
                                    mainFolder + radix + "material_decomposition/" + "/Au_decomposition/"
                                    + radix + "Au_decomposition_" + textSlice + '.edf')
        input_output.save_edf_image(IImage,
                                    mainFolder + radix + "material_decomposition/" + "/I_decomposition/"
                                    + radix + "I_decomposition_" + textSlice + '.edf')
        input_output.save_edf_image(WaterImage,
                                    mainFolder + radix + "material_decomposition/" + "/Water_decomposition/"
                                    + radix + "Water_decomposition_" + textSlice + '.edf')"""
