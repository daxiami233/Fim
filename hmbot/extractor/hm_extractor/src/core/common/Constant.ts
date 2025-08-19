export default class Const {

    static readonly MODULE_JSON5 = "src/main/module.json5";
    static readonly PROFILE_DIR = "src/main/resources/base/profile";
    static readonly ETS_DIR = "src/main/ets";
    static readonly DEFAULT_NAME = "default";

    static readonly BUILDCONFIG = "build-profile.json5";

    static readonly MAINPAGEFILES = "/entry/src/main/resources/base/profile/main_pages.json";
    static readonly ROUTERMAPFILE = "/entry/src/main/resources/base/profile/router_map.json";


    static ROUTERTRANSTIONSTMTS: Map<string, number> = new Map([
        ['pushUrl', 0],
        ['replaceUrl', 0]
    ]);
    static NAVI_TRANSTION_STMTS: Map<string, number> = new Map([
        ['pushPathByName', 0],
        ['pushPath', 0],
        ['replacePathByName', 0],
        ['replacePath', 0],
    ]);
    static readonly PAGETARGETOBJNAME = "url";
}