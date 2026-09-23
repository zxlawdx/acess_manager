def device_status(zte):
    zte.get_view(
        "statusMgr",
        Menu3Location=0
    )

    return zte.get_menu(
        "devmgr_statusmgr_lua.lua"
    )


def wan_status(zte):
    zte.get_view(
        "ethWanStatus",
        Menu3Location=0
    )

    return zte.get_menu(
        "wan_internetstatus_lua.lua",
        TypeUplink=2,
        pageType=1,
    )