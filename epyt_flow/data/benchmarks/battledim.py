"""
Module provides functions for loading BattLeDIM scenarios.
"""
from typing import Any
import os
import math
from datetime import datetime
import numpy as np
from scipy.sparse import bsr_array

from .battledim_data import START_TIME_TEST, START_TIME_TRAIN, LEAKS_CONFIG_TEST, \
    LEAKS_CONFIG_TRAIN
from ..networks import load_ltown, download_if_necessary
from ...simulation.events import AbruptLeakage, IncipientLeakage, Leakage
from ...simulation import ScenarioConfig
from ...simulation.scada import ScadaData
from ...utils import get_temp_folder


def parse_leak_config(start_time: str, leaks_config: str) -> list[Leakage]:
    leakages = []
    for leak in leaks_config.splitlines():
        # Parse entry
        items = [i.strip() for i in leak.split(",")]
        leaky_pipe_id = items[0]
        leak_start_time = int((datetime.strptime(items[1], "%Y-%m-%d %H:%M") - start_time)
                              .total_seconds())
        leak_end_time = int((datetime.strptime(items[2], "%Y-%m-%d %H:%M") - start_time)
                            .total_seconds())
        leak_diameter = float(items[3])
        leak_type = items[4]
        leak_peak_time = int((datetime.strptime(items[5], "%Y-%m-%d %H:%M") - start_time)
                             .total_seconds())

        # Create leak config
        if leak_type == "incipient":
            leak = IncipientLeakage(link_id=leaky_pipe_id, diameter=leak_diameter,
                                    start_time=leak_start_time, end_time=leak_end_time,
                                    peak_time=leak_peak_time)
        elif leak_type == "abrupt":
            leak = AbruptLeakage(link_id=leaky_pipe_id, diameter=leak_diameter,
                                 start_time=leak_start_time, end_time=leak_end_time)

        leakages.append(leak)

    return leakages


def load_battledim_data(test_scenario: bool, download_dir: str = None, return_X_y: bool = False,
                        return_leak_locations: bool = False) -> list[Any]:
    """
    Loads the simulated BattLeDIM benchmark scenario.

    .. warning::

        A large file (approx. 4GB) will be downloaded and loaded into memory --
        this might take some time.

    Parameters
    ----------
    test_scenario : `bool`
        If True, the evaluation/test scenario is returned, otherwise the historical
        (i.e. training) scenario is returned.
    download_dir : `str`, optional
        Path to the data files -- if None, the temp folder will be used.
        If the path does not exist, the data files will be downloaded to the give path.

        The default is None.
    return_X_y : `bool`, optional
        If True, the data is returned together with the labels (presence of a leakage) as
        two Numpy arrays, otherwise the data is returned as a
        :class:`~epyt_flow.simulation.scada.scada_data.ScadaData` instance.

        The default is False.
    return_leak_locations : `bool`
        If True, the leak locations are returned as well --
        as an instance of `scipy.sparse.bsr_array`.

        The default is False.

    Returns
    -------
    :class:`~epyt_flow.simulation.scada.scada_data.ScadaData` or `list[tuple[numpy.ndarray, numpy.ndarray]]`
        The simulated benchmark scenario as either a
        :class:`~epyt_flow.simulation.scada.scada_data.ScadaData` instance or as a tuple of
        (X, y) Numpy arrays. If 'return_leak_locations' is True, the leak locations are included
        as an instance of `scipy.sparse.bsr_array` as well.
    """
    download_dir = download_dir if download_dir is not None else get_temp_folder()

    url_data = "https://filedn.com/lumBFq2P9S74PNoLPWtzxG4/EPyT-Flow/BattLeDIM/"

    f_in = f"{'battledim_test' if test_scenario is True else 'battledim_train'}.epytflow_scada_data"
    download_if_necessary(os.path.join(download_dir, f_in), url_data + f_in)

    data = ScadaData.load_from_file(os.path.join(download_dir, f_in))

    X = data.get_data()
    y = np.zeros(X.shape[0])

    def leak_time_to_idx(t: int, round_up: bool = False):
        if round_up is False:
            return math.floor(t / 1800)
        else:
            return math.ceil(t / 1800)

    start_time = START_TIME_TEST if test_scenario is True else START_TIME_TRAIN
    leaks_config = LEAKS_CONFIG_TEST if test_scenario is True else LEAKS_CONFIG_TRAIN
    leakages = parse_leak_config(start_time, leaks_config)

    leak_locations_row = []
    leak_locations_col = []
    for leak in leakages:
        t_idx_start = leak_time_to_idx(leak.start_time)
        t_idx_end = leak_time_to_idx(leak.end_time, round_up=True)
        y[t_idx_start:t_idx_end] = 1

        leak_link_idx = data.sensor_config.links.index(leak.link_id)
        for t in range(t_idx_end - t_idx_start):
            leak_locations_row.append(t_idx_start + t)
            leak_locations_col.append(leak_link_idx)

    if return_leak_locations is True:
        y_leak_locations = bsr_array(
            (np.ones(len(leak_locations_row)), (leak_locations_row, leak_locations_col)),
            shape=(X.shape[0], len(data.sensor_config.nodes)))

    if return_X_y is True:
        if return_leak_locations is True:
            return X, y, y_leak_locations
        else:
            return X, y
    else:
        if return_leak_locations is True:
            return data, y_leak_locations
        else:
            return data


def load_battledim(test_scenario: bool, download_dir: str = None) -> ScenarioConfig:
    """
    The Battle of the Leakage Detection and Isolation Methods (*BattLeDIM*) 2020, organized by
    S. G. Vrachimis, D. G. Eliades, R. Taormina, Z. Kapelan, A. Ostfeld, S. Liu, M. Kyriakou,
    P. Pavlou, M. Qiu, and M. M. Polycarpou, as part of the 2nd International CCWI/WDSA Joint
    Conference in Beijing, China, aims at objectively comparing the performance of methods for
    the detection and localization of leakage events, relying on SCADA measurements of flow and
    pressure sensors installed within water distribution networks.

    See https://github.com/KIOS-Research/BattLeDIM for details.


    This method supports two different scenario configurations:
        - *Training/Historical configuration:* https://github.com/KIOS-Research/BattLeDIM/blob/master/Dataset%20Generator/dataset_configuration_historical.yalm
        - *Test/Evaluation configuraton:* https://github.com/KIOS-Research/BattLeDIM/blob/master/Dataset%20Generator/dataset_configuration_evaluation.yalm

    Parameters
    ----------
    test_scenario : `bool`
        If True, the evaluation/test scenario is returned, otherwise the historical
        (i.e. training) scenario is returned.
    download_dir : `str`, optional
        Path to the L-TOWN.inp file -- if None, the temp folder will be used.
        If the path does not exist, the .inp will be downloaded to the give path.

        The default is None.

    Returns
    -------
    :class:`epyt_flow.simulation.scenario_config.ScenarioConfig`
        Complete scenario configuration for this benchmark.
    """

    # Load L-Town network including the sensor placement
    if download_dir is not None:
        ltown_config = load_ltown(download_dir=download_dir, use_realistic_demands=True,
                                  include_default_sensor_placement=True)
    else:
        ltown_config = load_ltown(use_realistic_demands=True, include_default_sensor_placement=True)

    # Set simulation duration
    general_params = {"simulation_duration": 365,   # One year
                      "hydraulic_time_step": 300}   # 5min time steps

    # Add events
    start_time = START_TIME_TEST if test_scenario is True else START_TIME_TRAIN
    leaks_config = LEAKS_CONFIG_TEST if test_scenario is True else LEAKS_CONFIG_TRAIN
    leakages = parse_leak_config(start_time, leaks_config)

    # Build final scenario
    return ScenarioConfig(f_inp_in=ltown_config.f_inp_in, general_params=general_params,
                          sensor_config=ltown_config.sensor_config, system_events=leakages)
