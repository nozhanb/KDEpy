#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb  4 10:52:17 2018

@author: tommy
"""
import pytest
import numpy as np

try:
    import cutils
    _use_Cython = True
except ModuleNotFoundError:
    _use_Cython = False


def linbin_cython(data, grid_points, weights=None):
    """
    Linear binning using Cython. Assigns weights to grid points from data.
    
    from KDEpy.binning import linbin_cython
    import numpy as np
    data = np.random.randn(10**7)
    %timeit linbin_cython(data, np.linspace(-8,8, num=2**10))
    -> 547 ms ± 8.32 ms

    Time on 1 million data points: 30 ms
    Time on 10 million data points: 290 ms
    Time on 100 million data points: 2.86 s
    """
    # Convert the data and grid points
    data = np.asarray_chkfinite(data, dtype=np.float)
    grid_points = np.asarray_chkfinite(grid_points, dtype=np.float)

    # Verify that the grid is equidistant
    diffs = np.diff(grid_points)
    assert np.allclose(np.ones_like(diffs) * diffs[0], diffs)

    if weights is not None:
        weights = np.asarray_chkfinite(weights, dtype=np.float)
        weights = weights / np.sum(weights)

    if (weights is not None) and (len(data) != len(weights)):
        raise ValueError('Length of data must match length of weights.')

    # Transform the data
    min_grid = np.min(grid_points)
    max_grid = np.max(grid_points)
    num_intervals = len(grid_points) - 1  # Number of intervals
    dx = (max_grid - min_grid) / num_intervals
    transformed_data = (data - min_grid) / dx

    result = np.asfarray(np.zeros(len(grid_points) + 1))

    if weights is None:
        result = cutils.iterate_data(transformed_data, result)
        return np.asfarray(result[:-1]) / len(transformed_data)
    else:
        res = cutils.iterate_data_weighted(transformed_data, weights, result)
        return np.asfarray(res[:-1])


def linbin_numpy(data, grid_points, weights=None):
    """
    Linear binning using NumPy. Assigns weights to grid points from data.

    This function is fast for data sets upto approximately 1-10 million,
    it uses vectorized NumPy functions to perform linear binning.

    Time on 1 million data points: 79.6 ms ± 1.01 ms
    Time on 10 million data points: 879 ms ± 4.55 ms
    Time on 100 million data points: 10.3 s ± 663 ms


    Examples
    --------
    >>> data = np.array([2, 2.5, 3, 4])
    >>> linbin_numpy(data, np.arange(6), weights=None)
    array([0.   , 0.   , 0.375, 0.375, 0.25 , 0.   ])
    >>> linbin_numpy(data, np.arange(6), weights=np.arange(1, 5))
    array([0. , 0. , 0.2, 0.4, 0.4, 0. ])
    >>> data = np.array([2, 2.5, 3, 4])
    >>> linbin_numpy(data, np.arange(1, 7), weights=None)
    array([0.   , 0.375, 0.375, 0.25 , 0.   , 0.   ])
    """
    # Convert the data and grid points
    data = np.asarray_chkfinite(data, dtype=np.float)
    grid_points = np.asarray_chkfinite(grid_points, dtype=np.float)

    # Verify that the grid is equidistant
    diffs = np.diff(grid_points)
    assert np.allclose(np.ones_like(diffs) * diffs[0], diffs)

    if weights is None:
        weights = np.ones_like(data)

    weights = np.asarray_chkfinite(weights, dtype=np.float)
    weights = weights / np.sum(weights)

    if not len(data) == len(weights):
        raise ValueError('Length of data must match length of weights.')

    # Transform the data
    min_grid = np.min(grid_points)
    max_grid = np.max(grid_points)
    num_intervals = len(grid_points) - 1  # Number of intervals
    dx = (max_grid - min_grid) / num_intervals
    transformed_data = (data - min_grid) / dx

    # Compute the integral and fractional part of the data
    # The integral part is used for lookups, the fractional part is used
    # to weight the data
    num_intervals = len(grid_points) - 1  # Number of intervals
    fractional, integral = np.modf(transformed_data)
    integral = integral.astype(np.int)

    # Sort the integral values, and the fractional data and weights by
    # the same key. This lets us use binary search, which is faster
    # than using a mask in the the loop below
    indices_sorted = np.argsort(integral)
    integral = integral[indices_sorted]
    fractional = fractional[indices_sorted]
    weights = weights[indices_sorted]

    # Pre-compute these products, as they are used in the loop many times
    frac_weights = fractional * weights
    neg_frac_weights = weights - frac_weights

    # If the data is not a subset of the grid, the integral values will be
    # outside of the grid. To solve the problem, we filter these values away
    unique_integrals = np.unique(integral)
    unique_integrals = unique_integrals[(unique_integrals >= 0) &
                                        (unique_integrals <= len(grid_points))]

    result = np.asfarray(np.zeros(len(grid_points) + 1))
    for grid_point in unique_integrals:

        # Use binary search to find indices for the grid point
        # Then sum the data assigned to that grid point
        low_index = np.searchsorted(integral, grid_point, side='left')
        high_index = np.searchsorted(integral, grid_point, side='right')
        result[grid_point] += neg_frac_weights[low_index:high_index].sum()
        result[grid_point + 1] += frac_weights[low_index:high_index].sum()

    return result[:-1]


def linear_binning(data, grid_points, weights=None):
    """
    Compute binning by setting a linear grid and weighting points linearily
    by their distance to the grid points. In addition, weight asssociated with
    data points may be passed.

    Parameters
    ----------
    data
        The data points.
    num_points
        The number of points in the grid.
    weights
        The weights.

    Returns
    -------
    (grid, data)
        Data weighted at each grid point.

    Examples
    --------
    >>> data = [1, 1.5, 1.5, 2, 2.8, 3]
    >>> grid_points = [1, 2, 3]
    >>> data = linear_binning(data, grid_points)
    >>> np.allclose(data, np.array([0.33333, 0.36667, 0.3]))
    True
    """
    if _use_Cython:
        return linbin_cython(data, grid_points, weights=None)
    else:
        return linbin_numpy(data, grid_points, weights=None)


if __name__ == "__main__":
    # --durations=10  <- May be used to show potentially slow tests
    pytest.main(args=['.', '--doctest-modules', '-v', '--capture=sys'])
