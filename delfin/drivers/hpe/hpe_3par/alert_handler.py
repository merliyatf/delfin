# Copyright 2020 The SODA Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http:#www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import time

from oslo_log import log as logging

from delfin import exception
from delfin.common import constants
from delfin.i18n import _

LOG = logging.getLogger(__name__)


class AlertHandler(object):
    """Alert handling functions for Hpe3 parstor driver"""

    # Translation of trap severity to alert model severity
    SEVERITY_MAP = {"critical": constants.Severity.CRITICAL,
                    "major": constants.Severity.MAJOR,
                    "minor": constants.Severity.MINOR,
                    "degraded": constants.Severity.WARNING,
                    "fatal": constants.Severity.FATAL,
                    "info": constants.Severity.INFORMATIONAL,
                    "debug": constants.Severity.NOT_SPECIFIED}

    # Translation of trap alert category to alert model category
    CATEGORY_MAP = {"undefined": constants.Category.NOT_SPECIFIED,
                    "new": constants.Category.FAULT,
                    "acknowledged": constants.Category.RECOVERY,
                    "fixed": constants.Category.RECOVERY,
                    "removed": constants.Category.RECOVERY,
                    "autofixed": constants.Category.RECOVERY}

    # Attributes expected in alert info to proceed with model filling
    _mandatory_alert_attributes = (
        'component',
        'details',
        'nodeID',
        'severity',
        'timeOccurred',
        'id',
        'messageCode',
        'state',
        'serialNumber'
    )

    # ssh command
    # remove alert
    hpe3par_command_removealert = 'removealert -f '
    # get all new alerts
    HPE3PAR_COMMAND_SHOWALERT = 'showalert -d'
    # Convert received time to epoch format
    TIME_PATTERN = '%Y-%m-%d %H:%M:%S CST'

    default_me_category = 'storage-subsystem'

    def __init__(self, restclient=None, sshclient=None):
        self.restclient = restclient
        self.sshclient = sshclient

    def parse_alert(self, context, alert):
        """Parse alert data got from alert manager and fill the alert model."""
        # Check for mandatory alert attributes
        for attr in self._mandatory_alert_attributes:
            if not alert.get(attr):
                msg = "Mandatory information %s missing in alert message. " \
                      % attr
                raise exception.InvalidInput(msg)

        try:
            alert_model = dict()
            # These information are sourced from device registration info
            alert_model['alert_id'] = alert.get('messageCode')
            alert_model['alert_name'] = alert.get('messageCode')
            alert_model['severity'] = self.SEVERITY_MAP.get(
                alert.get('severity'), constants.Severity.NOT_SPECIFIED)
            alert_model['category'] = self.CATEGORY_MAP.get(
                alert.get('state'), constants.Category.NOT_SPECIFIED)
            alert_model['type'] = constants.EventType.EQUIPMENT_ALARM
            alert_model['sequence_number'] = alert.get('id')
            alert_model['occur_time'] = self.get_time_stamp(
                alert.get('timeOccurred'))
            alert_model['description'] = alert.get('details')
            alert_model['resource_type'] = constants.DEFAULT_RESOURCE_TYPE
            alert_model['location'] = alert.get('component')

            if alert.get('state') == 'autofixed':
                alert_model['clear_category'] = constants.ClearType.AUTOMATIC
            return alert_model
        except Exception as e:
            LOG.error(e)
            msg = (_("Failed to build alert model as some attributes missing "
                     "in alert message."))
            raise exception.InvalidResults(msg)

    def add_trap_config(self, context, storage_id, trap_config):
        """Config the trap receiver in storage system."""
        # Currently not implemented
        pass

    def remove_trap_config(self, context, storage_id, trap_config):
        """Remove trap receiver configuration from storage system."""
        # Currently not implemented
        pass

    def clear_alert(self, context, sshclient, alert):
        """Clear alert from storage system.
            Currently not implemented   removes command : removealert
        """
        re = 'Failed'
        try:
            if alert is not None and sshclient is not None:
                command_str = AlertHandler.hpe3par_command_removealert
                sshclient.doexec(context, command_str)
                # Determine the returned content to
                # implement the result of the device
                re = 'Success'
        except Exception as e:
            LOG.error(e)
            raise exception.StorageBackendException(
                reason='Failed to ssh Hpe3parStor')
        return re

    def list_alerts(self, context):
        try:
            # Get list of Hpe3parStor alerts
            alert_list = []
            try:
                command_str = AlertHandler.HPE3PAR_COMMAND_SHOWALERT
                reslist = self.sshclient.doexec(context, command_str)
            except Exception as e:
                LOG.error(e)
                raise exception.StorageBackendException(
                    reason='Failed to ssh Hpe3parStor')
            message_code = ''
            event_type = ''
            severity = ''
            state = ''
            alarm_id = ''
            occur_time = ''
            alert_message = ''
            component = ''

            alertlist = reslist.split('\n')

            for alertinfo in alertlist:
                strline = alertinfo
                if strline is not None and strline != '':
                    # strline = strline.replace(" ", "")
                    strinfo = strline.split(': ', 1)
                    strinfo[0] = strinfo[0].replace(" ", "")
                    if strinfo[0] == 'Id':
                        alarm_id = strinfo[1]
                    elif strinfo[0] == 'State':
                        if strinfo[1] == 'New':
                            state = constants.Category.FAULT
                    elif strinfo[0] == 'MessageCode':
                        message_code = strinfo[1]
                    elif strinfo[0] == 'Time':
                        occur_time = strinfo[1]
                    elif strinfo[0] == 'Severity':
                        if strinfo[1] == 'Major':
                            severity = constants.Severity.MAJOR
                        elif strinfo[1] == 'Minor':
                            severity = constants.Severity.MINOR
                        elif strinfo[1] == 'Critical':
                            severity = constants.Severity.CRITICAL
                        elif strinfo[1] == 'Degraded':
                            severity = constants.Severity.WARNING
                        elif strinfo[1] == 'Fatal':
                            severity = constants.Severity.FATAL
                        elif strinfo[1] == 'Informational':
                            severity = constants.Severity.INFORMATIONAL
                        elif strinfo[1] == 'Debug':
                            severity = constants.Severity.NOT_SPECIFIED
                    elif strinfo[0] == 'Type':
                        event_type = strinfo[1]
                    elif strinfo[0] == 'Message':
                        alert_message = strinfo[1]
                    elif strinfo[0] == 'Component':
                        component = strinfo[1]

                        alert_model = {
                            'alert_id': message_code,
                            'alert_name': event_type,
                            'severity': severity,
                            'category': state,
                            'type': constants.EventType.EQUIPMENT_ALARM,
                            'sequence_number': alarm_id,
                            'occur_time': self.get_time_stamp(occur_time),
                            'description': alert_message,
                            'resource_type': constants.DEFAULT_RESOURCE_TYPE,
                            'location': component
                        }

                        alert_list.append(alert_model)
                        message_code = ''
                        event_type = ''
                        severity = ''
                        state = ''
                        alarm_id = ''
                        occur_time = ''
                        alert_message = ''
                        component = ''
            return alert_list

        except Exception as err:
            LOG.error(
                "Failed to get pool metrics from Hpe3parStor: {}".format(err))
            raise exception.StorageBackendException(
                reason='Failed to get pool metrics from Hpe3parStor')

    def get_time_stamp(self, time_str):
        """ Time stamp to time conversion
        """
        time_stamp = None
        try:
            if time_str is not None:
                # Convert to time array first
                time_array = time.strptime(time_str, AlertHandler.TIME_PATTERN)
                # Convert to timestamps to milliseconds
                time_stamp = int(time.mktime(time_array) * 1000)
        except Exception as e:
            LOG.error(e)

        return time_stamp
