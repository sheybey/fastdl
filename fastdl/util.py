from steam.steamid import SteamID
from . import steam_api


def string_to_steamid(string, resolve_customurl=True):
    try:
        steamid = SteamID(string)
        if not steamid.is_valid() and resolve_customurl:
            steamid = SteamID(
                steam_api.ISteamUser.ResolveVanityURL(
                    vanityurl=string
                ).get('response', {}).get('steamid')
            )
        return steamid
    except ValueError:
        return SteamID()
