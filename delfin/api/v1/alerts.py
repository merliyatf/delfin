# Copyright 2020 The SODA Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from oslo_log import log

from delfin import db
from delfin.api.common import wsgi
from delfin.drivers import api as driver_manager

LOG = log.getLogger(__name__)


class AlertController(wsgi.Controller):
    def __init__(self):
        super().__init__()
        self.driver_manager = driver_manager.API()

    @wsgi.response(200)
    def delete(self, req, id, sequence_number):
        ctx = req.environ['delfin.context']
        _ = db.storage_get(ctx, id)
        self.driver_manager.clear_alert(ctx, id, sequence_number)


def create_resource():
    return wsgi.Resource(AlertController())
