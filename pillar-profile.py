#!/usr/bin/python3

import os
import sys

import yappi

import salt.config
import salt.pillar
import salt.syspaths
import salt.utils.master

if len(sys.argv) != 2:
    print("Minion ID must be specified as command line parameter!")
    exit(2)

MINION_ID = sys.argv[1]

salt_conf_path = os.path.join(salt.syspaths.CONFIG_DIR, "master")
salt_opts = salt.config.master_config(salt_conf_path)

class PillarProfiler:
    def __init__(self, opts):
        self.opts = opts
        self.context = {}
        import salt.daemons.masterapi
        self.masterapi = salt.daemons.masterapi.RemoteFuncs(self.opts)
        import salt.fileserver
        self.fs_ = salt.fileserver.Fileserver(self.opts)

    def pillar(self, load):
        yappi.start()
        ret = self._pillar(load)
        yappi.stop()
        print("\n\n\n\n============================= Time profile =============================")
        yappi.get_func_stats().print_all(
            columns={
                0: ("name", 92),
                1: ("ncall", 16),
                2: ("tsub", 8),
                3: ("ttot", 8),
                4: ("tavg", 8),
            }
        )
        print("\n\n\n\n============================= Calls profile =============================")
        yappi.get_func_stats().sort("ncall").print_all(
            columns={
                0: ("name", 92),
                1: ("ncall", 16),
                2: ("tsub", 8),
                3: ("ttot", 8),
                4: ("tavg", 8),
            }
        )
        yappi.clear_stats()
        print("\n\n\n\n============================= Pillar return =============================")
        print(ret)
        return ret

    def _pillar(self, load):
        """
        Return the pillar data for the minion

        :param dict load: Minion payload

        :rtype: dict
        :return: The pillar data for the minion
        """
        if any(key not in load for key in ("id", "grains")):
            return False
        if not salt.utils.verify.valid_id(self.opts, load["id"]):
            return False
        load["grains"]["id"] = load["id"]

        pillar = salt.pillar.get_pillar(
            self.opts,
            load["grains"],
            load["id"],
            load.get("saltenv", load.get("env")),
            ext=load.get("ext"),
            pillar_override=load.get("pillar_override", {}),
            pillarenv=load.get("pillarenv"),
            extra_minion_data=load.get("extra_minion_data"),
            clean_cache=load.get("clean_cache"),
            context=self.context,
        )
        data = pillar.compile_pillar()
        self.fs_.update_opts()
        if self.opts.get("minion_data_cache", False):
            self.masterapi.cache.store(
                "minions/{}".format(load["id"]),
                "data",
                {"grains": load["grains"], "pillar": data},
            )
            if self.opts.get("minion_data_cache_events") is True:
                self.event.fire_event(
                    {"Minion data cache refresh": load["id"]},
                    tagify(load["id"], "refresh", "minion"),
                )
        return data

mpu = salt.utils.master.MasterPillarUtil(tgt=MINION_ID, opts=salt_opts)
grains = mpu.get_minion_grains().get(MINION_ID)
if grains is None:
    print("Unable to get grains from the minion!")
    exit(3)
print("============================= Grains return =============================")
print(grains)
pp = PillarProfiler(salt_opts)
pp.pillar(
    {
        "id": MINION_ID,
        "grains": grains,
        "saltenv": "base",
        "pillarenv": "",
        "pillar_override": {},
        "extra_minion_data": {},
    }
)
