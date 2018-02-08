from pecan import expose
from pecan.rest import RestController

import json

from prtg import  module

class Root(RestController):

    @expose(template='json')
    def get(self, **kwargs):
        """
        Show the health of Ceph encoded as 0=GREEN 1=WARNING 2=ERROR 3=UNKNOWN
        """
        health_raw = module.instance.get("health")
        health = json.loads(health_raw['json'])['status']

        health_to_int = {
                          "HEALTH_OK": 0,
                          "HEALTH_WARN": 1,
                          "HEALTH_ERR": 2,
                        }

        health_int = health_to_int.get(health, 3)

        return {
            "prtg": {
              "result": [
                 {
                   "channel": "Health (integer)",
                   "value": health_int
                   "LimitMaxError": 1,
                   "LimitMaxWarning": 0,
                   "LimitMode": 1
                 }
              ],
              "text": "The health status as integer of Ceph"
            }
        }
