from pydle.features.rfc1459 import RFC1459Support


class RplWhoisHostSupport(RFC1459Support):
    """ Adds support for RPL_WHOISHOST messages (378) """

    async def on_raw_378(self, message):
        """ handles a RPL_WHOISHOST message """
        _, target, data = message.params
        data = data.split(" ")
        target = message.params[1]
        ip_addr = data[-1]
        host = data[-2]

        meta = {"real_ip_address": ip_addr, "real_hostname": host}
        self._sync_user(target, meta)
        if target in self._whois_info:
            self._whois_info[target]["real_ip_address"] = ip_addr
            self._whois_info[target]["real_hostname"] = host

    async def whois(self, nickname):
        info = await super().whois(nickname)
        info.setdefault("real_ip_address", None)
        info.setdefault("real_hostname", None)
        return info
