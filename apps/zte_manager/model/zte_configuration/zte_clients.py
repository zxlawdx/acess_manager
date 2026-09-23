def wifi_clients(zte):
    zte.get_view("localNetStatus")

    return zte.get_menu(
        "wlan_client_stat_lua.lua"
    )

def lan_clients(zte):
    zte.get_view(
        "localNetStatus"
    )

    return zte.get_menu(
        "accessdev_landevs_lua.lua"
    )