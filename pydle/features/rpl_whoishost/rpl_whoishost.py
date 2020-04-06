from pydle import BasicClient


class Rpl_WhoisHostSupport(BasicClient):
    async def on_raw_378(self, message):
        print("on_raw_378({!r}".format(message))
