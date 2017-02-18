""" Script to test descriptors for the ML model. Takes a database of candidates
    from with target values set in atoms.info['key_value_pairs'][key] and
    returns the correlation of descriptors with target values.
"""
from __future__ import print_function

import numpy as np

from ase.ga.data import DataConnection
from atoml.data_setup import get_unique, get_train
from atoml.fingerprint_setup import return_fpv, normalize
from atoml.feature_select import (sure_independence_screening, iterative_sis,
                                  pca)
from atoml.particle_fingerprint import ParticleFingerprintGenerator
from atoml.standard_fingerprint import StandardFingerprintGenerator
from atoml.predict import FitnessPrediction


# Connect database generated by a GA search.
db = DataConnection('gadb.db')

# Get all relaxed candidates from the db file.
print('Getting candidates from the database')
all_cand = db.get_all_relaxed_candidates(use_extinct=False)

# Setup the test and training datasets.
testset = get_unique(candidates=all_cand, testsize=500, key='raw_score')
trainset = get_train(candidates=all_cand, trainsize=500,
                     taken_cand=testset['taken'], key='raw_score')

# Get the list of fingerprint vectors and normalize them.
print('Getting the fingerprint vectors')
fpv = ParticleFingerprintGenerator(get_nl=False, max_bonds=13)
std = StandardFingerprintGenerator()
test_fp = return_fpv(testset['candidates'], [fpv.nearestneighbour_fpv,
                                             fpv.bond_count_fpv,
                                             fpv.distribution_fpv,
                                             fpv.rdf_fpv,
                                             std.mass_fpv,
                                             std.eigenspectrum_fpv,
                                             std.distance_fpv])
train_fp = return_fpv(trainset['candidates'], [fpv.nearestneighbour_fpv,
                                               fpv.bond_count_fpv,
                                               fpv.distribution_fpv,
                                               fpv.rdf_fpv,
                                               std.mass_fpv,
                                               std.eigenspectrum_fpv,
                                               std.distance_fpv])


def do_pred(ptrain_fp, ptest_fp):
    nfp = normalize(train=ptrain_fp, test=ptest_fp)
    print('Feature length:', len(nfp['train'][0]))

    # Set up the prediction routine.
    krr = FitnessPrediction(ktype='gaussian',
                            kwidth=0.5,
                            regularization=0.001)

    # Do the predictions.
    cvm = krr.get_covariance(train_fp=nfp['train'])
    cinv = np.linalg.inv(cvm)
    pred = krr.get_predictions(train_fp=nfp['train'],
                               test_fp=nfp['test'],
                               cinv=cinv,
                               train_target=trainset['target'],
                               test_target=testset['target'],
                               get_validation_error=True,
                               get_training_error=True)

    # Print the error associated with the predictions.
    print('Training error:', pred['training_rmse']['average'])
    print('Model error:', pred['validation_rmse']['average'])


for i in range(len(train_fp)):
    pca_r = pca(components=i+1, train_fpv=train_fp, test_fpv=test_fp)
    print('PREDICTION FOR', i+1, 'COMPONENTS')
    do_pred(ptrain_fp=pca_r['train_fpv'], ptest_fp=pca_r['test_fpv'])

# Get base predictions.
print('Base Predictions')
do_pred(ptrain_fp=train_fp, ptest_fp=test_fp)

# Get correlation for descriptors from SIS.
print('Getting descriptor correlation')
sis = sure_independence_screening(target=trainset['target'],
                                  train_fpv=train_fp, size=40)
print('sis features:', sis['accepted'])
print('sis correlation:', sis['correlation'])
sis_test_fp = np.delete(test_fp, sis['rejected'], 1)
sis_train_fp = np.delete(train_fp, sis['rejected'], 1)
do_pred(ptrain_fp=sis_train_fp, ptest_fp=sis_test_fp)

it_sis = iterative_sis(target=trainset['target'], train_fpv=train_fp,
                       size=40, step=4)
print('iterative_sis features:', it_sis['accepted'])
print('iterative_sis correlation:', it_sis['correlation'])
it_sis_test_fp = np.delete(test_fp, it_sis['rejected'], 1)
it_sis_train_fp = np.delete(train_fp, it_sis['rejected'], 1)
do_pred(ptrain_fp=it_sis_train_fp, ptest_fp=it_sis_test_fp)

cut_sis = iterative_sis(target=trainset['target'], train_fpv=train_fp,
                        size=40, step=4, cutoff=1.e-2)
print('iterative_sis + cutoff features:', cut_sis['accepted'])
print('iterative_sis + cutoff correlation:', cut_sis['correlation'])
cut_sis_test_fp = np.delete(test_fp, cut_sis['rejected'], 1)
cut_sis_train_fp = np.delete(train_fp, cut_sis['rejected'], 1)
do_pred(ptrain_fp=cut_sis_train_fp, ptest_fp=cut_sis_test_fp)
