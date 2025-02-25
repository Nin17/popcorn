import numpy as np

# -- registration library --
import SimpleITK as Sitk

# -- basic math functions --
import math

# -- 2D Convex Hull function --
from skimage.measure import label, regionprops


def sum_list_of_vectors(list_of_vectors):
    """sums all the vectors of a list

    Args:
        list_of_vectors (list[numpy.ndarray]): input list

    Returns:
        (numpy.ndarray) resulting vector
    """
    final_vector = np.zeros(list_of_vectors[0].shape)
    for vector in list_of_vectors:
        final_vector += vector

    return final_vector


def apply_2d_rotation_to_a_vector(vector, angle):
    """applies a 2d rotation to a vector depending on an input angle (anticlockwise)
    Args:
        vector (numpy.ndarray): input numpy vector
        angle (float): angle in degrees

    Returns:
        rotated vector
    """
    c = math.cos(float(angle))
    s = math.sin(float(angle))

    return np.array([vector[0] * c - vector[1] * s,
                     vector[0] * s + vector[1] * c])


def compute_2d_rotation(image, angle, interpolator_type="linear"):
    """computes a 2d rotation on an image based on an angle around axis z

    Args:
        image (numpy.ndarray):   input image
        angle (float):           angle
        interpolator_type (str): type of interpolator (linear or nearest neighbor)

    Returns:
        (numpy.ndarray) rotated image
    """

    image_itk = Sitk.GetImageFromArray(image)
    tx = Sitk.AffineTransform(image_itk.GetDimension())

    c = math.cos(float(angle))
    s = math.sin(float(angle))
    tx.SetMatrix((c, s, 0,
                  -s, c, 0,
                  0, 0, 1))

    # We use the center of the image to apply a 2D rotation
    tx.SetCenter((image.shape[2] / 2, image.shape[1] / 2, 0))

    if interpolator_type == "linear":
        interpolator = Sitk.sitkLinear
    else:
        interpolator = Sitk.sitkNearestNeighbor

    # We apply the rotation to the image
    image_itk = Sitk.Resample(image_itk, tx, interpolator, 0.0, image_itk.GetPixelIDValue())

    return Sitk.GetArrayFromImage(image_itk)


def calculate_rotation_matrix_between_3d_vectors(moving_vector, ref_vector):
    """computes the rotation matrix in order to align moving_vector on ref_vector (x, y, z)

    Args:
        moving_vector (numpy.ndarray): vector we're aligning
        ref_vector    (numpy.ndarray): vector we're aligning on

    Returns:
        (numpy.ndarray) rotation matrix
    """
    # We normalize the two vectors
    moving_vector = moving_vector / np.linalg.norm(moving_vector)
    ref_vector = ref_vector / np.linalg.norm(ref_vector)

    scalar = np.dot(moving_vector, ref_vector)  # cos = scalar product
    cross = np.cross(moving_vector, ref_vector)  # cross product between two vectors
    normalized = np.linalg.norm(cross)  # The normalized value of the cross product is the sinus

    # Rotation matrix calculation
    trans_matrix = np.array([[0, -cross[2], cross[1]], [cross[2], 0, -cross[0]], [-cross[1], cross[0], 0]])
    return (
            np.eye(3)
            + trans_matrix
            + trans_matrix.dot(trans_matrix) * ((1 - scalar) / (normalized ** 2))
    )


def compute_3d_rotation(image, rotation_matrix, center_of_rotation, translation=None, size_change=1.0):
    """computes rotation around a center_of_rotation based on a rotation matrix

    Args:
        image (numpy.ndarray):              input image
        rotation_matrix (numpy.ndarray):    rotation matrix
        center_of_rotation (numpy.ndarray): center of rotation [x, y, z]
        translation (numpy.ndarray):        3D translation in addition to the angular rotation
        size_change (float):                over/under 1.0 : image is enlarged/shrunken, equal to 1.0: same image size

    Returns:
        (numpy.ndarray) rotated image

    """
    # Image size reference
    ref_size_image = np.zeros((int(image.shape[0] * size_change), image.shape[1], image.shape[2]))

    # Conversion to simpleITK array
    ref_size_image_itk = Sitk.GetImageFromArray(ref_size_image)
    image_itk = Sitk.GetImageFromArray(image)

    # Type of transformation
    rotation_transformation = Sitk.AffineTransform(image_itk.GetDimension())

    # Rotation matrix
    rotation_transformation.SetMatrix((rotation_matrix[0][0], rotation_matrix[1][0], rotation_matrix[2][0],
                                       rotation_matrix[0][1], rotation_matrix[1][1], rotation_matrix[2][1],
                                       rotation_matrix[0][2], rotation_matrix[1][2], rotation_matrix[2][2]))

    if translation is not None:
        rotation_transformation.SetTranslation((float(translation[0]), float(translation[1]), float(translation[2])))

    # Center of rotation
    rotation_transformation.SetCenter((float(center_of_rotation[0]),
                                       float(center_of_rotation[1]),
                                       float(center_of_rotation[2])))

    # We apply the transformation previously parameterized
    image_itk = Sitk.Resample(image_itk, ref_size_image_itk, rotation_transformation, Sitk.sitkLinear, 0.0,
                              image_itk.GetPixelIDValue())

    # Conversion from itk image to numpy array
    image = Sitk.GetArrayFromImage(image_itk)

    return np.copy(image)


def retrieve_throat_centroid(mask):
    """Calculates the barycenter of a shape

    Args:
        mask (numpy.ndarray): 2D mask of a shape

    Returns:
        (numpy.ndarray)  barycenter of shape

    """
    label_img = label(mask)
    regions = regionprops(label_img)
    return regions[0].centroid


def count_the_needed_translation_for_black_slices(image):
    """looks at a rotated image in order to count the number of slices that become black.

    Args:
        image (numpy.ndarray): input rotated image

    Returns:
        (int) the number of slices that contain too much blackness (at the beginning/end)

    """
    nb_slice = 0
    front_offset = 0
    slice_of_image = image[nb_slice, :, :]

    while (slice_of_image == 0).sum() > slice_of_image.size * 0.5 and nb_slice < image.shape[0]:
        front_offset += 1
        slice_of_image = image[nb_slice, :, :]
        nb_slice += 1

    nb_slice = image.shape[0] - 1
    bottom_offset = 0
    slice_of_image = image[nb_slice, :, :]
    while (slice_of_image == 0).sum() > slice_of_image.size * 0.5 and nb_slice >= 0:
        bottom_offset += 1
        slice_of_image = image[nb_slice, :, :]
        nb_slice -= 1

    return front_offset, bottom_offset


def straight_triangle_rotation(image, skull, skull_bounding_box, barycenter_jaw_one, barycenter_jaw_two):
    """Uses the position of the jaws/cranial skull to make the rat straight (jaws at the bottom, skull at the top)

    Args:
        image (numpy.ndarray):              input image
        skull (numpy.ndarray):              mask of the segmented cranial skull
        skull_bounding_box (numpy.ndarray): skull bounding box
        barycenter_jaw_one (numpy.ndarray):    barycenter of the first jaw
        barycenter_jaw_two (numpy.ndarray):    barycenter of the second jaw

    Returns:
        (numpy.ndarray) rotated image

    """
    skull_center = [skull_bounding_box[0] + (skull_bounding_box[1] - skull_bounding_box[0]) / 2,
                    skull_bounding_box[2] + (skull_bounding_box[3] - skull_bounding_box[2]) / 2]

    if barycenter_jaw_one[0] < barycenter_jaw_two[0]:
        jaws_vector = np.array([barycenter_jaw_two[0] - barycenter_jaw_one[0],
                                barycenter_jaw_two[1] - barycenter_jaw_one[1]])
    else:
        jaws_vector = np.array([barycenter_jaw_one[0] - barycenter_jaw_two[0],
                                barycenter_jaw_one[1] - barycenter_jaw_two[1]])

    target_vector = np.array([np.linalg.norm(jaws_vector), 0])
    if jaws_vector[1] > 0:
        angle = -math.acos(np.dot(target_vector, jaws_vector) /
                           (np.linalg.norm(jaws_vector) * np.linalg.norm(target_vector)))
    else:
        angle = math.acos(np.dot(target_vector, jaws_vector) /
                          (np.linalg.norm(jaws_vector) * np.linalg.norm(target_vector)))

    skull_to_center_vector = np.array([skull_center[0] - image.shape[2] / 2,
                                       skull_center[1] - image.shape[1] / 2])
    new_skull_to_center_vector = apply_2d_rotation_to_a_vector(skull_to_center_vector, angle)

    jaw_one_to_center_vector = np.array([barycenter_jaw_one[0] - image.shape[2] / 2,
                                         barycenter_jaw_one[1] - image.shape[1] / 2])
    new_jaw_one_to_center_vector = apply_2d_rotation_to_a_vector(jaw_one_to_center_vector, angle)

    if new_jaw_one_to_center_vector[1] < new_skull_to_center_vector[1]:
        angle += math.pi

    resulting_image = compute_2d_rotation(image, angle, "linear")
    resulting_skull = compute_2d_rotation(skull, angle, "nearest")

    return np.copy(resulting_image), np.copy(resulting_skull), float(angle)


def straight_throat_rotation(image, throat_mask_img=None, direction_vector=None, throat_coordinates=None, manual=False):
    """ rotates the image based on the segmentation of the throat (so that is is aligned with a [0, 0, 1] vector)

    Args:
        image (numpy.ndarray):              input image
        throat_mask_img (numpy.ndarray):    throat segmentation result
        direction_vector (numpy.ndarray):   in case of manual rotation: direction vector of throat
        throat_coordinates (numpy.ndarray): in case of manual rotation: throat position on slice 0
        manual (bool):                      False: uses throat mask, True: uses input vector and throat coordinates

    Returns:
        (numpy.ndarray, numpy.ndarray, numpy.ndarray, int) the aligned image, the rotation matrix and the center
    of rotation plus the offset (caused by the rotation)

    TODO:
        better use/calculation of the offset + add some comments

    """

    if not manual:
        centroid_list = []
        vectors_list = []
        list_of_ys = []
        list_of_xs = []
        z_length = 0

        for nbSlice in range(throat_mask_img.shape[0]):
            z_length += 1
            nb_pixels_throat = np.sum(throat_mask_img[nbSlice, :, :])
            if nb_pixels_throat >= 1:
                centroid = retrieve_throat_centroid(throat_mask_img[nbSlice, :, :])
                centroid_list.append([centroid[0], centroid[1], nbSlice])
                if len(centroid_list) > 1:
                    vectors_list.append(np.array([centroid_list[-1][2] - centroid_list[-2][2],
                                                  centroid_list[-1][0] - centroid_list[-2][0],
                                                  centroid_list[-1][1] - centroid_list[-2][1]]))  # vector : [z, y, x]
                    list_of_ys.append(centroid_list[-1][0] - centroid_list[-2][0])
                    list_of_xs.append(centroid_list[-1][1] - centroid_list[-2][1])

                z_length = 0
        # print(centroid_list)
        list_of_ys.sort()
        list_of_xs.sort()
        # total_vector = sum_list_of_vectors(vectors_list)
        total_vector = [1, list_of_ys[len(list_of_ys) // 2], list_of_xs[len(list_of_xs) // 2]]
        # print(centroid_list)
        normalized_total_vector = total_vector / np.linalg.norm(total_vector)
        normalized_current_vector = vectors_list[0] / np.linalg.norm(vectors_list[0])
        for vector in vectors_list:
            normalized_current_vector = vector / np.linalg.norm(vector)
            # print(np.dot(normalized_total_vector, normalized_current_vector))
        while np.dot(normalized_total_vector, normalized_current_vector) < 0.92:
            del vectors_list[0]
            del centroid_list[0]
            del list_of_ys[0]
            del list_of_xs[0]
            # total_vector = sum_list_of_vectors(vectors_list)
            total_vector = [1, list_of_ys[len(list_of_ys) // 2], list_of_xs[len(list_of_xs) // 2]]
            normalized_total_vector = total_vector / np.linalg.norm(total_vector)
            normalized_current_vector = vectors_list[0] / np.linalg.norm(vectors_list[0])

        # total_vector = sum_list_of_vectors(vectors_list)
        total_vector = [1, list_of_ys[len(list_of_ys) // 2], list_of_xs[len(list_of_xs) // 2]]
        print(total_vector)
        normalized_total_vector = total_vector / np.linalg.norm(total_vector)
        normalized_current_vector = vectors_list[-1] / np.linalg.norm(vectors_list[-1])
        print(centroid_list)

        while np.dot(normalized_total_vector, normalized_current_vector) < 0.92:
            del vectors_list[-1]
            del centroid_list[-1]
            del list_of_ys[-1]
            del list_of_xs[-1]
            # total_vector = sum_list_of_vectors(vectors_list)
            total_vector = [1, list_of_ys[len(list_of_ys) // 2], list_of_xs[len(list_of_xs) // 2]]
            normalized_total_vector = total_vector / np.linalg.norm(total_vector)
            normalized_current_vector = vectors_list[-1] / np.linalg.norm(vectors_list[-1])

        direction_vector = np.flip(np.copy(normalized_total_vector))

        throat_coordinates = np.array([centroid_list[0][1], centroid_list[0][0], centroid_list[0][2]])  # [x, y]

    rotation_matrix = calculate_rotation_matrix_between_3d_vectors(direction_vector, np.array([0, 0, 1]))

    first_try_image = compute_3d_rotation(image, rotation_matrix, throat_coordinates, np.array([0, 0, 0]))
    first_front_offset, first_back_offset = count_the_needed_translation_for_black_slices(first_try_image)

    first_offset = (first_front_offset - first_back_offset) / 2

    second_try_image = compute_3d_rotation(image, rotation_matrix, throat_coordinates, np.array([0, 0, first_offset]))
    second_front_offset, second_back_offset = count_the_needed_translation_for_black_slices(second_try_image)

    final_offset = (second_front_offset - second_back_offset) / 2 + first_offset
    image = compute_3d_rotation(image, rotation_matrix, throat_coordinates, np.array([0, 0, final_offset]))

    return np.copy(image), rotation_matrix, throat_coordinates, final_offset


def symmetry_based_registration(image, skull, skull_bounding_box, throat_coordinates, number_of_iterations):
    """looks for the best rotation (around axis Z) making the skull symmetric

    Args:
        image (numpy.ndarray):              input image
        skull (numpy.ndarray):              input skull mask
        skull_bounding_box (numpy.ndarray): skull bounding box (2D)
        throat_coordinates (numpy.ndarray): coordinates of the segmented throat
        number_of_iterations (int):         how many angles we're trying to check (0.5 degrees step)

    Returns:
        (numpy.ndarray, numpy.ndarray) rotated image, rotated skull

    """

    # The bounding box needs to be centered on the throat coordinates
    if throat_coordinates[0] - skull_bounding_box[0] > skull_bounding_box[1] - throat_coordinates[0]:
        skull_bounding_box[1] = int(skull_bounding_box[0] + (throat_coordinates[0] - skull_bounding_box[0]) * 2)
    else:
        skull_bounding_box[0] = int(skull_bounding_box[1] - (skull_bounding_box[1] - throat_coordinates[0]) * 2)

    front_slices_to_delete, bottom_slices_to_delete = count_the_needed_translation_for_black_slices(image)
    if front_slices_to_delete + bottom_slices_to_delete < image.shape[0] / 2:
        image_to_study = image[front_slices_to_delete:image.shape[0] - bottom_slices_to_delete, :, :]
        skull_to_study = skull[front_slices_to_delete:image.shape[0] - bottom_slices_to_delete, :, :]
    else:
        image_to_study = np.copy(image)
        skull_to_study = np.copy(skull)

    cross_correlation_list = []
    diff = 1

    correct_angle = 0

    import popcorn.input_output as in_out

    in_out.save_tif_sequence(skull_to_study, "D:\\CT_md1217\\0873_05\\Au\\qsd\\")

    for increment, i in enumerate(range(number_of_iterations * 2)):

        angle = float(-number_of_iterations + i) / 180 * math.pi

        image_copy = np.copy(image_to_study)
        skull_copy = np.copy(skull_to_study)

        resulting_image = compute_2d_rotation(image_copy, angle, "linear")
        resulting_skull = compute_2d_rotation(skull_copy, angle, "nearest")

        cropped_image = resulting_image[:,
                        skull_bounding_box[2]:skull_bounding_box[3] + 1,
                        skull_bounding_box[0]:skull_bounding_box[1] + 1]
        flipped_image = cropped_image[:, :, ::-1]
        right_half_image = np.copy(flipped_image[:, :, int(flipped_image.shape[2] / 2):flipped_image.shape[2]])
        left_half_image = cropped_image[:, :, int(cropped_image.shape[2] / 2):cropped_image.shape[2]]

        cropped_skull = resulting_skull[:,
                        skull_bounding_box[2]:skull_bounding_box[3] + 1,
                        skull_bounding_box[0]:skull_bounding_box[1] + 1]
        flipped_skull = cropped_skull[:, :, ::-1]
        left_half_skull = np.copy(flipped_skull[:, :, int(flipped_skull.shape[2] / 2):flipped_skull.shape[2]])
        right_half_skull = cropped_skull[:, :, int(cropped_skull.shape[2] / 2):cropped_skull.shape[2]]

        left_half_skull[left_half_image == 0] = 0
        right_half_skull[right_half_image == 0] = 0

        number_of_zeros = np.zeros(left_half_skull.shape)
        number_of_zeros[right_half_image == 0] = 1
        number_of_zeros[left_half_image == 0] = 1
        subtraction = right_half_skull - left_half_skull
        count = len(subtraction[subtraction != 0])

        normalized_value = count / len(number_of_zeros[number_of_zeros == 0])

        cross_correlation_list.append(normalized_value)

        if diff > normalized_value:
            correct_angle = angle
            diff = normalized_value
    print(cross_correlation_list)
    image_copy = np.copy(image)
    skull_copy = np.copy(skull)

    print("Best angle :", correct_angle, "rad; in deg :", correct_angle / math.pi * 180, "°")

    resulting_image = compute_2d_rotation(image_copy, correct_angle, "linear")
    resulting_skull = compute_2d_rotation(skull_copy, correct_angle, "nearest")

    cropped_image = resulting_image[:,
                    skull_bounding_box[2]:skull_bounding_box[3] + 1,
                    skull_bounding_box[0]:skull_bounding_box[1] + 1]
    cropped_skull = resulting_skull[:,
                    skull_bounding_box[2]:skull_bounding_box[3] + 1,
                    skull_bounding_box[0]:skull_bounding_box[1] + 1]

    return np.copy(cropped_image), np.copy(cropped_skull), correct_angle


def command_iteration(method):
    """registration verbose output function

    Args:
        method (Sitk.ImageRegistrationMethod): registration method

    Returns: None

    """
    print("{0:3} = {1:10.8f}".format(method.GetOptimizerIteration(),
                                     method.GetMetricValue()))
    # print("Position = ", method.GetOptimizerPosition())


def command_iteration_widget(method, widget):
    """registration verbose output function

    Args:
        method (Sitk.ImageRegistrationMethod): registration method
        widget: QWidget
    Returns: None

    """

    output_txt = widget.output.toPlainText()

    output_txt = output_txt + "{0:3} = {1:10.8f}".format(method.GetOptimizerIteration(),
                                                         method.GetMetricValue()) + "\n"

    widget.my_signal.emit(output_txt)
    # widget.output.setText(output_txt)


def apply_rotation_pipeline(image, local_triangle_angle, rotation_matrix, local_throat_coordinates, binned_offset,
                            symmetry_angle):
    """applies all the rotations with the previously calculated angles/rotation matrix in order to align the rat with
    the z axis

    Args:
        image (numpy.ndarray):                    input image
        local_triangle_angle (float):             first function angle (in rad)
        rotation_matrix (numpy.ndarray):          second function rotation matrix
        local_throat_coordinates (numpy.ndarray): center of rotation for the rotation matrix
        binned_offset (int):                      translation offset after second rotation
        symmetry_angle (float):                   third function angle (in rad)

    Returns:
        (numpy.ndarray) transformed image
    """
    # Step 1
    print("Image initial size:", image.shape)
    image = compute_2d_rotation(image, local_triangle_angle, "linear")
    print("Image first size:", image.shape)
    # Step 2
    image = compute_3d_rotation(image, rotation_matrix, local_throat_coordinates,
                                translation=np.array([0, 0, binned_offset]), size_change=1.5)
    print("Image second size:", image.shape)
    # Step 3
    image = compute_2d_rotation(image, symmetry_angle, "linear")
    print("Image last size:", image.shape)

    return image


def set_transform_metric(method, metric):
    """Sets transformation metric for registration method

    Args:
        method (Sitk.ImageRegistrationMethod): registration computation method (sitk)
        metric (str):                          cc, ants, mi or msq

    Returns:
        (Sitk.ImageRegistrationMethod): registration computation method (sitk)
    """
    if metric == "cc":
        method.SetMetricAsCorrelation()
    elif metric == "ants":
        method.SetMetricAsANTSNeighborhoodCorrelation(2)
    elif metric == "mi":
        method.SetMetricAsJointHistogramMutualInformation()
    elif metric == "msq":
        method.SetMetricAsMeanSquares()

    return method


def set_registration_parameters(method, metric, transform_type="translation", ref_image=None, moving_image=None,
                                dimension=3):
    """defines sitk registration parameters based on given metric and transform type

    Args:
        method (Sitk.ImageRegistrationMethod): method used for registration computation
        metric (str):                          metric (cc, ants, mi or  msq)
        transform_type (str):                  translation or rotation
        ref_image (Sitk.GetImageFromArray):    ref image (sitk)
        moving_image (Sitk.GetImageFromArray): moving image (sitk)
        dimension (int):                       nb of dimensions

    Returns:
        (Sitk.ImageRegistrationMethod): defined method
    """

    # 1 ---> METRIC
    method = set_transform_metric(method, metric)

    # 2 ---> INTERPOLATOR
    method.SetInterpolator(Sitk.sitkLinear)

    # 3 ---> OPTIMIZER - 4 ---> TRANSFORMATION
    if transform_type == "translation":
        method.SetOptimizerAsRegularStepGradientDescent(learningRate=1.0,
                                                        minStep=1e-3,
                                                        numberOfIterations=100,
                                                        gradientMagnitudeTolerance=1e-8)

        # 4 ---> TRANSFORMATION
        transform = Sitk.TranslationTransform(dimension)
    else:
        method.SetOptimizerAsRegularStepGradientDescent(learningRate=1e-3,
                                                        minStep=1e-5,
                                                        numberOfIterations=50,
                                                        gradientMagnitudeTolerance=1e-6)

        # 4 ---> TRANSFORMATION
        transform = Sitk.CenteredTransformInitializer(ref_image,
                                                      moving_image,
                                                      Sitk.Euler3DTransform(),
                                                      Sitk.CenteredTransformInitializerFilter.GEOMETRY)

    method.SetInitialTransform(transform)

    return method


def registration_computation(moving_image, ref_image, transform_type="rotation", metric="cc", moving_mask=None,
                             ref_mask=None, verbose=False, widget=None):
    """computes transform between two images based on both metric and masks (optional)

    Args:
        moving_image (np.ndarray): image to register
        ref_image (np.ndarray):    reference image
        transform_type (str):      either rotation or transformation
        metric (str):              cc: cross-correlation, ants: ANTS-cc, mi: mutual information, msq: mean square diff
        moving_mask (np.ndarray):  mask-based registration image to register
        ref_mask (np.ndarray):     mask-based registration image to register on
        verbose (bool):            False: no output but the result, True: prints each iteration metric
        widget(QWidget):           Widget for then the fonction is call from gui
    Returns:
        (Sitk.Transform): computed transformation
    """
    # itk image conversion

    ref_image_itk = Sitk.GetImageFromArray(ref_image)
    moving_image_itk = Sitk.GetImageFromArray(moving_image)

    # Start of registration declaration
    registration_method = Sitk.ImageRegistrationMethod()

    # Setting needed parameters for registration
    registration_method = set_registration_parameters(registration_method, metric, transform_type, ref_image_itk,
                                                      moving_image_itk, dimension=moving_image.ndim)

    # Mask-based registration computation ?
    if moving_mask is not None and ref_mask is not None:
        registration_method.SetMetricFixedMask(Sitk.GetImageFromArray(ref_mask))
        registration_method.SetMetricMovingMask(Sitk.GetImageFromArray(moving_mask))

    # Registration execution
    if verbose:
        registration_method.AddCommand(Sitk.sitkIterationEvent, lambda: command_iteration(registration_method))

    if widget != None:
        registration_method.AddCommand(Sitk.sitkIterationEvent,
                                       lambda: command_iteration_widget(registration_method, widget))

    calculated_transform = registration_method.Execute(ref_image_itk, moving_image_itk)

    print("Transform :", calculated_transform.GetParameters())
    if widget != None:
        output_txt = widget.output.toPlainText()
        output_txt = output_txt + "Transform :" + str(calculated_transform.GetParameters()) + "\n"
        # widget.output.setText(output_txt)
    return calculated_transform


def apply_itk_transformation(image, transformation, interpolation_type="linear", ref_img=None):
    """applies SimpleITK transformation to an image using give interpolation type

    Args:
        image (numpy.ndarray):           input image
        transformation (Sitk.Transform): SimpleITK Transform
        interpolation_type (str):        interpolation type : can be "linear" or "nearest"
        ref_img (numpy.ndarray):         reference image (for shape information)

    Returns:
        (numpy.ndarray) transformed image
    """

    if interpolation_type == "linear":
        interpolator = Sitk.sitkLinear
    else:
        interpolator = Sitk.sitkNearestNeighbor
    image_itk = Sitk.GetImageFromArray(image)
    if ref_img is not None:
        ref_img_itk = Sitk.GetImageFromArray(ref_img)
        image_itk = Sitk.Resample(image_itk, ref_img_itk, transformation, interpolator, 0.0,
                                  image_itk.GetPixelIDValue())
    else:
        image_itk = Sitk.Resample(image_itk, transformation, interpolator, 0.0, image_itk.GetPixelIDValue())

    image = Sitk.GetArrayFromImage(image_itk)

    return np.copy(image)