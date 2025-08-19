from hmbot.device.device import Device
from hmbot.device.connector.hdc import HDC
from hmbot.model.vht import VHTParser
from hmbot.utils.cv import write
import uiautomator2
from hmbot.model.event import KeyEvent
from hmbot.utils.proto import SystemKey
from hmbot.model.ptg import PTG
from hmbot.model.page import Page
from hmbot.app.harmony_app import HarmonyApp
from hmbot.app.app import App


device = Device('127.0.0.1:5555', 'harmony')
page = device.dump_page()
write('test.png',page.img)

# app = HarmonyApp(device=device1)
# print(app.bundle, app.entry, app.main_page, app.name)
# print(isinstance(app, App))
# print(isinstance(app, HarmonyApp))
# print(device1.connector.current_ability())
# device2 = Device('emulator-5554', 'android')
# print(device.connector._hidumper('AbilityManagerService', '-i 16'))
# print(device.connector.get_current_ability())
# VHTParser.dump(device.dump_hierarchy(), 'origin.json')
# img = device.screenshot()
# print(img.shape)

# VHTParser.dump(device2.automator.dump_hierarchy(), 'and1.json')
# print(device.automator._driver.app_current())
# device2.recent()
# print(device1.weight, )
# print(device.automator._driver.dump_hierarchy())

# window = device.dump_window()
# page = window.pages[0]
# cv2.imwrite('page.jpg', page.img)

# print(device.connector._hidumper('AbilityManagerService', '-i 16'))