"""
This module provides all handlers for requests concerning scenarios.
"""
import warnings
import os
import falcon

from .base_handler import BaseHandler
from .res_manager import ResourceManager
from ..utils import get_temp_folder, pack_zip_archive
from .scada_data_handler import ScadaDataManager
from ..simulation import ScenarioSimulator, Leakage, SensorConfig, SensorFault, \
    SensorNoise, ModelUncertainty


class ScenarioManager(ResourceManager):
    """
    Class for managing all scenarios that are currently used by the REST API.
    """
    def create(self, **kwds) -> str:
        """
        Creates a new scenario -- e.g. loading a given .inp file or
        using a given scenario configuration.

        Returns
        -------
        `str`
            UUID of the new scenario.
        """
        return self.create_new_item(ScenarioSimulator(**kwds))

    def close_item(self, item: ScenarioSimulator) -> None:
        item.close()


class ScenarioBaseHandler(BaseHandler):
    """
    Base class for all handlers concerning scenarios.

    Parameters
    ----------
    scenario_mgr : :class:`~epyt_flow.rest_api.scenario_handler.ScenarioManager`
        Instance for managing all scenarios.
    """
    def __init__(self, scenario_mgr: ScenarioManager):
        self.scenario_mgr = scenario_mgr


class ScenarioRemoveHandler(ScenarioBaseHandler):
    """
    Class for handling a DELETE request for a given scenario.
    """
    def on_delete(self, _, resp: falcon.Response, scenario_id: str) -> None:
        """
        Deletes a given scenario.

        Parameters
        ----------
        resp : `falcon.Response`
            Response instance.
        scenario_id : `str`
            UUID of the scenario.
        """
        try:
            if self.scenario_mgr.validate_uuid(scenario_id) is False:
                self.send_invalid_resource_id_error(resp)
                return

            self.scenario_mgr.remove(scenario_id)
        except Exception as ex:
            warnings.warn(str(ex))
            resp.status = falcon.HTTP_INTERNAL_SERVER_ERROR


class ScenarioExportHandler(ScenarioBaseHandler):
    """
    Class for handling GET requests for exporting a given scenario to EPANET files
    -- i.e. .inp and (otpionally) .msx files.
    """
    def __create_temp_file_path(self, scenario_id: str, file_ext: str) -> None:
        """
        Returns a path to a temporary file for storing the scenario.

        Parameters
        ----------
        scenario_id : `str`
            UUID of the scenario.
        file_ext : `str`
            File extension.
        """
        return os.path.join(get_temp_folder(), f"{scenario_id}.{file_ext}")

    def __send_temp_file(self, resp: falcon.Response, tmp_file: str,
                         content_type: str = "application/octet-stream") -> None:
        """
        Sends a given file (`tmp_file`) to the the client.

        Parameters
        ----------
        resp : `falcon.Response`
            Response instance.
        tmp_file : `str`
            Path to the temporary file to be send.
        """
        resp.status = falcon.HTTP_200
        resp.content_type = content_type
        with open(tmp_file, 'rb') as f:
            resp.text = f.read()

    def on_get(self, _, resp: falcon.Response, scenario_id: str) -> None:
        """
        Exports a given scenario to an .inp and (optionally) .msx file.

        Parameters
        ----------
        resp : `falcon.Response`
            Response instance.
        scenario_id : `str`
            UUID of the scenario.
        """
        try:
            if self.scenario_mgr.validate_uuid(scenario_id) is False:
                self.send_invalid_resource_id_error(resp)
                return

            my_scenario = self.scenario_mgr.get(scenario_id)

            f_inp_out = self.__create_temp_file_path(scenario_id, "inp")
            f_msx_out = self.__create_temp_file_path(scenario_id, "msx")
            my_scenario.save_to_epanet_file(f_inp_out, f_msx_out)

            if os.path.isfile(f_msx_out):
                f_out = self.__create_temp_file_path(scenario_id, "zip")
                pack_zip_archive([f_inp_out, f_msx_out], f_out)

                self.__send_temp_file(resp, f_out)
                os.remove(f_out)
                os.remove(f_msx_out)
            else:
                self.__send_temp_file(resp, f_inp_out)
            os.remove(f_inp_out)
        except Exception as ex:
            warnings.warn(str(ex))
            resp.status = falcon.HTTP_INTERNAL_SERVER_ERROR


class ScenarioConfigHandler(ScenarioBaseHandler):
    """
    Class for handling a GET request for getting the scenario configuration of a given scenario.
    """
    def on_get(self, _, resp: falcon.Response, scenario_id: str) -> None:
        """
        Gets the scenario configuration of a given scenario.

        Parameters
        ----------
        resp : `falcon.Response`
            Response instance.
        scenario_id : `str`
            UUID of the scenario.
        """
        try:
            if self.scenario_mgr.validate_uuid(scenario_id) is False:
                self.send_invalid_resource_id_error(resp)
                return

            my_sceanrio_config = self.scenario_mgr.get(scenario_id).get_scenario_config()
            self.send_json_response(resp, my_sceanrio_config)
        except Exception as ex:
            warnings.warn(str(ex))
            resp.status = falcon.HTTP_INTERNAL_SERVER_ERROR


class ScenarioNewHandler(ScenarioBaseHandler):
    """
    Class for handling POST requests for creating a new scenario.
    """
    def on_post(self, req: falcon.Request, resp: falcon.Response) -> None:
        """
        Creates/Loads a new scenario.

        Parameters
        ----------
        req : `falcon.Request`
            Request instance.
        resp : `falcon.Response`
            Response instance.
        scenario_id : `str`
            UUID of the scenario.
        """
        try:
            args = self.load_json_data_from_request(req)
            scenario_id = self.scenario_mgr.create(**args)
            self.send_json_response(resp, {"scenario_id": scenario_id})
        except Exception as ex:
            warnings.warn(str(ex))
            resp.status = falcon.HTTP_INTERNAL_SERVER_ERROR


class ScenarioModelUncertaintyHandler(ScenarioBaseHandler):
    """
    Class for handling GET and POST requests concerning model uncertainty.
    """
    def on_get(self, _, resp: falcon.Response, scenario_id: str) -> None:
        """
        Gets the model uncertainties of a given scenario.

        Parameters
        ----------
        resp : `falcon.Response`
            Response instance.
        scenario_id : `str`
            UUID of the scenario.
        """
        try:
            if self.scenario_mgr.validate_uuid(scenario_id) is False:
                self.send_invalid_resource_id_error(resp)
                return

            my_model_uncertainties = self.scenario_mgr.get(scenario_id).model_uncertainty
            self.send_json_response(resp, my_model_uncertainties)
        except Exception as ex:
            warnings.warn(str(ex))
            resp.status = falcon.HTTP_INTERNAL_SERVER_ERROR

    def on_post(self, req: falcon.Request, resp: falcon.Response, scenario_id: str) -> None:
        """
        Sets the model uncertainties of a given scenario.

        Parameters
        ----------
        req : `falcon.Request`
            Request instance.
        resp : `falcon.Response`
            Response instance.
        scenario_id : `str`
            UUID of the scenario.
        """
        try:
            if self.scenario_mgr.validate_uuid(scenario_id) is False:
                self.send_invalid_resource_id_error(resp)
                return

            model_uncertainty = self.load_json_data_from_request(req)
            if not isinstance(model_uncertainty, ModelUncertainty):
                self.send_json_parsing_error(resp)
                return

            self.scenario_mgr.get(scenario_id).model_uncertainty = model_uncertainty
        except Exception as ex:
            warnings.warn(str(ex))
            resp.status = falcon.HTTP_INTERNAL_SERVER_ERROR


class ScenarioSensorUncertaintyHandler(ScenarioBaseHandler):
    """
    Class for handling GET and POST requests concerning sensor uncertainty (i.e. noise).
    """
    def on_get(self, _, resp: falcon.Response, scenario_id: str) -> None:
        """
        Gets the sensor uncertainty (i.e. noise) of a given scenario.

        Parameters
        ----------
        resp : `falcon.Response`
            Response instance.
        scenario_id : `str`
            UUID of the scenario.
        """
        try:
            if self.scenario_mgr.validate_uuid(scenario_id) is False:
                self.send_invalid_resource_id_error(resp)
                return

            my_sensor_noise = self.scenario_mgr.get(scenario_id).sensor_noise
            self.send_json_response(resp, my_sensor_noise)
        except Exception as ex:
            warnings.warn(str(ex))
            resp.status = falcon.HTTP_INTERNAL_SERVER_ERROR

    def on_post(self, req: falcon.Request, resp: falcon.Response, scenario_id: str) -> None:
        """
        Sets the sensor uncertainty (i.e. noise) of a given scenario.

        Parameters
        ----------
        req : `falcon.Request`
            Request instance.
        resp : `falcon.Response`
            Response instance.
        scenario_id : `str`
            UUID of the scenario.
        """
        try:
            if self.scenario_mgr.validate_uuid(scenario_id) is False:
                self.send_invalid_resource_id_error(resp)
                return

            sensor_noise = self.load_json_data_from_request(req)
            if not isinstance(sensor_noise, SensorNoise):
                self.send_json_parsing_error(resp)
                return

            self.scenario_mgr.get(scenario_id).sensor_noise = sensor_noise
        except Exception as ex:
            warnings.warn(str(ex))
            resp.status = falcon.HTTP_INTERNAL_SERVER_ERROR


class ScenarioLeakageHandler(ScenarioBaseHandler):
    """
    Class for handling GET and POST requests concerning leakages.
    """
    def on_get(self, _, resp: falcon.Response, scenario_id: str) -> None:
        """
        Gets all leakages of a given scenario.

        Parameters
        ----------
        resp : `falcon.Response`
            Response instance.
        scenario_id : `str`
            UUID of the scenario.
        """
        try:
            if self.scenario_mgr.validate_uuid(scenario_id) is False:
                self.send_invalid_resource_id_error(resp)
                return

            my_leakages = self.scenario_mgr.get(scenario_id).leakages
            self.send_json_response(resp, my_leakages)
        except Exception as ex:
            warnings.warn(str(ex))
            resp.status = falcon.HTTP_INTERNAL_SERVER_ERROR

    def on_post(self, req: falcon.Request, resp: falcon.Response, scenario_id: str) -> None:
        """
        Adds a new leakage to a given scenario.

        Parameters
        ----------
        req : `falcon.Request`
            Request instance.
        resp : `falcon.Response`
            Response instance.
        scenario_id : `str`
            UUID of the scenario.
        """
        try:
            if self.scenario_mgr.validate_uuid(scenario_id) is False:
                self.send_invalid_resource_id_error(resp)
                return

            leakage = self.load_json_data_from_request(req)
            if not isinstance(leakage, Leakage):
                self.send_json_parsing_error(resp)
                return

            self.scenario_mgr.get(scenario_id).add_leakage(leakage)
        except Exception as ex:
            warnings.warn(str(ex))
            resp.status = falcon.HTTP_INTERNAL_SERVER_ERROR


class ScenarioSensorFaultHandler(ScenarioBaseHandler):
    """
    Class for handling GET and POST requests concerning sensor faults.
    """
    def on_get(self, _, resp: falcon.Response, scenario_id: str) -> None:
        """
        Gets all sensor faults of a given scenario.

        Parameters
        ----------
        resp : `falcon.Response`
            Response instance.
        scenario_id : `str`
            UUID of the scenario.
        """
        try:
            if self.scenario_mgr.validate_uuid(scenario_id) is False:
                self.send_invalid_resource_id_error(resp)
                return

            my_sensor_faults = self.scenario_mgr.get(scenario_id).sensor_faults
            self.send_json_response(resp, my_sensor_faults)
        except Exception as ex:
            warnings.warn(str(ex))
            resp.status = falcon.HTTP_INTERNAL_SERVER_ERROR

    def on_post(self, req: falcon.Request, resp: falcon.Response, scenario_id: str) -> None:
        """
        Adds a new sensor fault to a given scenario.

        Parameters
        ----------
        req : `falcon.Request`
            Request instance.
        resp : `falcon.Response`
            Response instance.
        scenario_id : `str`
            UUID of the scenario.
        """
        try:
            if self.scenario_mgr.validate_uuid(scenario_id) is False:
                self.send_invalid_resource_id_error(resp)
                return

            sensor_fault = self.load_json_data_from_request(req)
            if not isinstance(sensor_fault, SensorFault):
                self.send_json_parsing_error(resp)
                return

            self.scenario_mgr.get(scenario_id).add_sensor_fault(sensor_fault)
        except Exception as ex:
            warnings.warn(str(ex))
            resp.status = falcon.HTTP_INTERNAL_SERVER_ERROR


class ScenarioTopologyHandler(ScenarioBaseHandler):
    """
    Class for handling GET requests for getting the topology of a given scenario.
    """
    def on_get(self, _, resp: falcon.Response, scenario_id: str) -> None:
        """
        Gets the topology of a given scenario.

        Parameters
        ----------
        resp : `falcon.Response`
            Response instance.
        scenario_id : `str`
            UUID of the scenario.
        """
        try:
            if self.scenario_mgr.validate_uuid(scenario_id) is False:
                self.send_invalid_resource_id_error(resp)
                return

            my_topology = self.scenario_mgr.get(scenario_id).get_topology()
            self.send_json_response(resp, my_topology)
        except Exception as ex:
            warnings.warn(str(ex))
            resp.status = falcon.HTTP_INTERNAL_SERVER_ERROR


class ScenarioGeneralParamsHandler(ScenarioBaseHandler):
    """
    Class for handling GET and POST requests for the general parameters of a given scenario.
    """
    def on_get(self, _, resp: falcon.Response, scenario_id: str) -> None:
        """
        Gets the general parameters (e.g. simulation duration, etc.) of a given scenario.

        Parameters
        ----------
        resp : `falcon.Response`
            Response instance.
        scenario_id : `str`
            UUID of the scenario.
        """
        try:
            if self.scenario_mgr.validate_uuid(scenario_id) is False:
                self.send_invalid_resource_id_error(resp)
                return

            my_general_params = self.scenario_mgr.get(scenario_id).get_scenario_config().\
                general_params
            self.send_json_response(resp, my_general_params)
        except Exception as ex:
            warnings.warn(str(ex))
            resp.status = falcon.HTTP_INTERNAL_SERVER_ERROR

    def on_post(self, req: falcon.Request, resp: falcon.Response, scenario_id: str) -> None:
        """
        Sets the general parameters of a given scenario.

        Parameters
        ----------
        req : `falcon.Request`
            Request instance.
        resp : `falcon.Request`
            Request instance.
        scenario_id : `str`
            UUID of the scenario.
        """
        try:
            if self.scenario_mgr.validate_uuid(scenario_id) is False:
                self.send_invalid_resource_id_error(resp)
                return

            general_params = self.load_json_data_from_request(req)
            if not isinstance(general_params, dict):
                self.send_json_parsing_error(resp)
                return

            self.scenario_mgr.get(scenario_id).set_general_parameters(**general_params)
        except Exception as ex:
            warnings.warn(str(ex))
            resp.status = falcon.HTTP_INTERNAL_SERVER_ERROR


class ScenarioSensorConfigHandler(ScenarioBaseHandler):
    """
    Class for handling GET and POST requests for the sensor configuration of a given scenario.
    """
    def on_get(self, _, resp: falcon.Response, scenario_id: str) -> None:
        """
        Gets the sensor configuration of a given scenario.

        Parameters
        ----------
        resp : `falcon.Response`
            Response instance.
        scenario_id : `str`
            UUID of the scenario.
        """
        try:
            if self.scenario_mgr.validate_uuid(scenario_id) is False:
                self.send_invalid_resource_id_error(resp)
                return

            my_sensor_config = self.scenario_mgr.get(scenario_id).sensor_config
            self.send_json_response(resp, my_sensor_config)
        except Exception as ex:
            warnings.warn(str(ex))
            resp.status = falcon.HTTP_INTERNAL_SERVER_ERROR

    def on_post(self, req: falcon.Request, resp: falcon.Response, scenario_id: str) -> None:
        """
        Sets the sensor configuration of a given scenario.

        Parameters
        ----------
        req : `falcon.Request`
            Request instance.
        resp : `falcon.Request`
            Request instance.
        scenario_id : `str`
            UUID of the scenario.
        """
        try:
            if self.scenario_mgr.validate_uuid(scenario_id) is False:
                self.send_invalid_resource_id_error(resp)
                return

            sensor_config = self.load_json_data_from_request(req)
            if not isinstance(sensor_config, SensorConfig):
                self.send_json_parsing_error(resp)
                return

            my_scenario = self.scenario_mgr.get(scenario_id)
            my_scenario.sensor_config = sensor_config
        except Exception as ex:
            warnings.warn(str(ex))
            resp.status = falcon.HTTP_INTERNAL_SERVER_ERROR


class ScenarioNodeDemandPatternHandler(ScenarioBaseHandler):
    """
    Class for handling POST requests for node demand patterns of a given scenario.
    """
    def on_post(self, req: falcon.Request, resp: falcon.Response, scenario_id: str,
                node_id: str) -> None:
        """
        Sets the demand pattern of a specific node in a given scenario.

        Parameters
        ----------
        req : `falcon.Request`
            Request instance.
        resp : `falcon.Response`
            Response instance.
        scenario_id : `str`
            UUID of the scenario.
        node_id : `str`
            ID of the node.
        """
        try:
            if self.scenario_mgr.validate_uuid(scenario_id) is False:
                self.send_invalid_resource_id_error(resp)
                return

            params = self.load_json_data_from_request(req)

            my_scenario = self.scenario_mgr.get(scenario_id)
            my_scenario.set_node_demand_pattern(node_id, params["base_demand"],
                                                params["demand_pattern_id"],
                                                params["demand_pattern"])
        except Exception as ex:
            warnings.warn(str(ex))
            resp.data = str(ex)
            resp.status = falcon.HTTP_INTERNAL_SERVER_ERROR


class ScenarioSimulationHandler(ScenarioBaseHandler):
    """
    Class for handling GET requests for simulating a given scenario.

    Parameters
    ----------
    scada_data_mgr : :class:`~epyt_flow.rest_api.scenario_handler.ScadaDataBaseHandler`
        SCADA data manager.
    """
    def __init__(self, scada_data_mgr: ScadaDataManager, **kwds):
        self.scada_data_mgr = scada_data_mgr

        super().__init__(**kwds)

    def on_post(self, req: falcon.Request, resp: falcon.Response, scenario_id: str) -> None:
        """
        Runs the simulation of a given scenario.

        Note that in contrat to the GET request
        (:func:`~epyt_flow.rest_api.scenario_handler.ScenarioSimulationHandler.on_get`),
        the POST request allows to specify additional arguments passed to
        :func:`~epyt_flow.simulation.scenario_simulator.ScenarioSimulator.run_simulation`.

        Parameters
        ----------
        req : `falcon.Request`
            Request instance.
        resp : `falcon.Response`
            Response instance.
        scenario_id : `str`
            UUID of the scenario.
        """
        try:
            if self.scenario_mgr.validate_uuid(scenario_id) is False:
                self.send_invalid_resource_id_error(resp)
                return

            params = self.load_json_data_from_request(req)

            my_scenario = self.scenario_mgr.get(scenario_id)
            res = my_scenario.run_simulation(**params)

            data_id = self.scada_data_mgr.create_new_item(res)
            self.send_json_response(resp, {"data_id": data_id})
        except Exception as ex:
            warnings.warn(str(ex))
            resp.data = str(ex)
            resp.status = falcon.HTTP_INTERNAL_SERVER_ERROR

    def on_get(self, _, resp: falcon.Response, scenario_id: str) -> None:
        """
        Runs the simulation of a given scenario.

        Parameters
        ----------
        resp : `falcon.Response`
            Response instance.
        scenario_id : `str`
            UUID of the scenario.
        """
        try:
            if self.scenario_mgr.validate_uuid(scenario_id) is False:
                self.send_invalid_resource_id_error(resp)
                return

            my_scenario = self.scenario_mgr.get(scenario_id)
            res = my_scenario.run_simulation()

            data_id = self.scada_data_mgr.create_new_item(res)
            self.send_json_response(resp, {"data_id": data_id})
        except Exception as ex:
            warnings.warn(str(ex))
            resp.data = str(ex)
            resp.status = falcon.HTTP_INTERNAL_SERVER_ERROR


class ScenarioBasicQualitySimulationHandler(ScenarioBaseHandler):
    """
    Class for handling POST requests for runing a basic quality simulation of a given scenario.

    Parameters
    ----------
    scada_data_mgr : :class:`~epyt_flow.rest_api.scenario_handler.ScadaDataBaseHandler`
        SCADA data manager.
    """
    def __init__(self, scada_data_mgr: ScadaDataManager, **kwds):
        self.scada_data_mgr = scada_data_mgr

        super().__init__(**kwds)

    def on_post(self, req: falcon.Request, resp: falcon.Response, scenario_id: str) -> None:
        """
        Runs the basic quality simulation of a given scenario.

        Parameters
        ----------
        req : `falcon.Request`
            Request instance.
        resp : `falcon.Response`
            Response instance.
        scenario_id : `str`
            UUID of the scenario.
        """
        try:
            if self.scenario_mgr.validate_uuid(scenario_id) is False:
                self.send_invalid_resource_id_error(resp)
                return

            params = self.load_json_data_from_request(req)

            my_scenario = self.scenario_mgr.get(scenario_id)
            res = my_scenario.run_basic_quality_simulation(**params)

            data_id = self.scada_data_mgr.create_new_item(res)
            self.send_json_response(resp, {"data_id": data_id})
        except Exception as ex:
            warnings.warn(str(ex))
            resp.data = str(ex)
            resp.status = falcon.HTTP_INTERNAL_SERVER_ERROR


class ScenarioAdvancedQualitySimulationHandler(ScenarioBaseHandler):
    """
    Class for handling POST requests for runing an advanced quality simulation of a given scenario.

    Parameters
    ----------
    scada_data_mgr : :class:`~epyt_flow.rest_api.scenario_handler.ScadaDataBaseHandler`
        SCADA data manager.
    """
    def __init__(self, scada_data_mgr: ScadaDataManager, **kwds):
        self.scada_data_mgr = scada_data_mgr

        super().__init__(**kwds)

    def on_post(self, req: falcon.Request, resp: falcon.Response, scenario_id: str) -> None:
        """
        Runs the advanced quality simulation of a given scenario.

        Parameters
        ----------
        req : `falcon.Request`
            Request instance.
        resp : `falcon.Response`
            Response instance.
        scenario_id : `str`
            UUID of the scenario.
        """
        try:
            if self.scenario_mgr.validate_uuid(scenario_id) is False:
                self.send_invalid_resource_id_error(resp)
                return

            params = self.load_json_data_from_request(req)

            my_scenario = self.scenario_mgr.get(scenario_id)
            res = my_scenario.run_advanced_quality_simulation(**params)

            data_id = self.scada_data_mgr.create_new_item(res)
            self.send_json_response(resp, {"data_id": data_id})
        except Exception as ex:
            warnings.warn(str(ex))
            resp.data = str(ex)
            resp.status = falcon.HTTP_INTERNAL_SERVER_ERROR
