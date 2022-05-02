import argparse
import json
import os

import h5py
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error

import sysid.utils as utils


def main():
    parser = argparse.ArgumentParser(description='Evaluate model')
    parser.add_argument('--mode', action='store', help='either "validation" or "test"')
    parser.add_argument('model', help='model')
    args = parser.parse_args()

    model_name = args.model
    mode = args.mode
    if mode not in {'validation', 'test'}:
        raise ValueError('Argument to --mode must be either "validation" or "test"')

    with open(os.environ['CONFIGURATION'], mode='r') as f:
        config = json.load(f)

    window_size = config['window']
    horizon_size = config['horizon']
    state_names = config['state_names']

    test_directory = os.environ['RESULT_DIRECTORY']
    test_file_path = os.path.join(
        test_directory, model_name, f'{mode}-w_{window_size}-h_{horizon_size}.hdf5')
    if mode == 'test':
        scores_file_path = os.path.join(
            test_directory, model_name, f'scores-w_{window_size}-h_{horizon_size}.hdf5')
        readable_scores_file_path = os.path.join(
            test_directory, model_name, f'scores-w_{window_size}-h_{horizon_size}.json')
    else:
        scores_file_path = os.path.join(
            test_directory, model_name, f'validation_scores-w_{window_size}-h_{horizon_size}.hdf5')
        readable_scores_file_path = os.path.join(
            test_directory, model_name, f'validation_scores-w_{window_size}-h_{horizon_size}.json')

    pred = []
    true = []
    steps = []

    # Load predicted and true states for each multi-step sequence.
    with h5py.File(test_file_path, 'r') as f:
        file_names = [fn.decode('UTF-8') for fn in f['file_names'][:].tolist()]
        for i in range(len(file_names)):
            pred.append(f['predicted'][str(i)][:])
            true.append(f['true'][str(i)][:])
            steps.append(f['predicted'][str(i)][:].shape[0])

    score_functions = (
        ('mse', lambda t, p: mean_squared_error(t, p, multioutput='raw_values')),
        ('rmse', lambda t, p: np.sqrt(mean_squared_error(t, p, multioutput='raw_values'))),
        ('rmse-std', lambda t, p: np.std(np.sqrt(mean_squared_error(t, p, multioutput='raw_values')),  axis=0)),
        ('mae', lambda t, p: mean_absolute_error(t, p, multioutput='raw_values')),
        ('d1', utils.index_of_agreement),
        ('mae_grad', utils.mean_absolute_gradient_error),
        ('mse_grad', utils.mean_squared_gradient_error),
        ('fourier_error', utils.fourier_amplitude_error)
    )

    scores = dict()
    for name, fct in score_functions:
        scores[name] = utils.score_on_sequence(true, pred, fct)

    with h5py.File(scores_file_path, 'w') as f:
        f.attrs['state_names'] = np.array(list(map(np.string_, state_names)))
        f.create_dataset('file_names', data=np.array(list(map(np.string_, file_names))))
        f.create_dataset('steps', data=np.array(steps))

        for name, _ in score_functions:
            f.create_dataset(name, data=scores[name])

    average_scores = dict()
    for name, _ in score_functions:
        # 1/60 * sum_1^60 RMSE
        average_scores[name] = np.average(scores[name], weights=steps, axis=0).tolist()

    with open(readable_scores_file_path, mode='w') as f:
        obj = dict()
        obj['scores'] = average_scores
        obj['state_names'] = state_names
        json.dump(obj, f)


if __name__ == '__main__':
    main()
