""" Random Relu Features. """

import statistics

import numpy as np
from sklearn.neighbors import NearestNeighbors
from sklearn.utils import check_array, check_random_state
from sklearn.utils.validation import check_is_fitted

# Import the feature mapping base class
from MRCpy.phi import BasePhi


class RandomReLUPhi(BasePhi):
    """
    ReLU features 

    ReLU features are given by -

    .. math::   \max(w^t * (1/gamma,x), 0)

    where w is a vector(dimension d) of random weights uniformly distributed
    over a sphere of unit radius.

    Relu function is defined as -

    .. math::           f(x) = \max(0, x)

    Parameters
    ----------
    n_classes : int
        The number of classes in the dataset.

    fit_intercept : bool, default=True
            Whether to calculate the intercept.
            If set to false, no intercept will be used in calculations
            (i.e. data is expected to be already centered).

    gamma : {'scale', 'avg_ann', 'avg_ann_50', float} default = 'avg_ann_50'
        It defines the type of heuristic to be used
        to calculate the scaling parameter.

    n_components : int, default=300
        Number of Monte Carlo samples for the original features.
        Equals the dimensionality of the computed (mapped) feature space.

    random_state : int, RandomState instance, default=None
        Used to produce the random weights
        used for the approximation of the gaussian kernel.

    Attributes
    ----------
    random_weights_ : array-like of shape (n_features, n_components/2)
        The sampled basis.

    is_fitted_ : bool
        True if the feature mappings has learned its hyperparameters (if any)
        and the length of the feature mapping is set.

    len_ : int
        Defines the length of the feature mapping vector.

    References
    ----------
    [1] On the Approximation Properties of Random ReLU Features.
    Yitong Sun, Anna Gilbert and Ambuj Tewari.
    arXiv: Machine Learning.
    (https://arxiv.org/pdf/1810.04374.pdf)

    """

    def __init__(self, n_classes, fit_intercept=True, gamma='avg_ann_50',
                 n_components=300, random_state=None):

        # Call the base class init function.
        super().__init__(n_classes=n_classes, fit_intercept=fit_intercept)

        self.gamma = gamma
        self.n_components = n_components
        self.random_state = random_state

    def fit(self, X, Y=None):
        """
        Get the set of random weights for computing the features space.
        Also, compute the value of gamma hyperparameter
        if the value is not given.

        Parameters
        ----------
        X : array-like of shape (n_samples, n_dimensions)
            Unlabeled training instances
            used to learn the feature configurations.

        Y : array-like of shape (n_samples,), default=None
            This argument will never be used in this case.
            It is present for the consistency of signature of function
            among different feature mappings.

        Returns
        -------
        self :
            Fitted estimator

        """

        X = check_array(X, accept_sparse=True)

        d = X.shape[1]
        # Evaluate the gamma according to the gamma type given in self.gamma
        if self.gamma == 'scale':
            self.gamma_val = 1 / (d * X.var())

        elif self.gamma == 'avg_ann_50':
            self.gamma_val = self.rff_gamma(X)

        elif type(self.gamma) != str:
            self.gamma_val = self.gamma

        else:
            raise ValueError('Unexpected value for gamma ...')

        # Obtain the random weights uniformly distributed on
        # sphere of unit radius in dimension d.
        # Step 1 Generate samples distributed with unit variance
        #        in each dimension using the gaussian distribution.
        self.random_state = check_random_state(self.random_state)
        self.random_weights_ = \
            self.random_state.normal(0, 1, size=(d + 1, self.n_components))
        # Step 2 Normalize the samples so that they are on a unit sphere.
        self.random_weights_ = self.random_weights_ / \
            np.linalg.norm(self.random_weights_, axis=0)

        # Sets the length of the feature mapping
        super().fit(X, Y)

        return self

    def transform(self, X):
        """
        Compute the ReLu Random Features from the given instances.

        Parameters
        ----------
        X : array-like of shape (n_samples, n_dimensions)
            Unlabeled training instances.

        Returns
        -------
        X_feat : array-like of shape (n_samples, n_features)
            Transformed features from the given instances.

        """

        check_is_fitted(self, ["random_weights_", "is_fitted_"])
        X = check_array(X, accept_sparse=True)
        n = X.shape[0]

        # Adding scaling parameter
        X = np.hstack(([[1 / self.gamma_val]] * n, X))
        X_feat = X @ self.random_weights_

        # ReLu on the computed feature matrix
        X_feat[X_feat < 0] = 0

        return X_feat

    def heuristic_gamma(self, X, Y):

        """
        Compute the scale parameter for gaussian kernels using the heuristic -

                sigma = median{ {min ||x_i-x_j|| for j|y_j != +1 }
                                    for i|y_i != -1 }

        for two classes {+1, -1}. For multi-class, we use the same strategy
        by finding median of min norm value
        for each class against all other classes
        and then taking the average value of the median of all the classes.

        The heuristic calculates the value of sigma for gaussian kernels.
        So to find the gamma value
        for the kernel defined in our implementation,
        the following formula is used -
                gamma = 1/ (2 * sigma^2)

        Parameters
        ----------
        X : array-like of shape (n_samples, n_dimensions)
            Unlabeled instances.

        Y : array-like of shape (n_samples,)
            Labels corresponding to the instances.

        Returns
        -------
        gamma : float value
            Gamma value computed using the heuristic from the instances.

        """

        # List to store the median of min norm value for each class
        dist_x_i = list()

        n_classes = np.max(Y) + 1

        for i in range(n_classes):
            x_i = X[Y == i, :]
            x_not_i = X[Y != i, :]

            # Find the distance of each point of this class
            # with every other point of other class
            norm_vec = np.linalg.norm(np.tile(x_not_i, (x_i.shape[0], 1)) -
                                      np.repeat(x_i, x_not_i.shape[0],
                                                axis=0), axis=1)
            dist_mat = np.reshape(norm_vec, (x_not_i.shape[0], x_i.shape[0]))

            # Find the min distance for each point and take the median distance
            minDist_x_i = np.min(dist_mat, axis=1)
            dist_x_i.append(statistics.median(minDist_x_i))

        sigma = np.average(dist_x_i)

        # Evaluate gamma
        gamma = 1 / (2 * sigma * sigma)

        return gamma

    def rff_gamma(self, X):

        """
        Function to find the scale parameter
        for random fourier features obtained from
        gaussian kernels using the heuristic given in -

                "Compact Nonlinear Maps and Circulant Extensions"

        The heuristic to calculate the sigma states that
        it is a value that is obtained from
        the average distance to the 50th nearest neighbour estimated
        from 1000 samples of the dataset.

        Gamma value is given by -
                gamma = 1/ (2 * sigma^2)

        Parameters
        ----------
        X : array-like of shape (n_samples, n_dimensions)
            Unlabeled instances.

        Returns
        -------
        gamma : float value
            Gamma value computed using the heuristic from the instances.

        References
        ----------
        [1] Compact Nonlinear Maps and Circulant Extensions
        Felix X. Yu, Sanjiv Kumar, Henry Rowley and Shih-Fu Chang
        (https://arxiv.org/pdf/1503.03893.pdf)

        """
        if X.shape[0]<50:
            neighbour_ind = X.shape[0]-2
        else:
            neighbour_ind = 50

        # Find the nearest neighbors
        nbrs = NearestNeighbors(n_neighbors=(neighbour_ind + 1),
                                algorithm='ball_tree').fit(X)
        distances, indices = nbrs.kneighbors(X)

        # Compute the average distance to the 50th nearest neighbour
        sigma = np.average(distances[:, neighbour_ind])

        return 1 / (2 * sigma * sigma)
