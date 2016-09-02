"""
facegen/generate.py

Methods for generating faces.

"""

import os
import yaml

import numpy as np
import scipy.misc

from .instance import Emotion


# TODO: Get number of identities dynamically from the loaded model.
NUM_ID = 57


class GenParser:
    """
    Class to parse and create inputs based on the parameters in a yaml file.
    """

    # Default parameters to use
    DefaultParams = {
        'mode'        : 'single',
        'constrained' : True,
        'id'          : None,
        'em'          : None,
        'or'          : None,
        'id_scale'    : 1.0,
        'id_step'     : 0.1,
        'id_min'      : None,
        'id_max'      : None,
        'em_scale'    : 1.0,
        'em_step'     : 0.1,
        'em_min'      : None,
        'em_max'      : None,
        'or_scale'    : 1.0,
        'or_step'     : 0.1,
        'or_min'      : None,
        'or_max'      : None,
        'num_images'  : '1s',
        'fps'         : 30,
        'keyframes'   : None,
    }

    def __init__(self, yaml_path):
        self.yaml_file = open(yaml_path, 'r')

        self.modes = {
            'single'     : self.mode_single,
            'random'     : self.mode_random,
            'drunk'      : self.mode_drunk,
            'interpolate': self.mode_interpolate,
        }

    def __del__(self):
        self.yaml_file.close()


    # Methods for generating inputs by mode

    def mode_single(self, params):
        """
        """

        if params['id'] is None:
            params['id'] = 0
        if params['em'] is None:
            params['em'] = 'neutral'
        if params['or'] is None:
            params['or'] = 0

        inputs = {
            'identity': np.empty((1, NUM_ID)),
            'emotion': np.empty((1, Emotion.length())),
            'orientation': np.empty((1, 2)),
        }

        inputs['identity'][0,:] = self.identity_vector(params['id'], params)
        inputs['emotion'][0,:] = self.emotion_vector(params['em'], params)
        inputs['orientation'][0,:] = self.orientation_vector(params['or'], params)

        return inputs


    def mode_random(self, params):
        """
        """

        num_images = self.num_frames(params['num_images'], params)

        inputs = {
            'identity':    np.empty((num_images, NUM_ID)),
            'emotion':     np.empty((num_images, Emotion.length())),
            'orientation': np.empty((num_images, 2)),
        }

        for i in range(0, num_images):
            if params['id'] is None:
                inputs['identity'][i,:] = self.random_identity(params)
            else:
                inputs['identity'][i,:] = self.identity_vector(params['id'], params)

            if params['em'] is None:
                inputs['emotion'][i,:] = self.random_emotion(params)
            else:
                inputs['emotion'][i,:] = self.emotion_vector(params['em'], params)

            if params['or'] is None:
                inputs['orientation'][i,:], _ = self.random_orientation(params)
            else:
                inputs['orientation'][i,:] = self.orientation_vector(params['or'], params)

        return inputs


    def mode_drunk(self, params):
        """
        """

        num_images = self.num_frames(params['num_images'], params)

        inputs = {
            'identity':    np.empty((num_images, NUM_ID)),
            'emotion':     np.empty((num_images, Emotion.length())),
            'orientation': np.empty((num_images, 2)),
        }

        last_id, last_em, last_or = None, None, None

        for i in range(0, num_images):
            if params['id'] is None:
                inputs['identity'][i,:] = self.random_identity(params, last_id)
                last_id = inputs['identity'][i,:]
            else:
                inputs['identity'][i,:] = self.identity_vector(params['id'], params)

            if params['em'] is None:
                inputs['emotion'][i,:] = self.random_emotion(params, last_em)
                last_em = inputs['emotion'][i,:]
            else:
                inputs['emotion'][i,:] = self.emotion_vector(params['em'], params)

            if params['or'] is None:
                inputs['orientation'][i,:], last_or = self.random_orientation(params, last_or)
            else:
                inputs['orientation'][i,:] = self.orientation_vector(params['or'], params)

        return inputs


    def mode_interpolate(self, params):
        """
        """

        if params['id'] is None:
            params['id'] = 0
        if params['em'] is None:
            params['em'] = 'neutral'
        if params['or'] is None:
            params['or'] = 0

        raise RuntimeError("Mode 'interpolate' is not implemented")


    # Helper methods

    def num_frames(self, val, params):
        """ Gets the number of frames for a value. """

        if isinstance(val, int):
            return val
        elif isinstance(val, str):
            if val.endswith('s'):
                return int( float(val[:-1]) * params['fps'] )
            else:
                raise RuntimeError("Length '{}' not understood".format(val))
        else:
            raise RuntimeError("Length '{}' not understood".format(val))


    def identity_vector(self, value, params):
        """ Create an identity vector for a provided value. """

        if isinstance(value, str):
            if '+' not in value:
                raise RuntimeError("Identity '{}' not understood".format(value))

            try:
                values = [int(x) for x in value.split('+')]
            except:
                raise RuntimeError("Identity '{}' not understood".format(value))
        elif isinstance(value, int):
            values = [value]
        else:
            raise RuntimeError("Identity '{}' not understood".format(value))

        vec = np.zeros((NUM_ID,))
        for val in values:
            if val < 0 or NUM_ID <= val:
                raise RuntimeError("Identity '{}' invalid".format(val))
            vec[val] += 1.0

        return self.constrain(vec, params['constrained'], params['id_scale'],
                params['id_min'], params['id_max'])


    def emotion_vector(self, value, params):
        """ Create an emotion vector for a provided value. """

        if not isinstance(value, str):
            raise RuntimeError("Emotion '{}' not understood".format(value))

        if '+' in value:
            values = value.split('+')
        else:
            values = [value]

        vec = np.zeros((Emotion.length(),))
        for emotion in values:
            try:
                vec += getattr(Emotion, emotion)
            except AttributeError:
                raise RuntimeError("Emotion '{}' is invalid".format(emotion))

        return self.constrain(vec, params['constrained'], params['em_scale'],
                params['em_min'], params['em_max'])


    def orientation_vector(self, value, params):
        """ Create an orientation vector for a provided value. """

        if isinstance(value, int) or isinstance(value, float):
            value = np.deg2rad(value)
            return np.array([np.sin(value), np.cos(value)])

        elif isinstance(value, str):
            if params['constrained']:
                raise RuntimeError("Cannot manually set orientation vector "
                                   "values when constrained is set to True")

            values = value.split()
            if len(values) != 2:
                raise RuntimeError("Orientation '{}' not understood".format(value))

            vec = np.empty((2,))
            try:
                x[0] = float(values[0])
                x[1] = float(values[1])
            except ValueError:
                raise RuntimeError("Orientation '{}' not understood".format(value))

            return vec
        else:
            raise RuntimeError("Orientation '{}' not understood".format(value))


    def random_identity(self, params, start=None):
        """ Create a random identity vector. """

        step = params['id_step']

        if start is None:
            vec = np.random.rand(NUM_ID)
        else:
            vec = start + (2*step*np.random.rand(NUM_ID)-step)

        return self.constrain(vec, params['constrained'], params['id_scale'],
                params['id_min'], params['id_max'])


    def random_emotion(self, params, start=None):
        """ Create a random emotion vector. """

        step = params['em_step']

        if start is None:
            vec = np.random.rand(Emotion.length())
        else:
            vec = start + (2*step*np.random.rand(Emotion.length())-step)

        return self.constrain(vec, params['constrained'], params['em_scale'],
                params['em_min'], params['em_max'])


    def random_orientation(self, params, start=None):
        """ Create a random orientation vector. """

        step = params['or_step']

        if params['constrained']:
            if start is None:
                angle = 180*np.random.rand() - 90
            else:
                angle = start + step * (180*np.random.rand()-90)
            rad = np.deg2rad(angle)

            # Return the angle as a second argument so the caller can grab it
            # in case it's in the drunk mode
            return np.array([np.sin(rad), np.cos(rad)]), angle
        else:
            if start is None:
                vec = np.random.rand(2)
            else:
                vec = start + (2*step*np.random.rand(2)-step)

            vec = self.constrain(vec, params['constrained'], params['or_scale'],
                    params['or_min'], params['or_max'])

            # Return the vector twice so it behaves the same as constrained
            return vec, vec


    def constrain(self, vec, constrained, scale, vec_min, vec_max):
        """ Constrains the emotion vector based on params. """

        if constrained:
            vec = vec / np.linalg.norm(vec)

        if scale is not None:
            vec = vec * scale

        if vec_min is not None and vec_max is not None:
            vec = np.clip(vec, vec_min, vec_max)

        return vec


    # Main parsing method

    def parse(self):
        """
        Parses the yaml file and creates input vectors to use with the model.
        """

        self.yaml_file.seek(0)

        yaml_params = yaml.load(self.yaml_file)

        params = GenParser.DefaultParams

        for field in params.keys():
            if field in yaml_params:
                params[field] = yaml_params[field]

        fn = None
        try:
            fn = self.modes[ params['mode'] ]
        except KeyError:
            raise RuntimeError("Mode '{}' is invalid".format(params['mode']))

        return fn(params)


def generate_from_yaml(yaml_path, model_path, output_dir, batch_size=32):
    """
    """

    parser = GenParser(yaml_path)

    try:
        inputs = parser.parse()
    except RuntimeError as e:
        print("Error: Unable to parse '{}'. Encountered exception:".format(yaml_path))
        print(e)
        return

    from keras import backend as K
    from keras.models import load_model

    print("Loading model...")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    else:
        raise RuntimeError("Directory '{}' exists. Cowardly refusing to continue."
            .format(output_dir))

    model = load_model(model_path)

    print("Generating images...")

    gen = model.predict(inputs, batch_size=batch_size)

    print("Writing to '{}'...".format(output_dir))

    for i in range(0, gen.shape[0]):
        if K.image_dim_ordering() == 'th':
            image = np.empty(gen.shape[2:]+(3,))
            for x in range(0, 3):
                image[:,:,x] = gen[i,x,:,:]
        else:
            image = gen[i,:,:,:]
        image = np.array(255*np.clip(image,0,1), dtype=np.uint8)
        file_path = os.path.join(output_dir, '{:05}.png'.format(i))
        scipy.misc.imsave(file_path, image)

